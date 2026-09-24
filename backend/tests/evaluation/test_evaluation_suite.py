"""
ResumeIQ Golden Regression Test Suite for Phase 4.0.2

Provides the dedicated pytest target:
pytest backend/tests/evaluation -q

Runs all 18 benchmark cases and prints a structured summary report.
"""

import pytest
from app.evaluation import EvaluationRunner, get_golden_cases, DATASET_VERSION


def test_golden_evaluation_dataset_execution():
    """Executes the Phase 4.0.2 benchmark suite and prints the formatted summary."""
    runner = EvaluationRunner()
    report = runner.run_suite()

    # Format summary table
    summary = EvaluationRunner.run_and_format_summary()
    print("\n" + summary)

    all_cases = get_golden_cases()
    assert report.dataset_version == DATASET_VERSION
    assert report.total_cases == len(all_cases)
    assert report.failed_cases == 0, f"Failures detected: {[r.failures for r in report.results if not r.passed]}"
    assert report.passed_cases == len(all_cases)
    assert report.overall_pass_rate == 1.0


@pytest.mark.parametrize("case", get_golden_cases(), ids=lambda c: f"{c.case_id}_{c.task_type}")
def test_individual_golden_case(case):
    """Executes each golden case as an independent parameterized pytest test."""
    from app.evaluation.evaluators import evaluate_case
    result = evaluate_case(case)
    assert result.passed is True, f"Case {case.case_id} failed: {result.failures}"
