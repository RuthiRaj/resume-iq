"""
Comprehensive Unit and Regression Tests for Phase 4.0.5 AI Abstention & Multi-Dimensional Confidence

Tests:
- ConfidenceBreakdown & AIAbstentionDecision schemas
- DecisionEngine deterministic policies (ACCEPT, REVIEW, ABSTAIN)
- Hard Safety Precedence over overall numerical confidence
- Multi-Tenant Security & Isolation enforcement
- Adversarial Prompt Injection resistance
- Grounding & ClaimValidator integration
- Technology Non-Equivalence & Related Cluster Review
- Expected Calibration Error (ECE) metric
- 10-Iteration Bitwise Determinism
- Full 55-case Golden Dataset Execution
"""

import pytest
from app.schemas.candidate import CandidateEvidence, ExperienceItem, SkillItem
from app.schemas.evidence import EvidenceItem, VerificationStatus
from app.schemas.remediation import ValidationResult, UnsupportedClaim
from app.schemas.decision import ConfidenceBreakdown, AIAbstentionDecision, DecisionType
from app.ai.decision_engine import (
    DecisionEngine,
    WEIGHT_EVIDENCE_STRENGTH,
    WEIGHT_RETRIEVAL_RELEVANCE,
    WEIGHT_GROUNDING_CONFIDENCE,
    WEIGHT_CLAIM_SAFETY,
    ACCEPT_CONFIDENCE_THRESHOLD,
    REVIEW_CONFIDENCE_THRESHOLD,
)
from app.evaluation.metrics import calculate_expected_calibration_error
from app.evaluation.runner import EvaluationRunner
from app.evaluation.datasets import get_golden_cases, DATASET_VERSION


# =============================================================================
# 1. SCHEMA TESTS
# =============================================================================

def test_confidence_breakdown_schema_bounds_and_defaults():
    cb = ConfidenceBreakdown(
        evidenceStrength=0.90,
        retrievalRelevance=0.85,
        groundingConfidence=0.95,
        claimSafety=1.0,
        overallConfidence=0.92,
    )
    assert 0.0 <= cb.evidence_strength <= 1.0
    assert 0.0 <= cb.retrieval_relevance <= 1.0
    assert 0.0 <= cb.grounding_confidence <= 1.0
    assert 0.0 <= cb.claim_safety <= 1.0
    assert 0.0 <= cb.overall_confidence <= 1.0

    # Test serialization and alias mapping
    dumped = cb.model_dump(by_alias=True)
    assert "evidenceStrength" in dumped
    assert "retrievalRelevance" in dumped
    assert "groundingConfidence" in dumped
    assert "claimSafety" in dumped
    assert "overallConfidence" in dumped


def test_ai_abstention_decision_serialization():
    cb = ConfidenceBreakdown(
        evidenceStrength=1.0,
        retrievalRelevance=1.0,
        groundingConfidence=1.0,
        claimSafety=1.0,
        overallConfidence=1.0,
    )
    decision = AIAbstentionDecision(
        decision="ACCEPT",
        confidence=cb,
        reasons=["Verified evidence found"],
        reviewPrompts=[],
        prohibitedClaims=[],
        evidenceIds=["ev_0"],
        requirement="React",
        matchClass="direct_match",
    )
    assert decision.decision == "ACCEPT"
    dumped = decision.model_dump(by_alias=True)
    assert dumped["decision"] == "ACCEPT"
    assert dumped["matchClass"] == "direct_match"
    assert dumped["evidenceIds"] == ["ev_0"]


# =============================================================================
# 2. DECISION ENGINE POLICY TESTS
# =============================================================================

