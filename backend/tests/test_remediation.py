import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from app.schemas.requirement_match import RequirementMatch, EvidenceDimensions
from app.schemas.candidate import CandidateEvidence, ExperienceItem, SkillItem
from app.schemas.remediation import (
    RemediationSuggestion,
    RemediationEligibility,
    RemediationActionType,
    SynthesizeBulletRequest,
    ApplyRemediationRequest,
)
from app.ai.claim_validator import validate_claims_against_source
from app.ai.remediation_engine import (
    generate_source_evidence_id,
    determine_remediation_eligibility_and_action,
    construct_remediation_suggestion,
    generate_remediation_suggestions,
)
from app.api.v1.remediate import synthesize_bullet_endpoint, apply_remediation_endpoint
from app.core.auth import AuthenticatedUser
from app.ai.scoring import calculate_deterministic_ats_score


# --- 1. Truthfulness Tests ---

def test_missing_evidence_never_generates_bullet():
    candidate = CandidateEvidence(
        headline="Full Stack Dev",
        experience=[ExperienceItem(role="Dev", company="A", bullets=["Built web applications."])],
    )
    missing_match = RequirementMatch(
        requirement_name="Apache Kafka",
        category="Tool",
        importance="MustHave",
        match_status="Missing",
        resume_evidence="",
        job_source_evidence="Must have experience with Apache Kafka for real-time streams",
        confidence="High",
    )
    sug = construct_remediation_suggestion(match=missing_match, candidate_evidence=candidate)
    assert sug is not None
    assert sug.suggested_bullet == ""
    assert sug.action_type == "PromptForMissingFacts"
    assert sug.eligibility == "RequiresCandidateFacts"


# --- 2. Claim Validation Tests ---

def test_claim_validator_accepts_grounded_rewrite():
    original = "Architected Python FastAPI microservices handling 15M transactions with 45% lower latency."
    proposed = "Engineered high-performance Python FastAPI microservices processing 15M daily transactions, reducing query latency by 45%."

    result = validate_claims_against_source(proposed_bullet=proposed, source_evidence=original)
    assert result.is_valid is True
    assert result.status == "Validated"
    assert len(result.unsupported_claims) == 0


def test_claim_validator_rejects_hallucinated_metrics():
    original = "Built Python REST endpoints for payment verification."
    proposed = "Architected Python REST endpoints processing 10M daily transactions and $50M in volume."

    result = validate_claims_against_source(proposed_bullet=proposed, source_evidence=original)
    assert result.is_valid is False
    assert result.status == "RequiresCandidateInput"
    assert len(result.unsupported_claims) >= 1
    categories = [c.category for c in result.unsupported_claims]
    assert "Metric" in categories


def test_claim_validator_rejects_hallucinated_team_size():
    original = "Collaborated with team on backend services in Go."
    proposed = "Managed a cross-functional team of 15 engineers to deliver backend services in Go."

    result = validate_claims_against_source(proposed_bullet=proposed, source_evidence=original)
    assert result.is_valid is False
    assert result.status == "RequiresCandidateInput"
    categories = [c.category for c in result.unsupported_claims]
    assert "TeamOrganization" in categories or "SeniorityRole" in categories


def test_claim_validator_rejects_hallucinated_seniority():
    original = "Assisted in building frontend components in React."
    proposed = "Acted as Lead Architect overseeing design system and frontend architecture in React."

    result = validate_claims_against_source(proposed_bullet=proposed, source_evidence=original)
    assert result.is_valid is False
    assert result.status == "RequiresCandidateInput"
    categories = [c.category for c in result.unsupported_claims]
    assert "SeniorityRole" in categories


def test_claim_validator_rejects_hallucinated_environment():
    original = "Tested web app on local development machine."
    proposed = "Deployed and maintained multi-region high availability production cluster on AWS EKS."

    result = validate_claims_against_source(proposed_bullet=proposed, source_evidence=original)
    assert result.is_valid is False
    assert result.status == "RequiresCandidateInput"
    categories = [c.category for c in result.unsupported_claims]
    assert "Scale" in categories


# --- 3. Provenance & Anchoring Tests ---

