import pytest
from pydantic import ValidationError
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.common import ScoreBreakdown, SkillMatchItem, AnalysisMetadata
from app.core.security import hash_job_description


def test_analyze_request_valid():
    req = AnalyzeRequest(
        resumeId="res_123",
        targetRole="Staff Backend Engineer",
        targetCompany="Stripe",
        jobDescription="We are looking for a Staff Backend Engineer with strong distributed systems and Go experience.",
    )
    assert req.resume_id == "res_123"
    assert req.target_role == "Staff Backend Engineer"


def test_analyze_request_short_jd_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            resumeId="res_123",
            targetRole="Staff Backend Engineer",
            jobDescription="Too short",
        )


def test_job_description_hash():
    h1 = hash_job_description("Sample Job Description Requirements")
    h2 = hash_job_description("  Sample Job Description Requirements  ")
    assert len(h1) == 64
    assert h1 == h2
