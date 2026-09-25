"""
Centralized Structured JSON Logging & Request Correlation Module for ResumeIQ.
Phase 6.0 — Milestone 1

Features:
- Standard library JSON logging formatter with ISO-8601 UTC timestamps.
- Context-variable request ID tracking across concurrent async calls.
- Safe secret redaction (JWTs, Bearer tokens, API keys).
- Clean structured schema for cloud log aggregators (GCP Cloud Logging, Datadog, AWS CloudWatch).
"""

import re
import sys
import json
import logging
import contextvars
from datetime import datetime, timezone
from typing import Optional, Any, Dict

# Context variable to hold the active request ID for the current async task
request_id_ctx_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id_ctx_var", default=None
)


def get_request_id() -> Optional[str]:
    """Returns the active request ID from the context variable."""
    return request_id_ctx_var.get()


def set_request_id(req_id: Optional[str]) -> contextvars.Token:
    """Sets the active request ID in the context variable and returns the reset token."""
    return request_id_ctx_var.set(req_id)


def reset_request_id(token: contextvars.Token) -> None:
    """Resets the context variable to its previous state using the token."""
    request_id_ctx_var.reset(token)


# Regex patterns for sensitive data redaction
REDACTION_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE), r'\1="[REDACTED]"'),
    (re.compile(r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+"), "[JWT_REDACTED]"),
]


def redact_sensitive_text(text: str) -> str:
    """Masks authorization tokens, JWTs, and secrets in text strings."""
    if not text:
        return text
    result = str(text)
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class StructuredJsonFormatter(logging.Formatter):
    """
    Emits log records as single-line JSON objects with standardized schema.
    """

    def __init__(self, fmt_keys: Optional[Dict[str, str]] = None):
        super().__init__()
        self.fmt_keys = fmt_keys or {}

    def format(self, record: logging.LogRecord) -> str:
        # Base log object
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }

        # Request ID from context or record extra
        req_id = getattr(record, "request_id", None) or get_request_id()
        if req_id:
            log_obj["request_id"] = str(req_id)

        # Standard extra fields if provided
        for field in (
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "provider",
            "model",
            "attempt",
            "error_type",
            "retry_count",
            "component",
            "reason",
            "error_category",
            "subcollection",
            "limit",
            "window_s",
            "claims_evaluated",
            "claims_accepted",
            "claims_rejected",
            "total_tokens",
        ):
            val = getattr(record, field, None)
            if val is not None:
                log_obj[field] = val

        # Exception formatting
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "UnknownException",
                "message": redact_sensitive_text(str(record.exc_info[1])),
                "stack_trace": redact_sensitive_text(self.formatException(record.exc_info)),
            }

        return json.dumps(log_obj, ensure_ascii=False, default=str)



def setup_logging(log_level: str = "INFO") -> None:
    """
    Initializes root logger with StructuredJsonFormatter on sys.stdout.
    """
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    level_str = log_level.upper() if log_level else "INFO"
    level = getattr(logging, level_str if level_str in valid_levels else "INFO", logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(stream_handler)

    # Suppress verbose third-party loggers
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Returns a namespaced logger instance."""
    return logging.getLogger(name)