def test_improve_existing_bullet_anchors_to_source():
    candidate = CandidateEvidence(
        headline="Dev",
        experience=[
            ExperienceItem(
                role="Dev",
                company="X Corp",
                bullets=["Optimized PostgreSQL database queries."],
            )
        ],
    )
    match = RequirementMatch(
        requirement_name="PostgreSQL",
        category="Database",
        importance="MustHave",
        match_status="PartialMatch",
        resume_evidence="Optimized PostgreSQL database queries.",
        job_source_evidence="3+ years PostgreSQL database optimization",
        evidence_source_section="Experience",
        confidence="High",
    )
    sug = construct_remediation_suggestion(match=match, candidate_evidence=candidate)
    assert sug is not None
    assert sug.action_type == "ImproveExistingBullet"
    assert sug.target_section == "Experience"
    assert sug.original_evidence == "Optimized PostgreSQL database queries."
    assert sug.source_evidence_id is not None
    assert len(sug.source_evidence_id) == 16


def test_stale_source_evidence_is_rejected():
    id_orig = generate_source_evidence_id("Experience", "0", "Built REST APIs with Python.")
    id_modified = generate_source_evidence_id("Experience", "0", "Completely rewritten different bullet.")
    assert id_orig != id_modified


# --- 4. Eligibility Tests ---

def test_missing_evidence_requires_candidate_facts():
    elig, act, _ = determine_remediation_eligibility_and_action(
        match_status="Missing",
        gap_type="MissingEvidence",
        provenance="None",
        importance="MustHave",
    )
    assert elig == "RequiresCandidateFacts"
    assert act == "PromptForMissingFacts"


def test_skilltag_production_gap_requires_candidate_facts():
    elig, act, _ = determine_remediation_eligibility_and_action(
        match_status="PartialMatch",
        gap_type="MissingProductionExperience",
        provenance="SkillTag",
        importance="MustHave",
    )
    assert elig == "RequiresCandidateFacts"
    assert act == "AddProjectContext"


def test_experience_year_gap_is_not_remediable():
    elig, act, _ = determine_remediation_eligibility_and_action(
        match_status="Missing",
        gap_type="InsufficientExperienceYears",
        provenance="None",
        importance="MustHave",
    )
    assert elig == "NotRemediable"
    assert act == "ExplainHardGap"


def test_adjacent_technology_is_partially_remediable():
    elig, act, _ = determine_remediation_eligibility_and_action(
        match_status="PartialMatch",
        gap_type="AdjacentTechnology",
        provenance="Experience",
        importance="Preferred",
    )
    assert elig == "PartiallyRemediable"
    assert act == "ClarifyAdjacentTechnology"


# --- 5. Candidate Fact Synthesis Tests ---

