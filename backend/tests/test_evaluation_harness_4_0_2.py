"""
Tests for Phase 4.0.2 AI Evaluation Framework and Harness

Verifies:
1. Golden dataset loading, versioning, and schema integrity
2. Evaluator correctness across retrieval, grounding, planning, security, and determinism
3. Metric calculations and category summaries
4. Report serialization and formatting
5. Offline LLM boundary interface
6. Full execution of all 18 Phase 4.0.2 golden evaluation cases
"""

import pytest
from app.evaluation import (
    DATASET_VERSION,
    EvaluationCase,
    EvaluationResult,
    EvaluationSuiteReport,
    EvaluationRunner,
    get_golden_cases,
    evaluate_case,
    evaluate_retrieval_case,
    evaluate_grounding_case,
    evaluate_planning_case,
    evaluate_security_case,
    evaluate_determinism_case,
    compute_category_summary,
    summarize_evaluation_results,
    OfflineMockEvaluationProvider,
)
from app.schemas.candidate import CandidateEvidence, SkillItem, ExperienceItem


def test_golden_dataset_integrity():
    """Verifies that the golden dataset loads unique, well-formed benchmark cases."""
    cases = get_golden_cases()
    assert len(cases) >= 18, f"Expected at least 18 golden cases, found {len(cases)}"
    assert DATASET_VERSION == "4.0.3"

    case_ids = [c.case_id for c in cases]
    assert len(case_ids) == len(set(case_ids)), "Duplicate case IDs detected in golden dataset!"

    for c in cases:
        assert c.case_id.startswith("CASE_")
        assert c.description
        assert c.task_type in ("retrieval", "grounding", "planning", "security", "determinism")
        assert isinstance(c.workspace_fixture, CandidateEvidence)


def test_offline_mock_evaluation_provider():
    """Verifies that the offline mock provider functions without external network calls."""
    mock_payload = {"summary": "Mock summary", "experienceRewrites": []}
    provider = OfflineMockEvaluationProvider(predefined_response=mock_payload)

    import asyncio
    res = asyncio.run(provider.generate_json("system instructions", "user prompt", "schema hint"))
    assert res == mock_payload
    assert len(provider.call_history) == 1
    assert provider.call_history[0]["system_instruction"] == "system instructions"


def test_evaluator_empty_workspace_case():
    """Verifies evaluator behavior on empty workspace fixture."""
    cases = get_golden_cases()
    empty_case = next(c for c in cases if c.case_id == "CASE_012")
    res = evaluate_planning_case(empty_case)
    assert res.passed is True
    assert res.case_id == "CASE_012"
    assert res.task_type == "planning"


def test_evaluator_unsupported_metric_case():
    """Verifies that ungrounded metrics are rejected by the grounding evaluator."""
    cases = get_golden_cases()
    metric_case = next(c for c in cases if c.case_id == "CASE_007")
    res = evaluate_grounding_case(metric_case)
    assert res.passed is True
    assert res.metrics.get("unsupported_claims_rejected", 0) >= 1


def test_evaluator_prompt_injection_case():
    """Verifies that prompt injection in workspace data is safely resisted."""
    cases = get_golden_cases()
    injection_case = next(c for c in cases if c.case_id == "CASE_010")
    res = evaluate_security_case(injection_case)
    assert res.passed is True
    assert res.score == 1.0


def test_evaluator_tenant_isolation_case():
    """Verifies that cross-tenant evidence access is rejected."""
    cases = get_golden_cases()
    auth_case = next(c for c in cases if c.case_id == "CASE_016")
    res = evaluate_security_case(auth_case)
    assert res.passed is True
    assert res.metrics.get("unauthorized_leak_count", 0) == 0


def test_evaluator_determinism():
    """Verifies that repeated evaluation of a deterministic case produces identical results."""
    cases = get_golden_cases()
    case_001 = cases[0]
    res = evaluate_determinism_case(case_001, runs=3)
    assert res.passed is True
    assert res.metrics["repetition_consistency"] == 1.0


def test_metrics_aggregation():
    """Verifies category summary metric computation."""
    mock_results = [
        EvaluationResult(
            caseId="C1",
            taskType="retrieval",
            passed=True,
            score=1.0,
            metrics={"precision": 1.0, "hit_rate": 1.0},
        ),
        EvaluationResult(
            caseId="C2",
            taskType="retrieval",
            passed=False,
            score=0.5,
            metrics={"precision": 0.5, "hit_rate": 0.0},
            failures=["Expected item missed"],
        ),
    ]

    summary = compute_category_summary("retrieval", mock_results)
    assert summary.total_cases == 2
    assert summary.passed_cases == 1
    assert summary.failed_cases == 1
    assert summary.pass_rate == 0.5
    assert summary.aggregated_metrics["avg_precision"] == 0.75
    assert summary.aggregated_metrics["avg_hit_rate"] == 0.5


def test_full_golden_evaluation_suite():
    """Executes all 18 golden evaluation cases and asserts 100% benchmark pass rate."""
    runner = EvaluationRunner()
    report = runner.run_suite()

    all_cases = get_golden_cases()
    assert report.dataset_version == DATASET_VERSION
    assert report.total_cases == len(all_cases)
    assert report.failed_cases == 0, f"Failures detected: {[r.failures for r in report.results if not r.passed]}"
    assert report.passed_cases == len(all_cases)
    assert report.overall_pass_rate == 1.0

    # Ensure all 4 core categories are summarized
    assert "retrieval" in report.category_summaries
    assert "grounding" in report.category_summaries
    assert "planning" in report.category_summaries
    assert "security" in report.category_summaries

    # Verify report formatting
    summary_text = EvaluationRunner.run_and_format_summary()
    assert f"ResumeIQ AI Intelligence Evaluation Report (v{DATASET_VERSION})" in summary_text
    assert "Overall Status: PASSED" in summary_text
