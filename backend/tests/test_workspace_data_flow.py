import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
    AchievementItem,
)
from app.schemas.variant import GenerateResumeRequest
from app.services.resume_service import ResumeService
from app.services.resume_generation_service import ResumeGenerationService
from app.ai.provider import AiAnalyzerProvider


class MockTestProvider(AiAnalyzerProvider):
    name = "MockTestProvider"
    model_name = "mock-test-model"

    def __init__(self):
        self.last_user_prompt = ""
        self.last_system_instruction = ""
        self.last_schema_hint = ""

    async def analyze_fit(self, resume_text, job_description, score_weighting=None):
        return {}

    async def generate_json(self, system_instruction, user_prompt, schema_hint):
        self.last_system_instruction = system_instruction
        self.last_user_prompt = user_prompt
        self.last_schema_hint = schema_hint
        return {
            "summary": "Tailored summary for target role.",
            "experienceRewrites": [],
            "projectRewrites": [],
        }


@pytest.mark.asyncio
async def test_all_workspace_data_reaches_ai_generation(monkeypatch):
    """
    Verifies that all 7 workspace data sources:
    1. Profile (PROFILE_TEST_VALUE)
    2. Experience (EXPERIENCE_TEST_VALUE)
    3. Projects (PROJECT_TEST_VALUE)
    4. Skills (SKILL_TEST_VALUE)
    5. Education (EDUCATION_TEST_VALUE)
    6. Certifications (CERTIFICATE_TEST_VALUE)
    7. Achievements (ACHIEVEMENT_TEST_VALUE)
    reach ResumeGenerationService and are included in the AI prompt context.
    """
    user = AuthenticatedUser(uid="test_user_flow_123", email="user@example.com", token="fake_token")

    synthetic_evidence = CandidateEvidence(
        headline="PROFILE_TEST_VALUE Senior Architect",
        summary="PROFILE_TEST_VALUE Experienced engineer with deep technical domain skills.",
        experience=[
            ExperienceItem(
                id="exp_0",
                role="EXPERIENCE_TEST_VALUE Lead Engineer",
                company="TechCorp Inc",
                start_date="2020",
                end_date="Present",
                bullets=["EXPERIENCE_TEST_VALUE Engineered high-throughput distributed systems in Python."],
                technologies=["Python", "FastAPI"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="PROJECT_TEST_VALUE Microservice Framework",
                description="PROJECT_TEST_VALUE High-performance API gateway",
                highlights=["PROJECT_TEST_VALUE Developed event-driven streaming architecture."],
                tech_stack=["Kafka", "Python"],
            )
        ],
        skills=[
            SkillItem(name="SKILL_TEST_VALUE_Python", category="Languages", proficiency="Expert"),
            SkillItem(name="SKILL_TEST_VALUE_FastAPI", category="Frameworks & Libraries", proficiency="Expert"),
        ],
        education=[
            EducationItem(
                degree="EDUCATION_TEST_VALUE B.S. in Computer Science",
                institution="EDUCATION_TEST_VALUE MIT",
                field_of_study="Computer Science",
            )
        ],
        certifications=[
            CertificationItem(
                title="CERTIFICATE_TEST_VALUE AWS Certified Solutions Architect",
                issuer="CERTIFICATE_TEST_VALUE Amazon Web Services",
            )
        ],
        achievements=[
            AchievementItem(
                id="ach_0",
                title="ACHIEVEMENT_TEST_VALUE Global Hackathon Winner",
                issuer="ACHIEVEMENT_TEST_VALUE Global Tech Summit",
                description="ACHIEVEMENT_TEST_VALUE Awarded 1st place among 500 engineering teams.",
            )
        ],
    )

    monkeypatch.setattr(
        ResumeService,
        "get_candidate_resume_data",
        AsyncMock(return_value=synthetic_evidence),
    )
    monkeypatch.setattr(
        ResumeService,
        "save_resume_snapshot",
        AsyncMock(return_value=True),
    )

    mock_provider = MockTestProvider()
    req = GenerateResumeRequest(
        target_role="Senior Python Engineer",
        target_company="InnovativeTech",
        job_description="Looking for senior Python and distributed systems engineers.",
    )

    variant = await ResumeGenerationService.generate_role_targeted_resume(
        user=user,
        req=req,
        provider=mock_provider,
    )

    # 1. Verify that all 7 synthetic values reach the AI prompt context
    prompt = mock_provider.last_user_prompt
    assert "PROFILE_TEST_VALUE" in prompt, "Profile data must reach AI prompt"
    assert "EXPERIENCE_TEST_VALUE" in prompt, "Experience data must reach AI prompt"
    assert "PROJECT_TEST_VALUE" in prompt, "Project data must reach AI prompt"
    assert "SKILL_TEST_VALUE_Python" in prompt, "Skill data must reach AI prompt"
    assert "EDUCATION_TEST_VALUE" in prompt, "Education data must reach AI prompt"
    assert "CERTIFICATE_TEST_VALUE" in prompt, "Certificate data must reach AI prompt"
    assert "ACHIEVEMENT_TEST_VALUE" in prompt, "Achievement data must reach AI prompt"

    # 2. Verify that all 7 data sources are preserved in the variant snapshot
    assert variant.snapshot is not None
    assert "PROFILE_TEST_VALUE" in (variant.snapshot.headline or "")
    assert any("EXPERIENCE_TEST_VALUE" in e.role for e in variant.snapshot.experience)
    assert any("PROJECT_TEST_VALUE" in p.title for p in variant.snapshot.projects)
    assert any("SKILL_TEST_VALUE" in s.name for s in variant.snapshot.skills)
    assert any("EDUCATION_TEST_VALUE" in ed.degree for ed in variant.snapshot.education)
    assert any("CERTIFICATE_TEST_VALUE" in c.title for c in variant.snapshot.certifications)
    assert any("ACHIEVEMENT_TEST_VALUE" in a.title for a in variant.snapshot.achievements)

    # 3. Verify variant is isolated and has expected target role metadata
    assert variant.target_role == "Senior Python Engineer"
    assert variant.target_company == "InnovativeTech"
    assert variant.version == 1
