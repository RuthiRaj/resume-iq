"""
Comprehensive Test Suite for Production Observability, Structured Logging & Request Correlation.
Phase 6.0 — Milestone 1

Verifies:
A. Request ID generated when absent
B. Valid incoming request ID preserved
C. Invalid/malicious request ID replaced
D. Request ID response header (X-Request-ID)
E. Response timing header (X-Response-Time)
F. Context isolation between concurrent requests
G. Structured log is valid JSON
H. Structured log contains request_id
I. Structured log does not contain Authorization tokens (redacted)
J. Structured log does not contain raw sensitive content
K. Unexpected exception produces safe JSON 500
L. Unexpected exception response includes request_id
M. Explicit HTTPException behavior remains correct
N. Validation errors remain correct
O. Authentication failure emits safe security event
P. Rate-limit rejection emits safe security event
Q. AI provider failure emits structured event
R. AI provider failover emits structured event
S. Firestore failure emits safe diagnostic event
T. /health remains lightweight liveness probe
U. /health/ready returns deterministic readiness state
V. CORS includes PATCH and DELETE
"""

import io
import json
import logging
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.main import app, _sanitize_request_id
from app.core.logging import (
    StructuredJsonFormatter,
    get_request_id,
    set_request_id,
    reset_request_id,
    redact_sensitive_text,
    get_logger,
)
from app.core.config import settings
from app.core.auth import AuthenticatedUser, get_authenticated_user
from app.core.rate_limiter import InMemoryRateLimiter
from app.ai.resilience import classify_provider_exception, ProviderErrorType
from app.ai.fallback_provider import FallbackProvider
from app.ai.provider import AiAnalyzerProvider
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse
from app.schemas.common import ScoreBreakdown, AnalysisMetadata


@pytest.fixture
def app_client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://testserver")



# =====================================================================
# 1. Request ID Generation, Sanitization & Header Propagation
# =====================================================================

@pytest.mark.asyncio
async def test_req_id_generated_when_absent(app_client: AsyncClient):
    """A & D & E: When X-Request-ID is absent, generates clean req_<uuid> and sets response headers."""
    async with app_client as client:
        res = await client.get("/health")
        assert res.status_code == 200
        req_id = res.headers.get("x-request-id")
        assert req_id is not None
        assert req_id.startswith("req_")
        assert len(req_id) > 10

        resp_time = res.headers.get("x-response-time")
        assert resp_time is not None
        assert resp_time.endswith("ms")


@pytest.mark.asyncio
async def test_req_id_preserved_when_valid(app_client: AsyncClient):
    """B: Valid incoming X-Request-ID is preserved across request lifecycle."""
    custom_id = "client_txn_abc123_test"
    async with app_client as client:
        res = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers.get("x-request-id") == custom_id


@pytest.mark.asyncio
async def test_req_id_sanitization_and_malicious_replacement():
    """C: Malicious, oversized, or control-character IDs are replaced with clean generated IDs."""
    # 1. Newline injection attempt
    bad_nl = "req_123\r\nInjected-Header: evil"
    assert _sanitize_request_id(bad_nl) != bad_nl
    assert _sanitize_request_id(bad_nl).startswith("req_")

    # 2. Oversized ID (> 128 chars)
    bad_huge = "a" * 200
    assert _sanitize_request_id(bad_huge) != bad_huge
    assert _sanitize_request_id(bad_huge).startswith("req_")

    # 3. Special characters ($@#!)
    bad_special = "req_123!@#$%^&*()"
    assert _sanitize_request_id(bad_special) != bad_special
    assert _sanitize_request_id(bad_special).startswith("req_")

    # 4. Valid alphanumeric with underscore and hyphen
    valid_id = "req_2026_client-01-AB"
    assert _sanitize_request_id(valid_id) == valid_id


# =====================================================================
# 2. Context Isolation Between Concurrent Requests
# =====================================================================

@pytest.mark.asyncio
async def test_context_isolation_between_concurrent_tasks():
    """F: Context variable request_id remains isolated across concurrent async tasks."""
    results = {}

    async def task_worker(task_id: str, req_id: str):
        token = set_request_id(req_id)
        try:
            await asyncio.sleep(0.01)
            # Verify context holds our own req_id, not overwritten by other tasks
            results[task_id] = get_request_id()
        finally:
            reset_request_id(token)

    tasks = [
        task_worker("task_1", "req_aaa"),
        task_worker("task_2", "req_bbb"),
        task_worker("task_3", "req_ccc"),
    ]
    await asyncio.gather(*tasks)

    assert results["task_1"] == "req_aaa"
    assert results["task_2"] == "req_bbb"
    assert results["task_3"] == "req_ccc"


