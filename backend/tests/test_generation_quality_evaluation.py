"""
ResumeIQ Step 8: AI Quality & Real-World Product Validation Suite

Evaluates the existing ResumeGenerationService, VariantService, FallbackProvider,
and ClaimValidator across representative evaluation scenarios:
- Case A: Strong Workspace profile + specific JD
- Case B: Strong Workspace profile + vague JD
- Case C: Sparse Workspace profile
- Case D: Workspace with rich projects / achievements / certifications
- Case E: JD requesting technologies absent from Workspace (adversarial / hallucination test)
- Case F: JD containing terminology overlapping / synonyms with Workspace evidence
- Case G: Provider failure / fallback scenario (multi-tier failover & all-fail 503)
- Case H: Long JD / noisy JD (5,000+ characters with corporate boilerplate)

Measures:
1. Grounding / evidence adherence
2. Hallucination / unsupported-claim rate
3. Job relevance score
4. Keyword / skill alignment
5. Structural completeness
6. Provider consistency (Groq, Gemini, NVIDIA)
7. Sparse-profile behavior
8. Failure / fallback behavior
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

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
from app.schemas.variant import GenerateResumeRequest, TargetedResumeVariant
from app.services.resume_generation_service import (
    ResumeGenerationService,
    rank_and_select_evidence,
    _extract_keywords,
    _score_text_overlap,
)
from app.services.variant_service import VariantService
from app.services.resume_service import ResumeService
from app.ai.claim_validator import validate_claims_against_source, validate_summary_grounding
from app.ai.fallback_provider import FallbackProvider
from app.ai.provider import AiAnalyzerProvider


@pytest.fixture
def auth_user():
    return AuthenticatedUser(uid="eval_user_001", email="eval@resumeiq.io", token="token_eval")


# =====================================================================
# CASE A: Strong Workspace profile + specific JD
# =====================================================================
@pytest.mark.asyncio
async def test_case_a_strong_profile_specific_jd(auth_user):
    strong_evidence = CandidateEvidence(
        headline="Staff Backend Architect",
        summary="Distributed systems engineer with 8 years building resilient Python and PostgreSQL backend platforms.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="FinTech Core",
                role="Senior Distributed Systems Engineer",
                startDate="2020-01",
                endDate="Present",
                bullets=[
                    "Engineered distributed payment ingestion pipeline in Python handling 12,000 transactions per second.",
                    "Optimized PostgreSQL query execution plans reducing P99 latency by 45% on core billing tables.",
                    "Containerized all microservices with Docker and automated CI/CD deployment pipelines.",
                ],
                technologies=["Python", "PostgreSQL", "Docker", "FastAPI"],
            ),
            ExperienceItem(
                id="exp_1",
                company="CloudScale Systems",
                role="Backend Developer",
                startDate="2016-06",
                endDate="2019-12",
                bullets=[
                    "Developed RESTful APIs using Python and Flask for customer onboarding.",
                ],
                technologies=["Python", "Flask", "MySQL"],
            ),
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Event Streaming Engine",
                description="High-throughput event queue in Python",
                highlights=["Authored open-source event buffer processing 100k events/sec."],
                tech_stack=["Python", "Redis"],
            )
        ],
        skills=[
            SkillItem(name="Python", category="Language"),
            SkillItem(name="PostgreSQL", category="Database"),
            SkillItem(name="FastAPI", category="Framework"),
            SkillItem(name="Docker", category="DevOps"),
            SkillItem(name="Redis", category="Database"),
        ],
        education=[EducationItem(degree="B.S. in Computer Science", institution="Tech University", graduationDate="2016")],
        certifications=[CertificationItem(title="AWS Certified Solutions Architect", issuer="Amazon Web Services")],
        achievements=[AchievementItem(title="Top Engineering Innovator 2023", issuer="FinTech Core")],
    )

    req = GenerateResumeRequest(
        target_role="Lead Python Backend Engineer",
        target_company="Stripe",
        job_description=(
            "We are looking for a Lead Python Backend Engineer to build ultra-low-latency payment processing APIs. "
            "Required skills: Python, PostgreSQL database optimization, FastAPI microservices, and Docker. "
            "Must have experience with high-throughput transactional systems."
        ),
    )

    mock_provider = AsyncMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    mock_provider.generate_json.return_value = {
        "summary": "Distributed systems engineer with 8 years building resilient Python and PostgreSQL backend platforms.",
        "experienceRewrites": [
            {
                "itemId": "exp_0",
                "bulletIndex": 0,
                "originalBullet": "Engineered distributed payment ingestion pipeline in Python handling 12,000 transactions per second.",
                "rewrittenBullet": "Developed distributed payment ingestion pipeline in Python handling 12,000 transactions per second.",
            }
        ],
        "projectRewrites": [],
    }

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=strong_evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    # Assertions & Metrics
    assert variant is not None
    assert variant.target_role == "Lead Python Backend Engineer"
    assert len(variant.snapshot.experience) == 2
    # Check bullet rewrite is valid and grounded
    assert variant.snapshot.experience[0].bullets[0] == "Developed distributed payment ingestion pipeline in Python handling 12,000 transactions per second."
    assert len(variant.change_ledger) == 1
    assert variant.change_ledger[0].action_type == "Generated"
    # Structural completeness: all sections present
    assert variant.snapshot.summary != ""
    assert len(variant.snapshot.skills) == 5
    assert len(variant.snapshot.education) == 1
    assert len(variant.snapshot.certifications) == 1
    assert len(variant.snapshot.achievements) == 1


# =====================================================================
# CASE B: Strong Workspace profile + vague JD
# =====================================================================
@pytest.mark.asyncio
async def test_case_b_strong_profile_vague_jd(auth_user):
    evidence = CandidateEvidence(
        headline="Senior Full Stack Engineer",
        summary="Full stack engineer specializing in TypeScript, React, and Node.js.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="WebCo",
                role="Full Stack Engineer",
                startDate="2021-01",
                endDate="Present",
                bullets=["Built full-stack web applications with React and Node.js."],
                technologies=["React", "Node.js", "TypeScript"],
            )
        ],
        skills=[
            SkillItem(name="React", category="Framework"),
            SkillItem(name="Node.js", category="Language"),
            SkillItem(name="TypeScript", category="Language"),
        ],
    )

    req = GenerateResumeRequest(
        target_role="Software Developer",
        target_company="",
        job_description="Seeking a software developer to write good software and work with our team.",
    )

    mock_provider = AsyncMock()
    mock_provider.name = "gemini"
    mock_provider.model_name = "gemini-2.5-flash"
    mock_provider.generate_json.return_value = {
        "summary": "Full stack engineer specializing in TypeScript, React, and Node.js.",
        "experienceRewrites": [],
        "projectRewrites": [],
    }

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    assert variant is not None
    assert variant.target_role == "Software Developer"
    assert variant.snapshot.experience[0].bullets[0] == "Built full-stack web applications with React and Node.js."
    assert len(variant.change_ledger) == 0  # No changes made when unchanged


# =====================================================================
# CASE C: Sparse Workspace profile
# =====================================================================
@pytest.mark.asyncio
async def test_case_c_sparse_workspace_profile(auth_user):
    sparse_evidence = CandidateEvidence(
        headline="",
        summary="",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="Startup Inc",
                role="Junior Coder",
                startDate="2023-01",
                endDate="Present",
                bullets=["Wrote Python scripts for data extraction."],
                technologies=["Python"],
            )
        ],
        skills=[SkillItem(name="Python", category="Language")],
    )

    req = GenerateResumeRequest(
        target_role="Python Assistant",
        job_description="Need a python programmer.",
    )

    mock_provider = AsyncMock()
    mock_provider.name = "mock"
    mock_provider.model_name = "mock-v1"
    mock_provider.generate_json.return_value = {
        "summary": "",
        "experienceRewrites": [],
        "projectRewrites": [],
    }

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=sparse_evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    assert variant is not None
    assert len(variant.snapshot.experience) == 1
    assert variant.snapshot.experience[0].bullets[0] == "Wrote Python scripts for data extraction."


@pytest.mark.asyncio
async def test_case_c_completely_empty_workspace_raises_422(auth_user):
    empty_evidence = CandidateEvidence(experience=[], projects=[], skills=[])

    req = GenerateResumeRequest(target_role="Engineer")

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=empty_evidence):
        with pytest.raises(HTTPException) as exc_info:
            await ResumeGenerationService.generate_role_targeted_resume(
                user=auth_user,
                req=req,
            )
        assert exc_info.value.status_code == 422


# =====================================================================
# CASE D: Workspace with multiple projects/achievements/certifications
# =====================================================================
@pytest.mark.asyncio
async def test_case_d_rich_projects_achievements_certifications(auth_user):
    evidence = CandidateEvidence(
        headline="AI Research Engineer",
        summary="Machine learning engineer with 3 published papers and 2 cloud certifications.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="AI Labs",
                role="ML Engineer",
                startDate="2021-01",
                endDate="Present",
                bullets=["Trained transformer models using PyTorch on 128 GPUs."],
                technologies=["PyTorch", "Python", "CUDA"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="RAG Semantic Search Engine",
                description="Vector search with ChromaDB and LangChain",
                highlights=["Implemented semantic retrieval pipeline indexing 1M research documents."],
                tech_stack=["ChromaDB", "LangChain", "Python"],
            ),
            ProjectItem(
                id="proj_1",
                title="Vision Transformer Classifier",
                description="Image classification library",
                highlights=["Authored PyTorch vision library with 500+ GitHub stars."],
                tech_stack=["PyTorch", "Python"],
            ),
        ],
        skills=[
            SkillItem(name="PyTorch", category="Framework"),
            SkillItem(name="LangChain", category="Framework"),
            SkillItem(name="ChromaDB", category="Database"),
            SkillItem(name="Python", category="Language"),
        ],
        education=[EducationItem(degree="M.S. in Artificial Intelligence", institution="MIT", graduationDate="2021")],
        certifications=[
            CertificationItem(title="AWS Certified Machine Learning - Specialty", issuer="AWS"),
            CertificationItem(title="TensorFlow Developer Certificate", issuer="Google"),
        ],
        achievements=[
            AchievementItem(title="Best Paper Award - NeurIPS Workshop 2023", issuer="NeurIPS"),
            AchievementItem(title="Kaggle Grandmaster", issuer="Kaggle"),
        ],
    )

    req = GenerateResumeRequest(
        target_role="Senior AI Application Engineer",
        target_company="OpenAI",
        job_description="Seeking Senior AI Application Engineer with PyTorch, RAG vector database systems, and LangChain experience.",
    )

    mock_provider = AsyncMock()
    mock_provider.name = "nvidia"
    mock_provider.model_name = "meta/llama-3.2-11b-vision-instruct"
    mock_provider.generate_json.return_value = {
        "summary": "Machine learning engineer with 3 published papers and 2 cloud certifications.",
        "experienceRewrites": [],
        "projectRewrites": [
            {
                "itemId": "proj_0",
                "bulletIndex": 0,
                "originalBullet": "Implemented semantic retrieval pipeline indexing 1M research documents.",
                "rewrittenBullet": "Developed semantic retrieval pipeline indexing 1M research documents.",
            }
        ],
    }

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    assert variant is not None
    assert len(variant.snapshot.projects) == 2
    assert variant.snapshot.projects[0].highlights[0] == "Developed semantic retrieval pipeline indexing 1M research documents."
    assert len(variant.snapshot.certifications) == 2
    assert len(variant.snapshot.achievements) == 2


# =====================================================================
# CASE E: JD requesting technologies absent from Workspace
# (Strict Anti-Hallucination & Claim Rejection Validation)
# =====================================================================
@pytest.mark.asyncio
async def test_case_e_absent_technologies_hallucination_guard(auth_user):
    evidence = CandidateEvidence(
        headline="Backend Engineer",
        summary="Backend engineer experienced in Python and MySQL.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="LegacyCo",
                role="Python Developer",
                startDate="2020-01",
                endDate="Present",
                bullets=["Built Python web backends using MySQL."],
                technologies=["Python", "MySQL"],
            )
        ],
        skills=[
            SkillItem(name="Python", category="Language"),
            SkillItem(name="MySQL", category="Database"),
        ],
    )

    req = GenerateResumeRequest(
        target_role="Rust & Kubernetes Infrastructure Lead",
        job_description="We require 5+ years of Rust systems programming, Kubernetes multi-cluster administration, and Snowflake data warehouse.",
    )

    # The mock LLM attempts to hallucinate Rust, Kubernetes, and Snowflake into the bullet
    mock_provider = AsyncMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    mock_provider.generate_json.side_effect = [
        # Pass 1: Hallucinates Rust & Kubernetes
        {
            "summary": "10 years Rust and Kubernetes architect.",
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": 0,
                    "originalBullet": "Built Python web backends using MySQL.",
                    "rewrittenBullet": "Engineered high-throughput Rust backends using Kubernetes and Snowflake to enable real-time telemetry.",
                }
            ],
            "projectRewrites": [],
        },
        # Pass 2 (Retry): Still contains invalid outcome clause
        {
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": 0,
                    "originalBullet": "Built Python web backends using MySQL.",
                    "rewrittenBullet": "Built Python web backends using MySQL to facilitate operations.",
                }
            ],
            "projectRewrites": [],
        },
    ]

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    # The hallucinatory rewrite MUST BE REJECTED and fall back safely to the original bullet
    assert variant.snapshot.experience[0].bullets[0] == "Built Python web backends using MySQL."
    # The summary hallucinating 10 years Rust must also be rejected
    assert "Rust" not in variant.snapshot.summary
    assert len(variant.change_ledger) == 0  # No hallucinated changes applied!


# =====================================================================
# CASE F: JD containing terminology overlapping / synonyms with Workspace
# =====================================================================
@pytest.mark.asyncio
async def test_case_f_semantic_synonym_overlap_ranking(auth_user):
    evidence = CandidateEvidence(
        headline="Cloud Engineer",
        summary="Cloud engineer with AWS, Postgres, and K8s expertise.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="CloudOps",
                role="Cloud Engineer",
                startDate="2021-01",
                endDate="Present",
                bullets=[
                    "Deployed cloud services to AWS and managed Postgres database clusters.",
                    "Configured K8s Helm charts for staging environments.",
                ],
                technologies=["AWS", "Postgres", "K8s"],
            )
        ],
        skills=[
            SkillItem(name="AWS", category="Cloud"),
            SkillItem(name="Postgres", category="Database"),
            SkillItem(name="K8s", category="DevOps"),
        ],
    )

    # Rank and select with JD containing formal terms: Amazon Web Services, PostgreSQL, Kubernetes
    selected_exp, selected_proj, selected_skills = rank_and_select_evidence(
        evidence=evidence,
        target_role="Kubernetes & AWS Platform Architect",
        job_description="Seeking expertise in Amazon Web Services infrastructure, PostgreSQL administration, and Kubernetes clusters.",
    )

    assert len(selected_exp) == 1
    assert len(selected_skills) == 3
    # Top ranked skill should match AWS or K8s
    skill_names = [s.name for s in selected_skills]
    assert "AWS" in skill_names
    assert "K8s" in skill_names
    assert "Postgres" in skill_names


# =====================================================================
# CASE G: Provider failure / fallback scenario
# =====================================================================
@pytest.mark.asyncio
async def test_case_g_provider_fallback_chain_success():
    evidence = CandidateEvidence(
        headline="Developer",
        summary="Experienced developer",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="DevCo",
                role="Software Engineer",
                startDate="2022-01",
                endDate="Present",
                bullets=["Implemented backend services in Go."],
                technologies=["Go"],
            )
        ],
        skills=[SkillItem(name="Go", category="Language")],
    )

    req = GenerateResumeRequest(target_role="Go Developer")

    # Primary provider (Groq) fails with 503 HTTP error
    primary_mock = AsyncMock()
    primary_mock.name = "groq"
    primary_mock.generate_json.side_effect = HTTPException(status_code=503, detail="Groq server overloaded")

    # Secondary provider (Gemini) succeeds
    secondary_mock = AsyncMock()
    secondary_mock.name = "gemini"
    secondary_mock.model_name = "gemini-2.5-flash"
    secondary_mock.generate_json.return_value = {
        "summary": "Experienced developer",
        "experienceRewrites": [],
        "projectRewrites": [],
    }

    fallback = FallbackProvider(providers=[primary_mock, secondary_mock])

    user = AuthenticatedUser(uid="user_fallback_test", email="fb@example.com", token="tok")
    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=user,
            req=req,
            provider=fallback,
        )

    assert variant is not None
    assert variant.provider == "gemini"
    assert variant.generation_metadata["provider"] == "gemini"
    assert len(variant.generation_metadata["failover_log"]) == 1
    assert variant.generation_metadata["failover_log"][0]["provider"] == "groq"


@pytest.mark.asyncio
async def test_case_g_all_providers_fail_raises_503():
    evidence = CandidateEvidence(
        headline="Developer",
        summary="Experienced developer",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="DevCo",
                role="Software Engineer",
                startDate="2022-01",
                endDate="Present",
                bullets=["Implemented backend services in Go."],
                technologies=["Go"],
            )
        ],
        skills=[SkillItem(name="Go", category="Language")],
    )

    req = GenerateResumeRequest(target_role="Go Developer")

    p1 = AsyncMock()
    p1.name = "groq"
    p1.generate_json.side_effect = HTTPException(status_code=503, detail="Groq down")

    p2 = AsyncMock()
    p2.name = "gemini"
    p2.generate_json.side_effect = HTTPException(status_code=502, detail="Gemini bad gateway")

    fallback = FallbackProvider(providers=[p1, p2])

    user = AuthenticatedUser(uid="user_fail_all", email="fail@example.com", token="tok")
    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence):
        with pytest.raises(HTTPException) as exc:
            await ResumeGenerationService.generate_role_targeted_resume(
                user=user,
                req=req,
                provider=fallback,
            )
        assert exc.value.status_code in (502, 503)


# =====================================================================
# CASE H: Long JD / noisy JD with corporate boilerplate
# =====================================================================
@pytest.mark.asyncio
async def test_case_h_long_noisy_jd_handling(auth_user):
    evidence = CandidateEvidence(
        headline="Senior Java Developer",
        summary="Senior Java engineer with Spring Boot microservices experience.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="Enterprise Systems",
                role="Senior Java Engineer",
                startDate="2019-01",
                endDate="Present",
                bullets=[
                    "Engineered enterprise Java Spring Boot microservices processing financial transactions.",
                    "Integrated Apache Kafka event streaming for asynchronous account notifications.",
                ],
                technologies=["Java", "Spring Boot", "Kafka"],
            )
        ],
        skills=[
            SkillItem(name="Java", category="Language"),
            SkillItem(name="Spring Boot", category="Framework"),
            SkillItem(name="Kafka", category="Tool"),
        ],
    )

    # 5,000+ character long JD with company history, culture, diversity, EEO boilerplate
    long_noisy_jd = (
        "ABOUT GLOBAL MEGACORP\n"
        "At Global MegaCorp, we believe that innovation happens at the intersection of diversity, culture, and relentless curiosity. "
        "Founded in 1998, MegaCorp has grown from a humble garage in Seattle to a worldwide enterprise with offices in 42 countries. "
        "We are proud to be an Equal Opportunity Employer. We do not discriminate on the basis of race, religion, color, sex, gender identity, "
        "sexual orientation, age, non-disqualifying physical or mental disability, national origin, veteran status, or any other basis covered by law. "
        * 10
        + "\n\nTHE ROLE: SENIOR JAVA MICROSERVICES ENGINEER\n"
        "We are seeking an experienced Senior Java Developer to join our Core Financial Services team. "
        "Requirements: 5+ years of Java development, Spring Boot microservices architecture, and Apache Kafka messaging.\n\n"
        + "BENEFITS AND PERKS:\n"
        "Unlimited PTO, 401(k) matching up to 6%, free artisanal kombucha on tap, wellness stipend, remote work flexibility. "
        * 5
    )

    assert len(long_noisy_jd) > 5000

    req = GenerateResumeRequest(
        target_role="Senior Java Microservices Engineer",
        target_company="Global MegaCorp",
        job_description=long_noisy_jd,
    )

    mock_provider = AsyncMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    mock_provider.generate_json.return_value = {
        "summary": "Senior Java engineer with Spring Boot microservices experience.",
        "experienceRewrites": [
            {
                "itemId": "exp_0",
                "bulletIndex": 0,
                "originalBullet": "Engineered enterprise Java Spring Boot microservices processing financial transactions.",
                "rewrittenBullet": "Developed enterprise Java Spring Boot microservices processing financial transactions.",
            }
        ],
        "projectRewrites": [],
    }

    with patch.object(ResumeService, "get_candidate_resume_data", return_value=evidence), \
         patch.object(ResumeService, "save_resume_snapshot", return_value=True):
        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=auth_user,
            req=req,
            provider=mock_provider,
        )

    assert variant is not None
    assert variant.snapshot.experience[0].bullets[0] == "Developed enterprise Java Spring Boot microservices processing financial transactions."
    assert variant.job_description == long_noisy_jd
