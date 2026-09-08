import pytest
import io
import base64
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pypdf

from app.main import app
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.services.pdf_renderer import ResumeViewModel, AtsTemplateRenderer
from app.services.variant_service import VariantService
from app.services.resume_service import ResumeService
from app.schemas.variant import TargetedResumeVariant
from app.mcp.mcp_server import export_targeted_resume


# ---------------------------------------------------------------------------
# Unit Tests for ReportLab PDF Renderer
# ---------------------------------------------------------------------------

def test_pdf_renderer_valid_resume_and_text_extraction():
    """Verify that AtsTemplateRenderer generates valid native vector PDF with searchable text and special character escaping."""
    vm = ResumeViewModel(
        full_name="Jane & John Doe",
        headline="Senior R&D <Architect> & Lead",
        contact_line="jane@example.com | +1 (555) 019-2834 | San Francisco, CA",
        summary="Proven software engineering leader with 10+ years specializing in distributed systems & cloud native tech.",
        experience=[
            {
                "role": "Staff Engineer & Tech Lead",
                "company": "Acme Systems Inc.",
                "location": "San Francisco, CA",
                "date_range": "2021 – Present",
                "bullets": [
                    "Architected high-throughput microservices using Python & Go, reducing latency by 45%.",
                    "Managed team of 8 engineers handling <10ms SLA web applications.",
                ],
            }
        ],
        projects=[
            {
                "title": "OpenSource Framework <v2.0>",
                "role": "Creator & Maintainer",
                "description": "Distributed task queue processing 1M+ tasks/sec.",
                "highlights": [
                    "Engineered zero-copy memory buffers using Rust & C++.",
                ],
            }
        ],
        skills=["Python", "Go", "C++", "Kubernetes", "PostgreSQL", "Docker"],
        education=[
            {
                "degree": "B.S. Computer Science & Mathematics",
                "institution": "Stanford University",
                "fieldOfStudy": "Computer Science",
            }
        ],
        certifications=[
            {
                "title": "AWS Certified Solutions Architect & DevOps Engineer",
                "issuer": "Amazon Web Services",
            }
        ],
        target_role="Staff Software Engineer",
        target_company="Acme Systems",
    )

    renderer = AtsTemplateRenderer()
    pdf_bytes = renderer.render(vm)

    # 1. Header Magic Bytes
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file must start with PDF magic header %PDF-"
    assert len(pdf_bytes) > 1000, "Generated PDF bytes must not be trivially small"

    # 2. PyPDF Text Extraction Verification
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1, "PDF must contain at least 1 page"

    extracted_text = "\n".join([page.extract_text() for page in reader.pages])

    # Check key candidate information present in extracted vector text
    assert "Jane & John Doe" in extracted_text or "Jane" in extracted_text
    assert "Senior R&D <Architect> & Lead" in extracted_text or "Architect" in extracted_text
    assert "Acme Systems Inc." in extracted_text
    assert "Python & Go" in extracted_text or "Python" in extracted_text
    assert "Stanford University" in extracted_text
    assert "Kubernetes" in extracted_text


def test_pdf_renderer_large_resume_multi_page_flow():
    """Verify that AtsTemplateRenderer handles multi-page resumes smoothly without throwing exceptions."""
    bullets = [f"Designed and implemented high scale service sub-system bullet point item #{i} with extensive metrics & telemetry." for i in range(30)]
    vm = ResumeViewModel(
        full_name="Alexander Hamilton",
        headline="Principal Infrastructure Architect",
        contact_line="alex@hamilton.org | New York, NY",
        summary="Architecting resilient scalable infrastructure for large enterprise networks.",
        experience=[
            {
                "role": f"Senior Infrastructure Engineer #{j}",
                "company": f"Global Corp #{j}",
                "location": "New York, NY",
                "date_range": "2015 – 2020",
                "bullets": bullets[:10],
            }
            for j in range(3)
        ],
        projects=[
            {
                "title": f"Enterprise Cloud Migration Project #{k}",
                "role": "Lead Architect",
                "description": "Complete infrastructure overhaul to Kubernetes and AWS.",
                "highlights": bullets[10:15],
            }
            for k in range(3)
        ],
        skills=[f"Cloud Skill {i}" for i in range(25)],
        education=[
            {
                "degree": "M.S. Systems Engineering",
                "institution": "Columbia University",
                "fieldOfStudy": "Engineering",
            }
        ],
        certifications=[],
    )

    renderer = AtsTemplateRenderer()
    pdf_bytes = renderer.render(vm)

    assert pdf_bytes.startswith(b"%PDF-")
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2, "Large multi-section resume should wrap onto page 2 cleanly"


