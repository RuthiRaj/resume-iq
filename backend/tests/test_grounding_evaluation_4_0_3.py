"""
Grounding & Hallucination Evaluation Suite for ResumeIQ Phase 4.0.3

Unit and integration tests verifying:
- Supported claim acceptance
- Unsupported claim rejection
- Metric fabrication detection
- Technology hallucination detection
- Leadership / scope inflation detection
- Business outcome fabrication detection
- Experience duration validation
- Credential hallucination detection
- Company / Title hallucination detection
- Workspace prompt injection handling
- Related-but-unverified skill rejection
- Missing evidence / abstention enforcement
- Provenance chain verification
- Contradictory evidence handling
- AI inference != verified fact boundary
- Candidate workspace immutability
- Granular grounding metrics & false acceptance rates
"""

import pytest
from app.schemas.candidate import CandidateEvidence, ExperienceItem, SkillItem
from app.evaluation.schemas import EvaluationCase, EvaluationResult
from app.evaluation.datasets import get_golden_cases, DATASET_VERSION
from app.evaluation.evaluators import evaluate_case, evaluate_grounding_case
from app.evaluation.metrics import compute_category_summary
from app.evaluation.runner import EvaluationRunner


def test_dataset_version_4_0_3():
    """Verifies that dataset version is 4.0.3 and total cases count is 35."""
    assert DATASET_VERSION == "4.0.3"
    cases = get_golden_cases()
    assert len(cases) == 35
    assert len({c.case_id for c in cases}) == 35


def test_case_g1_supported_technology():
    """Case G1: Verified FastAPI + Python REST API claim must be accepted."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_019")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["supported_claims_accepted"] >= 1.0
    assert res.metrics["false_rejection_count"] == 0.0


def test_case_g2_supported_metric():
    """Case G2: Verified 30% latency reduction metric must be preserved and accepted."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_020")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["supported_claims_accepted"] >= 1.0
    assert res.metrics["false_rejection_count"] == 0.0


def test_case_g3_outcome_boundary_enforcement():
    """Case G3: Unproven outcome clause 'to improve service reliability' must be flagged."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_021")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0
    assert res.metrics["false_acceptance_count"] == 0.0


def test_case_g4_fabricated_metric_rejection():
    """Case G4: Fabricated metric 40% (source 30%) must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_022")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0
    assert res.metrics["metric_hallucination_rejection"] >= 1.0


def test_case_g5_technology_hallucination_rejection():
    """Case G5: Hallucinated Kubernetes, AWS, PostgreSQL, Terraform must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_023")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g6_leadership_scope_inflation_rejection():
    """Case G6: Unsupported 'Led the backend architecture team' must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_024")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["leadership_scope_inflation_rejection"] >= 1.0


def test_case_g7_fabricated_business_outcome_rejection():
    """Case G7: Fabricated 'increased sales by 25%' outcome must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_025")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g8_scope_inflation_rejection():
    """Case G8: Fabricated enterprise-wide / 50,000 customers scale must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_026")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g9_duration_hallucination_rejection():
    """Case G9: Fabricated '3+ years' experience from 8 months dates must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_027")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g10_credential_hallucination_rejection():
    """Case G10: Unverified AWS Certified Solutions Architect must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_028")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g11_company_title_hallucination_rejection():
    """Case G11: Fabricated company 'Global Systems' & title must be rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_029")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g12_prompt_injection_boundary():
    """Case G12: Prompt injection in candidate bullet text remains passive data; unverified skills rejected."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_030")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g13_related_unverified_rejection():
    """Case G13: Docker does not authorize unverified Kubernetes claims."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_031")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g14_missing_evidence_abstention():
    """Case G14: Absent PostgreSQL evidence causes rejection of PostgreSQL schema claims."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_032")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g15_provenance_preservation_chain():
    """Case G15: Verified claim preserves evidence ID, source item ID, and source document metadata."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_033")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["provenance_preservation"] == 1.0
    assert res.actual["provenance"]["sourceDocumentName"] == "backend_resume_2024.pdf"


def test_case_g16_conflict_handling_without_fabrication():
    """Case G16: Conflicting concurrent records are evaluated safely without fabricating unified scope inflation."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_034")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_case_g17_ai_inference_not_verified_fact():
    """Case G17: AI inference ('designed distributed microservices architecture') cannot be accepted as fact."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_035")
    res = evaluate_grounding_case(case)
    assert res.passed is True
    assert res.metrics["unsupported_claims_rejected"] >= 1.0


def test_candidate_workspace_immutability():
    """Verifies that evaluation never mutates the underlying candidate workspace fixture."""
    fixture = CandidateEvidence(
        headline="Original Headline",
        summary="Original Summary",
        experience=[
            ExperienceItem(
                id="exp_immut_0",
                role="Original Role",
                company="Original Company",
                start_date="2020",
                end_date="Present",
                bullets=["Original verified accomplishment."],
                technologies=["Python"],
            )
        ],
        skills=[SkillItem(name="Python", category="Language", proficiency="Advanced")],
    )
    original_json = fixture.model_dump_json()

    case = EvaluationCase(
        caseId="IMMUTABILITY_TEST",
        description="Immutability validation test",
        taskType="grounding",
        workspaceFixture=fixture,
        jobDescriptionFixture={"targetRole": "Engineer", "mustHaveSkills": ["Python"]},
        syntheticGenerationPayload={
            "summary": "Mutated AI summary attempt.",
            "experienceRewrites": [
                {
                    "itemId": "exp_immut_0",
                    "originalBullet": "Original verified accomplishment.",
                    "rewrittenBullet": "Original verified accomplishment.",
                }
            ],
        },
    )

    res = evaluate_grounding_case(case)
    assert res.passed is True
    # Ensure fixture in memory was not modified
    assert fixture.model_dump_json() == original_json


def test_grounding_metrics_calculation():
    """Verifies category metric calculation and explicit hallucination false acceptance rate."""
    runner = EvaluationRunner()
    report = runner.run_suite()

    grounding_summary = report.category_summaries["grounding"]
    assert grounding_summary.total_cases == 22
    assert grounding_summary.passed_cases == 22
    assert grounding_summary.pass_rate == 1.0
    assert grounding_summary.aggregated_metrics["total_false_acceptance_count"] == 0.0
    assert grounding_summary.aggregated_metrics["avg_hallucination_false_acceptance_rate"] == 0.0
    assert grounding_summary.aggregated_metrics["total_unsupported_claims_rejected"] >= 15.0