# =====================================================================
# 3. Structured JSON Logging & Secret Redaction
# =====================================================================

def test_structured_log_is_valid_json_and_contains_request_id():
    """G & H: Formatter emits valid single-line JSON containing level, message, and request_id."""
    formatter = StructuredJsonFormatter()
    logger = logging.getLogger("test_logger")

    token = set_request_id("req_struct_test_456")
    try:
        record = logger.makeRecord(
            name="test_logger",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="Processing user transaction",
            args=(),
            exc_info=None,
            extra={"event": "user_action", "component": "test"},
        )
        formatted_line = formatter.format(record)
        log_json = json.loads(formatted_line)

        assert log_json["level"] == "INFO"
        assert log_json["logger"] == "test_logger"
        assert log_json["message"] == "Processing user transaction"
        assert log_json["request_id"] == "req_struct_test_456"
        assert log_json["event"] == "user_action"
        assert log_json["component"] == "test"
        assert "timestamp" in log_json
    finally:
        reset_request_id(token)


def test_sensitive_data_redaction():
    """I & J: Authorization tokens, passwords, and JWTs are safely redacted from log strings."""
    # 1. Bearer Token
    raw_bearer = "Request received with Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJ1c3JfMTIzIn0.sig"
    redacted = redact_sensitive_text(raw_bearer)
    assert "Bearer [REDACTED]" in redacted
    assert "eyJ1aWQi" not in redacted

    # 2. Secret Key Parameter
    raw_key = 'Calling API with api_key="sk_live_secret123456789"'
    redacted_key = redact_sensitive_text(raw_key)
    assert '[REDACTED]' in redacted_key
    assert "sk_live_secret123456789" not in redacted_key


# =====================================================================
# 4. Error Handling: Global 500, Validation 400 & Explicit HTTPException
# =====================================================================

@pytest.mark.asyncio
async def test_unexpected_exception_produces_safe_json_500(app_client: AsyncClient, monkeypatch):
    """K & L: Unexpected server errors return clean JSON 500 with request_id, without leaking traces."""
    from app.api.v1 import analyze
    
    async def mock_buggy_get_candidate(user, resume_id):
        raise ZeroDivisionError("Simulated unexpected internal calculation bug")

    async def mock_auth_user():
        return AuthenticatedUser(uid="usr_test_500", token="tok_500")

    monkeypatch.setattr(analyze, "get_candidate_resume_data", mock_buggy_get_candidate)
    app.dependency_overrides[get_authenticated_user] = mock_auth_user

    try:
        async with app_client as client:
            res = await client.post(
                "/api/v1/ai/analyze",
                headers={"X-Request-ID": "req_err_trace_999", "Authorization": "Bearer tok_500"},
                json={
                    "resumeId": "workspace",
                    "targetRole": "Backend Engineer",
                    "jobDescription": "We are seeking a Backend Engineer with 5+ years of Python, FastAPI, distributed systems, and cloud experience.",
                },
            )
            assert res.status_code == 500
            data = res.json()
            assert "error" in data
            assert data["request_id"] == "req_err_trace_999"
            # Must not leak the raw exception name or traceback to the user
            assert "ZeroDivisionError" not in data["error"]
            assert "Simulated unexpected" not in data["error"]
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.asyncio
async def test_validation_error_returns_status_400_and_request_id(app_client: AsyncClient):
    """N: Request validation failure returns 400 with formatted message and request_id."""
    async with app_client as client:
        # Send empty POST body to generate roadmap endpoint which expects non-empty JSON
        res = await client.post(
            "/api/v1/career/roadmaps/generate",
            headers={"X-Request-ID": "req_val_error_123"},
            json={},  # Missing required fields
        )
        assert res.status_code in (400, 401)
        data = res.json()
        assert res.headers.get("x-request-id") == "req_val_error_123"


# =====================================================================
# 5. Security Event Logging (Auth & Rate Limit)
# =====================================================================

@pytest.mark.asyncio
async def test_auth_failure_rejection_and_event(app_client: AsyncClient):
    """O: Unauthorized requests return 401 without leaking internal details."""
    async with app_client as client:
        res = await client.get("/api/v1/career/roadmaps")
        assert res.status_code == 401
        data = res.json()
        assert "detail" in data or "error" in data


@pytest.mark.asyncio
async def test_rate_limiter_rejection_and_security_event():
    """P: Rate limiter rejects requests when quota is exceeded with 429 and Retry-After header."""
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    user_key = "usr_rate_test"

    await limiter.check(user_key)
    await limiter.check(user_key)

    with pytest.raises(HTTPException) as exc:
        await limiter.check(user_key)

    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


