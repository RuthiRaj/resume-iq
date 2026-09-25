"""
Comprehensive Test Suite for Production Containerization & Runtime Health.
Phase 6.0 — Milestone 2

Tests:
1. Backend Dockerfile structure & multi-stage directives
2. Backend runtime base image (Python 3.11-slim)
3. Backend non-root user declaration (appuser / UID 10001)
4. Backend port exposition (8000)
5. Backend healthcheck probe (/health)
6. Frontend Dockerfile structure & multi-stage directives
7. Frontend runtime base image (Node 20-alpine)
8. Frontend non-root user declaration (nextjs / UID 10001)
9. Frontend port exposition (3000)
10. Next.js standalone output configuration
11. Dockerignore exclusions (secrets, .git, caches, node_modules, .venv)
12. Docker Compose topology (backend, frontend, resumeiq-network)
13. Docker Compose networking (BACKEND_API_URL=http://backend:8000)
14. Docker Compose security parameters (non-root, no-new-privileges, cap_drop, read_only)
15. Docker Compose secret hygiene (no hardcoded keys)
16. Production startup preflight validation (rejects invalid production configuration)
17. Production startup preflight validation (passes on valid production configuration)
18. Development and test environment defaults preserved
19. Lightweight /health liveness probe verification
20. Deterministic /health/ready readiness probe verification
"""

import os
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import Settings


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


# =====================================================================
# 1. Backend Dockerfile & Container Structure Tests
# =====================================================================

def test_backend_dockerfile_exists():
    dockerfile = BACKEND_DIR / "Dockerfile"
    assert dockerfile.exists(), "backend/Dockerfile must exist"
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM python:3.11-slim AS builder" in content
    assert "FROM python:3.11-slim AS runtime" in content


