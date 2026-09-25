"""
ResumeIQ Phase 4.0.8 Adversarial AI & Security Evaluation Test Suite

Offline, deterministic security benchmark suite verifying:
- Prompt injection resistance in evidence and job descriptions
- Technology equivalence attack rejection
- Metric & scale inflation rejection
- Leadership & scope inflation rejection
- Purpose / outcome clause injection rejection
- Malicious payload handling (SQL, XSS, control characters)
- Provenance boundary enforcement
- Multi-tenant isolation enforcement
- Authoritative workspace immutability
- AI failover context integrity & telemetry privacy
"""

import pytest
from app.evaluation.dataset.adversarial_cases import get_adversarial_cases, AdversarialCase
from app.evaluation.adversarial_evaluator import (
    evaluate_adversarial_case,
    run_adversarial_suite,
)


def test_adversarial_suite_aggregate_execution():
    """Executes the complete Phase 4.0.8 adversarial security suite."""
    report = run_adversarial_suite()

    assert report.total_cases == 33
    assert report.passed_cases == 33
    assert report.failed_cases == 0
    assert report.pass_rate == 1.0
    assert report.workspace_contamination_count == 0
    assert report.telemetry_privacy_violations_count == 0
    assert report.prompt_injection_blocked_count >= 6
    assert report.unsupported_claims_rejected_count >= 17
    assert report.tenant_violations_prevented_count >= 4


@pytest.mark.parametrize("case", get_adversarial_cases(), ids=lambda c: f"{c.case_id}_{c.category}")
def test_individual_adversarial_case(case: AdversarialCase):
    """Executes each adversarial case independently to verify defense enforcement."""
    result = evaluate_adversarial_case(case)
    assert result.passed is True, f"Adversarial case {case.case_id} failed: {result.failures}"


class TestAdversarialSecurityInvariants:
    """Explicit verification of the 12 core security invariants."""

    def test_invariant_1_evidence_prompt_injection_blocked(self):
        cases = [c for c in get_adversarial_cases() if c.category == "evidence_prompt_injection"]
        assert len(cases) == 3
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_2_jd_prompt_injection_blocked(self):
        cases = [c for c in get_adversarial_cases() if c.category == "jd_prompt_injection"]
        assert len(cases) == 2
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_3_hard_gap_bypass_prevented(self):
        cases = [c for c in get_adversarial_cases() if c.category == "hard_gap_bypass"]
        assert len(cases) == 1
        res = evaluate_adversarial_case(cases[0])
        assert res.passed is True, f"Failed on {cases[0].case_id}: {res.failures}"

    def test_invariant_4_technology_equivalence_rejected(self):
        cases = [c for c in get_adversarial_cases() if c.category == "technology_equivalence"]
        assert len(cases) == 6
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_5_metric_inflation_rejected(self):
        cases = [c for c in get_adversarial_cases() if c.category == "metric_inflation"]
        assert len(cases) == 4
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_6_leadership_scope_inflation_rejected(self):
        cases = [c for c in get_adversarial_cases() if c.category == "leadership_inflation"]
        assert len(cases) == 4
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_7_outcome_injection_rejected(self):
        cases = [c for c in get_adversarial_cases() if c.category == "outcome_injection"]
        assert len(cases) == 3
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_8_malicious_payloads_handled_safely(self):
        cases = [c for c in get_adversarial_cases() if c.category == "malicious_payload"]
        assert len(cases) == 3
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_9_provenance_boundary_enforced(self):
        cases = [c for c in get_adversarial_cases() if c.category == "provenance_attack"]
        assert len(cases) == 2
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_10_tenant_isolation_enforced(self):
        cases = [c for c in get_adversarial_cases() if c.category == "tenant_isolation"]
        assert len(cases) == 2
        for case in cases:
            res = evaluate_adversarial_case(case)
            assert res.passed is True, f"Failed on {case.case_id}: {res.failures}"

    def test_invariant_11_workspace_contamination_prevented(self):
        cases = [c for c in get_adversarial_cases() if c.category == "workspace_contamination"]
        assert len(cases) == 1
        res = evaluate_adversarial_case(cases[0])
        assert res.passed is True, f"Failed on {cases[0].case_id}: {res.failures}"

    def test_invariant_provider_failover_context_preserved(self):
        cases = [c for c in get_adversarial_cases() if c.category == "provider_failover_attack"]
        assert len(cases) == 1
        res = evaluate_adversarial_case(cases[0])
        assert res.passed is True, f"Failed on {cases[0].case_id}: {res.failures}"

    def test_invariant_12_telemetry_privacy_and_secrets_protected(self):
        cases = [c for c in get_adversarial_cases() if c.category == "telemetry_privacy"]
        assert len(cases) == 1
        res = evaluate_adversarial_case(cases[0])
        assert res.passed is True, f"Failed on {cases[0].case_id}: {res.failures}"