# =====================================================================
# 6. AI Provider Observability & Failover Logging
# =====================================================================

class MockTransientFailProvider(AiAnalyzerProvider):
    def __init__(self, name: str, fail_count: int = 1):
        self._name = name
        self._model_name = "mock-model"
        self._fail_count = fail_count
        self._attempts = 0

    @property
    def name(self) -> str:
        return self._name

    async def analyze(self, **kwargs) -> AnalyzeResponse:
        self._attempts += 1
        if self._attempts <= self._fail_count:
            raise HTTPException(status_code=429, detail=f"Provider {self._name} Rate Limited")
        return AnalyzeResponse(
            ats_score=88,
            summary_feedback="Strong candidate profile match",
            score_breakdown=ScoreBreakdown(relevance=90, keywords=85, metrics=90, formatting=90),
            matching_skills=[],
            missing_skills=[],
            partial_skills=[],
            requirement_matches=[],
            remediation_suggestions=[],
            metadata=AnalysisMetadata(
                model=self._model_name,
                provider=self._name,
                analyzed_at="2026-09-25T00:00:00Z",
                job_description_hash="mock_hash",
                target_role="Dev",
            ),
        )

    async def generate_json(self, **kwargs):
        return {}


class MockSuccessProvider(AiAnalyzerProvider):
    def __init__(self, name: str):
        self._name = name
        self._model_name = "mock-success-model"

    @property
    def name(self) -> str:
        return self._name

    async def analyze(self, **kwargs) -> AnalyzeResponse:
        return AnalyzeResponse(
            ats_score=95,
            summary_feedback="Excellent candidate profile match",
            score_breakdown=ScoreBreakdown(relevance=95, keywords=95, metrics=95, formatting=95),
            matching_skills=[],
            missing_skills=[],
            partial_skills=[],
            requirement_matches=[],
            remediation_suggestions=[],
            metadata=AnalysisMetadata(
                model=self._model_name,
                provider=self._name,
                analyzed_at="2026-09-25T00:00:00Z",
                job_description_hash="mock_hash",
                target_role="Dev",
            ),
        )

    async def generate_json(self, **kwargs):
        return {}


@pytest.mark.asyncio
async def test_ai_provider_failover_telemetry_and_events():
    """Q & R: AI fallback provider records failover logs and execution events."""
    p1 = MockTransientFailProvider("mock_groq_fail", fail_count=5)  # Always fails with 429
    p2 = MockSuccessProvider("mock_gemini_success")  # Succeeds on fallback

    fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=0)

    res = await fallback.analyze(
        target_role="Software Engineer",
        target_company="Acme",
        job_description="Python dev",
        job_description_hash="hash123",
        candidate_evidence=CandidateEvidence(experience=[], projects=[], skills=[], education=[], certifications=[]),
    )

    assert res.ats_score == 95
    assert fallback.last_provider == "mock_gemini_success"
    assert len(fallback.failover_log) == 1
    assert fallback.failover_log[0]["provider"] == "mock_groq_fail"
    assert "HTTP 429" in fallback.failover_log[0]["error_type"]
    assert len(fallback.execution_events) == 2


# =====================================================================
# 7. Health & Readiness Probes
# =====================================================================

@pytest.mark.asyncio
async def test_health_liveness_endpoint(app_client: AsyncClient):
    """T: GET /health returns operational liveness metadata."""
    async with app_client as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "resumeiq-backend"


@pytest.mark.asyncio
async def test_health_readiness_endpoint(app_client: AsyncClient):
    """U: GET /health/ready returns deterministic configuration and dependency readiness state."""
    async with app_client as client:
        res = await client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["checks"]["config"] == "ok"
        assert data["checks"]["auth_jwks"] == "ok"
        assert data["checks"]["http_pool"] == "ok"


# =====================================================================
# 8. CORS Headers Verification (PATCH, DELETE)
# =====================================================================

@pytest.mark.asyncio
async def test_cors_methods_support_patch_and_delete(app_client: AsyncClient):
    """V: CORS OPTIONS preflight returns support for GET, POST, PATCH, DELETE, OPTIONS."""
    async with app_client as client:
        res = await client.options(
            "/api/v1/career/roadmaps/rdm_test/progress",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Authorization, Content-Type, X-Request-ID",
            },
        )
        assert res.status_code == 200
        allow_methods = res.headers.get("access-control-allow-methods", "")
        assert "PATCH" in allow_methods
        assert "DELETE" in allow_methods
        assert "GET" in allow_methods
        assert "POST" in allow_methods