def test_decision_engine_accept_policy():
    item = EvidenceItem(
        evidenceId="ev_0",
        userId="user_123",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Software Engineer at Acme",
        skills=["React", "TypeScript"],
        verificationStatus="verified",
        confidence=1.0,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="React",
        match_class="direct_match",
        matched_technology="React",
        evidence_items=[item],
        retrieval_score=1.0,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "ACCEPT"
    assert dec.confidence.overall_confidence >= ACCEPT_CONFIDENCE_THRESHOLD
    assert dec.confidence.claim_safety == 1.0
    assert len(dec.reasons) > 0
    assert len(dec.prohibited_claims) == 0


def test_decision_engine_review_on_unverified_evidence():
    item = EvidenceItem(
        evidenceId="ev_unverified",
        userId="user_123",
        sourceType="experience",
        sourceItemId="exp_draft",
        title="Draft Engineer",
        skills=["Go"],
        verificationStatus="unverified",
        confidence=0.50,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="Go",
        match_class="direct_match",
        matched_technology="Go",
        evidence_items=[item],
        retrieval_score=0.90,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "REVIEW"
    assert any("unverified" in r.lower() for r in dec.reasons)
    assert len(dec.review_prompts) > 0


def test_decision_engine_review_on_related_unverified():
    item = EvidenceItem(
        evidenceId="ev_docker",
        userId="user_123",
        sourceType="experience",
        sourceItemId="exp_0",
        title="DevOps Engineer",
        skills=["Docker"],
        verificationStatus="verified",
        confidence=1.0,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="Kubernetes",
        match_class="related_but_unverified",
        matched_technology="Docker",
        evidence_items=[item],
        retrieval_score=0.75,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "REVIEW"
    assert any("Docker" in r for r in dec.reasons)
    assert any("Kubernetes" in p for p in dec.review_prompts)


def test_decision_engine_abstain_on_missing_evidence():
    dec = DecisionEngine.evaluate_decision(
        requirement="Rust",
        match_class="missing",
        matched_technology=None,
        evidence_items=[],
        retrieval_score=0.0,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "ABSTAIN"
    assert any("No verified evidence" in r for r in dec.reasons)
    assert any("Do not fabricate" in p for p in dec.prohibited_claims)


def test_decision_engine_abstain_on_claim_validator_failure():
    val_res = ValidationResult(
        is_valid=False,
        status="RequiresCandidateInput",
        unsupported_claims=[
            UnsupportedClaim(
                category="Metric",
                claim_text="99.99%",
                reason="The metric '99.99%' does not appear in verified evidence.",
                prompt_for_user="What was your actual availability metric?",
            )
        ],
        sanitized_bullet="",
    )
    item = EvidenceItem(
        evidenceId="ev_0",
        userId="user_123",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Database Engineer",
        skills=["PostgreSQL"],
        verificationStatus="verified",
        confidence=1.0,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="PostgreSQL",
        match_class="direct_match",
        matched_technology="PostgreSQL",
        evidence_items=[item],
        validation_result=val_res,
        retrieval_score=1.0,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "ABSTAIN"
    assert dec.confidence.claim_safety == 0.0
    assert any("99.99%" in r for r in dec.reasons)
    assert any("99.99%" in p for p in dec.prohibited_claims)


# =============================================================================
# 3. HARD SAFETY PRECEDENCE & SECURITY TESTS
# =============================================================================

def test_hard_safety_tenant_isolation_always_abstains():
    item = EvidenceItem(
        evidenceId="ev_alice",
        userId="user_alice",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Proprietary AI Architect",
        skills=["PyTorch"],
        verificationStatus="verified",
        confidence=1.0,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="PyTorch",
        match_class="direct_match",
        matched_technology="PyTorch",
        evidence_items=[item],
        retrieval_score=1.0,
        auth_context={"resourceOwnerUid": "user_alice", "evaluatingUid": "user_bob"},
    )
    assert dec.decision == "ABSTAIN"
    assert dec.confidence.claim_safety == 0.0
    assert any("Multi-tenant isolation violation" in r for r in dec.reasons)


def test_hard_safety_prompt_injection_always_abstains():
    item = EvidenceItem(
        evidenceId="ev_adv",
        userId="user_123",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Attacker",
        skills=["Solana"],
        verificationStatus="verified",
        confidence=1.0,
    )
    dec = DecisionEngine.evaluate_decision(
        requirement="Solana",
        match_class="direct_match",
        matched_technology="Solana",
        evidence_items=[item],
        retrieval_score=1.0,
        is_prompt_injection_detected=True,
        auth_context={"resourceOwnerUid": "user_123", "evaluatingUid": "user_123"},
    )
    assert dec.decision == "ABSTAIN"
    assert dec.confidence.claim_safety == 0.0
    assert any("Adversarial prompt injection" in r for r in dec.reasons)


# =============================================================================
# 4. DETERMINISM & CALIBRATION TESTS
# =============================================================================

def test_decision_engine_bitwise_repetition_determinism():
    item = EvidenceItem(
        evidenceId="ev_det",
        userId="user_det",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Systems Developer",
        skills=["C++"],
        verificationStatus="verified",
        confidence=1.0,
    )
    decisions = []
    for _ in range(10):
        d = DecisionEngine.evaluate_decision(
            requirement="C++",
            match_class="direct_match",
            matched_technology="C++",
            evidence_items=[item],
            retrieval_score=0.95,
            auth_context={"resourceOwnerUid": "user_det", "evaluatingUid": "user_det"},
        )
        decisions.append(d.model_dump())

    # Assert 100% bitwise identity across all 10 iterations
    first = decisions[0]
    for idx, d in enumerate(decisions[1:], start=2):
        assert d == first, f"Non-deterministic decision on iteration {idx}"


def test_expected_calibration_error_metric():
    confidences = [0.95, 0.90, 0.85, 0.70, 0.60, 0.30, 0.10]
    labels = [1, 1, 1, 1, 0, 0, 0]
    ece = calculate_expected_calibration_error(confidences, labels, num_bins=5)
    assert 0.0 <= ece <= 1.0


# =============================================================================
# 5. FULL BENCHMARK DATASET EXECUTION
# =============================================================================

def test_golden_dataset_version_is_4_0_5():
    assert DATASET_VERSION == "4.0.5"
    cases = get_golden_cases()
    assert len(cases) == 55
    case_ids = [c.case_id for c in cases]
    assert "CASE_046" in case_ids
    assert "CASE_055" in case_ids


def test_full_evaluation_runner_suite():
    runner = EvaluationRunner()
    report = runner.run_suite()
    assert report.dataset_version == "4.0.5"
    assert report.evaluator_version == "4.0.5"
    assert report.total_cases == 55
    assert report.failed_cases == 0, f"Failures: {[(r.case_id, r.failures) for r in report.results if not r.passed]}"
    assert report.passed_cases == 55
    assert report.overall_pass_rate == 1.0
    assert "abstention" in report.category_summaries
    assert report.category_summaries["abstention"].pass_rate == 1.0
