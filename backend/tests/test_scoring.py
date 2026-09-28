import pytest
from app.ai.scoring import calculate_deterministic_ats_score, reconcile_score_breakdown
from app.schemas.common import ScoreBreakdown


def test_scoring_all_max_scores_yields_100():
    score = calculate_deterministic_ats_score(100, 100, 100, 100)
    assert score == 100


def test_scoring_all_zero_scores_yields_0():
    score = calculate_deterministic_ats_score(0, 0, 0, 0)
    assert score == 0


def test_scoring_reconciled_weights_example_1():
    # 80*0.4 (32) + 60*0.3 (18) + 40*0.15 (6) + 20*0.15 (3) = 59
    score = calculate_deterministic_ats_score(80, 60, 40, 20)
    assert score == 59


def test_scoring_reconciled_weights_example_2():
    # 40*0.4 (16) + 30*0.3 (9) + 15*0.15 (2.25) + 15*0.15 (2.25) = 29.5 -> rounds to 30
    score = calculate_deterministic_ats_score(40, 30, 15, 15)
    assert score == 30


def test_scoring_reconciled_weights_example_3():
    # 90*0.4 (36) + 85*0.3 (25.5) + 70*0.15 (10.5) + 80*0.15 (12) = 84.0 -> 84
    score = calculate_deterministic_ats_score(90, 85, 70, 80)
    assert score == 84


def test_scoring_clamping_out_of_bounds():
    # Negative values clamped to 0
    assert calculate_deterministic_ats_score(-10, -50, 0, 0) == 0
    # Values > 100 clamped to 100
    assert calculate_deterministic_ats_score(150, 200, 100, 100) == 100


def test_reconcile_score_breakdown_helper():
    breakdown = ScoreBreakdown(relevance=75, keywords=80, metrics=65, formatting=90)
    # 75*0.4 (30) + 80*0.3 (24) + 65*0.15 (9.75) + 90*0.15 (13.5) = 77.25 -> 77
    score = reconcile_score_breakdown(breakdown)
    assert score == 77


def test_scoring_and_evidence_pipeline_with_none_proficiency():
    """
    Verifies that skill items with proficiency=None (omitted default) work cleanly
    across evidence construction, ATS scoring breakdowns, and deterministic calculations.
    """
    from app.schemas.candidate import CandidateEvidence, SkillItem
    from app.services.evidence_service import EvidenceService

    evidence = CandidateEvidence(
        headline="Full Stack Engineer",
        summary="Experienced engineer with backend skills.",
        skills=[
            SkillItem(name="Python", category="Language", proficiency=None, verification_status="verified"),
            SkillItem(name="TypeScript", category="Language", proficiency=None, verification_status="unverified"),
        ],
    )

    # 1. Verify EvidenceService converts proficiency=None skills into clean text representations
    evidence_items = EvidenceService.normalize_candidate_evidence("usr_test_scoring", evidence)
    assert len(evidence_items) >= 2
    skill_descriptions = [item.description for item in evidence_items if item.source_type == "skills"]
    assert "Python (Language)" in skill_descriptions
    assert "TypeScript (Language)" in skill_descriptions

    # 2. Verify ATS scoring breakdown calculations remain deterministic and valid
    breakdown = ScoreBreakdown(relevance=85, keywords=90, metrics=70, formatting=80)
    score = reconcile_score_breakdown(breakdown)
    assert score == 84
    assert 0 <= score <= 100