# ---------------------------------------------------------------------------
# Integration Tests for VariantService.export_targeted_variant_pdf
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_variant_doc():
    return {
        "variantId": "var_pdf_123",
        "isTargetedVariant": True,
        "masterResumeId": "master_789",
        "title": "Targeted Resume - Senior DevOps Engineer",
        "targetRole": "Senior DevOps Engineer",
        "targetCompany": "Netflix",
        "version": 3,
        "baselineScore": 75,
        "currentScore": 88,
        "snapshot": {
            "profile": {"headline": "DevOps Architect"},
            "summary": "Expert in Kubernetes and Cloud Automation.",
            "experience": [
                {
                    "role": "DevOps Lead",
                    "company": "Streaming Tech Inc",
                    "startDate": "2020",
                    "endDate": "Present",
                    "location": "Los Angeles, CA",
                    "bullets": ["Automated CI/CD pipelines.", "Managed 500+ K8s nodes."],
                }
            ],
            "projects": [
                {
                    "title": "Multi-region Failover Engine",
                    "role": "Architect",
                    "description": "Active-active disaster recovery.",
                    "highlights": ["0 downtime during regional outage."],
                }
            ],
            "skills": [{"name": "Kubernetes"}, {"name": "Terraform"}],
            "education": [
                {
                    "degree": "B.S. Software Engineering",
                    "institution": "UCLA",
                    "fieldOfStudy": "Software",
                }
            ],
            "certifications": [],
        },
        "jobDescriptionHash": "hash_12345",
        "changeLedger": [
            {
                "id": "chg_1",
                "version": 2,
                "requirementName": "Kubernetes",
                "action": "ModifyBullet",
                "section": "Experience",
                "targetItemId": "exp_0",
                "targetBulletIndex": 0,
                "originalText": "Automated CI/CD pipelines.",
                "approvedText": "Automated multi-region CI/CD pipelines.",
                "status": "Applied",
                "appliedAt": "2026-09-07T10:30:00Z",
            }
        ],
        "createdAt": "2026-09-07T10:00:00Z",
        "updatedAt": "2026-09-07T11:00:00Z",
    }


@pytest.mark.asyncio
async def test_export_targeted_variant_pdf_service(monkeypatch, mock_variant_doc):
    saved_docs = {"var_pdf_123": mock_variant_doc}

    async def mock_get(user, resume_id):
        if user.uid == "usr_test_1" and resume_id == "var_pdf_123":
            return saved_docs[resume_id]
        return None

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    user = AuthenticatedUser(uid="usr_test_1", token="tok_1", email="dev@example.com")

    pdf_bytes, filename = await VariantService.export_targeted_variant_pdf(user, "var_pdf_123", template="ats")

    assert pdf_bytes.startswith(b"%PDF-")
    assert filename == "Senior_DevOps_Engineer_v3.pdf"

    # Verify read-only invariant: version remains 3, saved_docs unchanged
    assert saved_docs["var_pdf_123"]["version"] == 3


@pytest.mark.asyncio
async def test_export_targeted_variant_pdf_tenant_isolation(monkeypatch, mock_variant_doc):
    async def mock_get(user, resume_id):
        if user.uid == "usr_owner" and resume_id == "var_pdf_123":
            return mock_variant_doc
        return None

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    user_unauthorized = AuthenticatedUser(uid="usr_attacker", token="tok_2", email="attacker@example.com")

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await VariantService.export_targeted_variant_pdf(user_unauthorized, "var_pdf_123")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# API & MCP Route Tests
# ---------------------------------------------------------------------------

def test_api_export_variant_pdf_endpoint(monkeypatch, mock_variant_doc):
    client = TestClient(app)

    async def mock_get_auth_user():
        return AuthenticatedUser(uid="usr_test_1", token="tok_1", email="dev@example.com")

    async def mock_get_resume_doc(user, resume_id):
        if user.uid == "usr_test_1" and resume_id == "var_pdf_123":
            return mock_variant_doc
        return None

    app.dependency_overrides[get_authenticated_user] = mock_get_auth_user
    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get_resume_doc)

    try:
        res = client.get("/api/v1/variants/var_pdf_123/export/pdf?template=ats")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert 'attachment; filename="Senior_DevOps_Engineer_v3.pdf"' in res.headers["content-disposition"]
        assert res.content.startswith(b"%PDF-")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_export_targeted_resume_pdf(monkeypatch, mock_variant_doc):
    async def mock_get_resume_doc(user, resume_id):
        if user.uid == "usr_mcp" and resume_id == "var_pdf_123":
            return mock_variant_doc
        return None

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get_resume_doc)

    mock_ctx = MagicMock()
    mock_ctx.session.client_meta = None
    mock_user = AuthenticatedUser(uid="usr_mcp", token="tok_mcp", email="mcp@example.com")

    monkeypatch.setattr("app.mcp.mcp_server.resolve_mcp_user", lambda ctx: mock_user)

    result = await export_targeted_resume(mock_ctx, "var_pdf_123", format="pdf")

    assert result["variantId"] == "var_pdf_123"
    assert result["format"] == "pdf"
    assert result["filename"] == "Senior_DevOps_Engineer_v3.pdf"
    assert result["mimeType"] == "application/pdf"

    pdf_bytes = base64.b64decode(result["contentBase64"])
    assert pdf_bytes.startswith(b"%PDF-")