def test_backend_dockerfile_non_root_user():
    content = (BACKEND_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "useradd -u 10001" in content
    assert "appuser" in content
    assert "USER appuser" in content


def test_backend_dockerfile_port_and_healthcheck():
    content = (BACKEND_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "EXPOSE 8000" in content
    assert "HEALTHCHECK" in content
    assert "/health" in content
    assert "uvicorn" in content
    assert "app.main:app" in content


# =====================================================================
# 2. Frontend Dockerfile & Standalone Configuration Tests
# =====================================================================

def test_frontend_dockerfile_exists():
    dockerfile = FRONTEND_DIR / "Dockerfile"
    assert dockerfile.exists(), "frontend/Dockerfile must exist"
    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM node:20-alpine AS deps" in content
    assert "FROM node:20-alpine AS builder" in content
    assert "FROM node:20-alpine AS runner" in content


def test_frontend_dockerfile_non_root_user():
    content = (FRONTEND_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "adduser --system --uid 10001 nextjs" in content
    assert "USER nextjs" in content
    assert "EXPOSE 3000" in content
    assert "server.js" in content


def test_frontend_next_config_standalone():
    next_config = FRONTEND_DIR / "next.config.ts"
    assert next_config.exists(), "frontend/next.config.ts must exist"
    content = next_config.read_text(encoding="utf-8")
    assert 'output: "standalone"' in content or "output: 'standalone'" in content


# =====================================================================
# 3. Dockerignore & Secret Hygiene Tests
# =====================================================================

def test_dockerignore_files_exist_and_exclude_secrets():
    root_dockerignore = REPO_ROOT / ".dockerignore"
    backend_dockerignore = BACKEND_DIR / ".dockerignore"
    frontend_dockerignore = FRONTEND_DIR / ".dockerignore"

    assert root_dockerignore.exists(), ".dockerignore must exist in repository root"
    assert backend_dockerignore.exists(), "backend/.dockerignore must exist"
    assert frontend_dockerignore.exists(), "frontend/.dockerignore must exist"

    root_content = root_dockerignore.read_text(encoding="utf-8")
    for pattern in [".git", ".env", ".env.*", "node_modules", ".venv", "__pycache__", "*.pem", "*.key"]:
        assert pattern in root_content, f".dockerignore must exclude {pattern}"

    backend_content = backend_dockerignore.read_text(encoding="utf-8")
    assert ".env" in backend_content
    assert ".venv" in backend_content

    frontend_content = frontend_dockerignore.read_text(encoding="utf-8")
    assert ".env" in frontend_content
    assert "node_modules" in frontend_content


# =====================================================================
# 4. Docker Compose Topology & Configuration Tests
# =====================================================================

def test_docker_compose_exists_and_declares_services():
    compose_file = REPO_ROOT / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml must exist"
    content = compose_file.read_text(encoding="utf-8")

    assert "backend:" in content
    assert "frontend:" in content
    assert "resumeiq-network:" in content
    assert "8000:8000" in content
    assert "3000:3000" in content
    assert "BACKEND_API_URL=http://backend:8000" in content
    assert "no-new-privileges:true" in content
    assert "cap_drop:" in content
    assert "read_only: true" in content
    assert "/tmp:rw,noexec,nosuid,size=64m" in content


def test_docker_compose_contains_no_baked_secrets():
    content = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "gsk_" not in content
    assert "AIzaSy" not in content
    assert "nvapi-" not in content
    assert "sk_live_" not in content


def test_docker_compose_override_example_exists():
    override_file = REPO_ROOT / "docker-compose.override.yml.example"
    assert override_file.exists(), "docker-compose.override.yml.example must exist"


# =====================================================================
# 5. Production Startup Preflight Validation Tests
# =====================================================================

def test_preflight_allows_development_and_test_defaults():
    dev_settings = Settings(ENVIRONMENT="development", GROQ_API_KEY="", GEMINI_API_KEY="")
    # Must not raise in development
    dev_settings.validate_production_preflight()

    test_settings = Settings(ENVIRONMENT="test", GROQ_API_KEY="", GEMINI_API_KEY="")
    # Must not raise in test
    test_settings.validate_production_preflight()


def test_preflight_rejects_missing_firebase_project_in_production():
    with pytest.raises(RuntimeError) as exc_info:
        bad_settings = Settings(
            ENVIRONMENT="production",
            FIREBASE_PROJECT_ID="",
            GROQ_API_KEY="valid_gsk_test_key_12345",
            CORS_ORIGINS=["https://app.resumeiq.com"],
        )
        bad_settings.validate_production_preflight()
    assert "FIREBASE_PROJECT_ID" in str(exc_info.value)


def test_preflight_rejects_missing_ai_key_in_production():
    with pytest.raises(RuntimeError) as exc_info:
        bad_settings = Settings(
            ENVIRONMENT="production",
            FIREBASE_PROJECT_ID="resumeiq-prod",
            AI_PROVIDER_CHAIN="groq,gemini",
            GROQ_API_KEY="",
            GEMINI_API_KEY="",
            NVIDIA_API_KEY="",
            CORS_ORIGINS=["https://app.resumeiq.com"],
        )
        bad_settings.validate_production_preflight()
    assert "At least one AI provider" in str(exc_info.value)


def test_preflight_rejects_wildcard_cors_in_production():
    with pytest.raises(RuntimeError) as exc_info:
        bad_settings = Settings(
            ENVIRONMENT="production",
            FIREBASE_PROJECT_ID="resumeiq-prod",
            AI_PROVIDER_CHAIN="groq",
            GROQ_API_KEY="valid_gsk_test_key_12345",
            CORS_ORIGINS=["*"],
        )
        bad_settings.validate_production_preflight()
    assert "Wildcard CORS_ORIGINS" in str(exc_info.value)


def test_preflight_passes_valid_production_configuration():
    valid_prod_settings = Settings(
        ENVIRONMENT="production",
        FIREBASE_PROJECT_ID="resumeiq-prod-12345",
        AI_PROVIDER_CHAIN="groq,gemini",
        GROQ_API_KEY="gsk_valid_production_secret_key_12345",
        CORS_ORIGINS=["https://app.resumeiq.com", "https://resumeiq.com"],
    )
    # Must not raise
    valid_prod_settings.validate_production_preflight()


# =====================================================================
# 6. Health & Readiness Runtime Semantics Tests
# =====================================================================

@pytest.mark.asyncio
async def test_health_liveness_runtime_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "resumeiq-backend"


@pytest.mark.asyncio
async def test_health_readiness_runtime_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["config"] == "ok"
        assert data["checks"]["auth_jwks"] == "ok"
        assert data["checks"]["http_pool"] == "ok"
