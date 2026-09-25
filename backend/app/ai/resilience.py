import json
import re
import time
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from fastapi import HTTPException, status


from app.ai.observability import TokenUsage, CostBreakdown, calculate_token_cost


class ProviderErrorType(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_429 = "RATE_LIMIT_429"
    SERVER_ERROR_5XX = "SERVER_ERROR_5XX"
    MALFORMED_JSON = "MALFORMED_JSON"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    CONTENT_FILTER = "CONTENT_FILTER"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


class ProviderExecutionEvent(BaseModel):
    provider_name: str = Field(..., description="Name of the AI provider (e.g. groq, gemini, nvidia)")
    model_name: Optional[str] = Field(default=None, description="Model identifier used")
    latency_ms: Optional[float] = Field(default=None, description="Execution duration in milliseconds")
    error_type: Optional[ProviderErrorType] = Field(default=None, description="Classified error type if failed")
    error_detail: Optional[str] = Field(default=None, description="Sanitized error description")
    retry_count: int = Field(default=0, ge=0, description="Number of bounded in-provider retries performed")
    success: bool = Field(default=True, description="Whether the call succeeded")
    token_usage: Optional[TokenUsage] = Field(default=None, description="Extracted token usage if available")
    cost: Optional[CostBreakdown] = Field(default=None, description="Deterministic cost calculation if available")
    operation: Optional[str] = Field(default=None, description="Operation identifier e.g. ats_analysis, resume_tailoring_initial")
    timestamp: float = Field(default_factory=time.time, description="Epoch timestamp of the event")

    model_config = ConfigDict(populate_by_name=True)


class ProviderResilienceError(Exception):
    def __init__(
        self,
        error_type: ProviderErrorType,
        detail: str,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        raw_error: Optional[Exception] = None,
    ):
        super().__init__(detail)
        self.error_type = error_type
        self.detail = detail
        self.status_code = status_code
        self.provider_name = provider_name
        self.model_name = model_name
        self.raw_error = raw_error

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail=self.detail,
        )


def classify_provider_exception(exc: Exception, provider_name: Optional[str] = None) -> ProviderErrorType:
    """Deterministically classifies any provider exception into standard ProviderErrorType."""
    if isinstance(exc, ProviderResilienceError):
        return exc.error_type

    if isinstance(exc, HTTPException):
        if exc.status_code == 429:
            return ProviderErrorType.RATE_LIMIT_429
        if exc.status_code in (504, 408):
            return ProviderErrorType.TIMEOUT
        if exc.status_code == 401 or exc.status_code == 403:
            return ProviderErrorType.AUTH_ERROR
        if exc.status_code >= 500:
            return ProviderErrorType.SERVER_ERROR_5XX

    err_str = str(exc).lower()

    if any(k in err_str for k in ("timeout", "timed out", "deadline", "timeouterror")):
        return ProviderErrorType.TIMEOUT
    if any(k in err_str for k in ("429", "rate_limit", "rate limit", "quota", "resource_exhausted")):
        return ProviderErrorType.RATE_LIMIT_429
    if any(k in err_str for k in ("401", "403", "unauthorized", "invalid_api_key", "api_key", "api key", "authentication", "forbidden")):
        return ProviderErrorType.AUTH_ERROR
    if any(k in err_str for k in ("content_filter", "safety", "harmful", "blocked", "safety_rating", "flagged")):
        return ProviderErrorType.CONTENT_FILTER
    if any(k in err_str for k in ("networkerror", "connection error", "connection refused", "connecterror")):
        return ProviderErrorType.NETWORK_ERROR
    if any(k in err_str for k in ("500", "502", "503", "504", "server error", "internal server error", "bad gateway")):
        return ProviderErrorType.SERVER_ERROR_5XX
    if isinstance(exc, json.JSONDecodeError) or "json" in err_str:
        return ProviderErrorType.MALFORMED_JSON

    return ProviderErrorType.UNKNOWN


def is_transient_error(error_type: ProviderErrorType) -> bool:
    """Returns True if the error is considered transient and safe for a bounded retry."""
    return error_type in (
        ProviderErrorType.TIMEOUT,
        ProviderErrorType.RATE_LIMIT_429,
        ProviderErrorType.SERVER_ERROR_5XX,
        ProviderErrorType.NETWORK_ERROR,
    )


def _strip_markdown_code_fences(text: str) -> str:
    """Removes outer markdown code fences (e.g. ```json ... ``` or ``` ... ```)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Drop first line if it's a fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # Drop last line if it's a fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_outermost_json(text: str) -> str:
    """Extracts text bounded by outermost { ... } or [ ... ]."""
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")

    # Check if object is more prominent
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        if first_bracket == -1 or first_brace < first_bracket:
            return text[first_brace : last_brace + 1]
    
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return text[first_bracket : last_bracket + 1]

    return text


def _remove_trailing_commas(json_str: str) -> str:
    """Safely removes trailing commas before closing braces/brackets in JSON."""
    # Matches a comma followed by whitespace and a closing brace or bracket
    return re.sub(r",\s*([\]\}])", r"\1", json_str)


def _normalize_control_characters(text: str) -> str:
    """
    Normalizes unescaped ASCII control characters in strings (0x00 to 0x1F) except standard whitespace.
    """
    # Replace non-printable ASCII control characters except \t, \n, \r
    def clean_char(char: str) -> str:
        code = ord(char)
        if code < 32 and char not in ("\t", "\n", "\r"):
            return ""
        return char

    return "".join(clean_char(c) for c in text)


def repair_and_parse_json(text: str) -> Dict[str, Any]:
    """
    Deterministically cleans, repairs bounded formatting anomalies, and parses JSON output from AI providers.
    
    Allowed transformations:
    - Markdown code-fence removal
    - Safe extraction of outermost JSON object/array
    - Control-character normalization
    - Safe trailing-comma removal
    - Standard JSON parsing

    Strict Invariant:
    - Does NOT invent missing fields or values.
    - Does NOT use LLM or heuristic text generation.
    - If deterministic repair cannot parse valid JSON, raises ProviderResilienceError with MALFORMED_JSON.
    """
    if not text or not isinstance(text, str) or not text.strip():
        raise ProviderResilienceError(
            error_type=ProviderErrorType.MALFORMED_JSON,
            detail="AI provider returned an empty or non-string response payload.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Fast path: direct JSON parse
    raw_stripped = text.strip()
    try:
        parsed = json.loads(raw_stripped)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # Stage 1: Strip markdown code fences
    cleaned = _strip_markdown_code_fences(raw_stripped)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # Stage 2: Extract outermost JSON object/array bounds
    extracted = _extract_outermost_json(cleaned)
    try:
        parsed = json.loads(extracted)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # Stage 3: Normalize control characters
    ctrl_cleaned = _normalize_control_characters(extracted)
    try:
        parsed = json.loads(ctrl_cleaned)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # Stage 4: Remove trailing commas
    no_trailing = _remove_trailing_commas(ctrl_cleaned)
    try:
        parsed = json.loads(no_trailing)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        pass

    # If all deterministic bounded stages fail, raise MALFORMED_JSON
    raise ProviderResilienceError(
        error_type=ProviderErrorType.MALFORMED_JSON,
        detail="AI provider returned an invalid JSON response format.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