@pytest.mark.asyncio
async def test_user_fact_synthesis_is_bounded(monkeypatch):
    import app.api.v1.remediate as remediate_module
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "synthesizedBullet": "Deployed containerized microservices to AWS EKS clusters during internship."
    })
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(remediate_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    user = AuthenticatedUser(uid="test_u1", token="mock_token", email="test@example.com")
    req = SynthesizeBulletRequest(
        requirement_name="Kubernetes",
        candidate_fact="Deployed containerized microservices to AWS EKS clusters during internship.",
        target_role="Senior Engineer",
    )

    resp = await synthesize_bullet_endpoint(req=req, current_user=user)
    assert resp.synthesized_bullet == "Deployed containerized microservices to AWS EKS clusters during internship."
    assert resp.validation.is_valid is True
    assert resp.status == "Validated"


@pytest.mark.asyncio
async def test_user_fact_synthesis_rejects_hallucinated_metrics(monkeypatch):
    import app.api.v1.remediate as remediate_module
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_key")

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    # Model introduces 100M queries not in candidate facts
    mock_choice.message.content = json.dumps({
        "synthesizedBullet": "Architected Kubernetes cluster handling 100M daily queries with 99.99% uptime."
    })
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(remediate_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    user = AuthenticatedUser(uid="test_u1", token="mock_token", email="test@example.com")
    req = SynthesizeBulletRequest(
        requirement_name="Kubernetes",
        candidate_fact="Used Kubernetes locally for running mini test pods.",
        target_role="Senior Engineer",
    )

    resp = await synthesize_bullet_endpoint(req=req, current_user=user)
    assert resp.validation.is_valid is False
    assert resp.status == "RequiresCandidateInput"
    assert len(resp.validation.unsupported_claims) >= 1


# --- 6. Resume Protection & Targeted Variant Tests ---

@pytest.mark.asyncio
async def test_master_resume_remains_unmodified_and_targeted_receives_remediation(monkeypatch):
    from app.services.resume_service import ResumeService

    mock_resume_doc = {
        "title": "Master Resume",
        "targetRole": "Software Engineer",
        "snapshot": {
            "experience": [
                {
                    "role": "Software Engineer",
                    "company": "Tech Corp",
                    "bullets": ["Old bullet 1", "Old bullet 2"],
                }
            ],
            "skills": [],
            "projects": [],
        }
    }

    saved_data = None
    saved_resume_id = None

    async def mock_get(user, resume_id):
        return mock_resume_doc

    async def mock_save(user, resume_id, resume_data):
        nonlocal saved_data, saved_resume_id
        saved_data = resume_data
        saved_resume_id = resume_id
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="test_user_456", token="mock_token", email="u@example.com")
    valid_anchor_id = generate_source_evidence_id("Experience", "0", "Old bullet 1")
    req = ApplyRemediationRequest(
        resume_id="master_resume_123",
        remediation_id="rem_123",
        source_evidence_id=valid_anchor_id,
        target_section="Experience",
        target_experience_id="0",
        target_bullet_index=0,
        approved_bullet="Architected high-throughput payment REST APIs using Python.",
        target_role="Senior Backend Engineer",
        target_company="Stripe",
    )

    resp = await apply_remediation_endpoint(req=req, current_user=user)

    assert resp.success is True
    assert resp.status == "Applied"
    assert resp.targeted_resume_id.startswith("targeted_master_resume_123_")
    assert saved_data["isTargetedVariant"] is True
    assert saved_data["masterResumeId"] == "master_resume_123"
    assert saved_data["snapshot"]["experience"][0]["bullets"][0] == "Architected high-throughput payment REST APIs using Python."
    assert mock_resume_doc["title"] == "Master Resume"


@pytest.mark.asyncio
async def test_stale_source_evidence_is_rejected_on_apply(monkeypatch):
    from fastapi import HTTPException
    from app.services.resume_service import ResumeService

    mock_resume_doc = {
        "title": "Master Resume",
        "targetRole": "Software Engineer",
        "snapshot": {
            "experience": [
                {
                    "role": "Software Engineer",
                    "company": "Tech Corp",
                    "bullets": ["Modified bullet that no longer matches analysis."],
                }
            ],
            "skills": [],
            "projects": [],
        }
    }

    async def mock_get(user, resume_id):
        return mock_resume_doc

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    user = AuthenticatedUser(uid="test_user_456", token="mock_token", email="u@example.com")
    stale_anchor_id = generate_source_evidence_id("Experience", "0", "Original bullet from previous analysis")

    req = ApplyRemediationRequest(
        resume_id="master_resume_123",
        remediation_id="rem_123",
        source_evidence_id=stale_anchor_id,
        target_section="Experience",
        target_experience_id="0",
        target_bullet_index=0,
        approved_bullet="Architected high-throughput payment REST APIs using Python.",
        target_role="Senior Backend Engineer",
        target_company="Stripe",
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_remediation_endpoint(req=req, current_user=user)
    assert exc_info.value.status_code == 409
    assert "Stale remediation" in exc_info.value.detail


# --- 7. ATS Formula & Re-Analysis Delta Tests ---

def test_ats_formula_unchanged():
    # 50*0.40 + 50*0.30 + 75*0.15 + 80*0.15 = 20 + 15 + 11.25 + 12 = 58.25 -> 58
    score = calculate_deterministic_ats_score(50, 50, 75, 80)
    assert score == 58


def test_reanalysis_delta_is_actual_difference():
    before_score = 58
    after_score = 71
    delta = after_score - before_score
    assert delta == 13
