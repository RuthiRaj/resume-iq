"""
Evaluation Suite Runner for ResumeIQ Phase 4.0.2

Orchestrates execution of benchmark cases, collects structured results,
computes category metrics, and outputs formatted evaluation reports.
"""

from typing import List, Optional, Dict, Any
from app.evaluation.schemas import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSuiteReport,
)
from app.evaluation.datasets import get_golden_cases, DATASET_VERSION
from app.evaluation.evaluators import evaluate_case
from app.evaluation.metrics import summarize_evaluation_results


class EvaluationRunner:
    """
    Orchestrates execution of the ResumeIQ AI Evaluation benchmark suite.
    """

    def __init__(self, cases: Optional[List[EvaluationCase]] = None):
        self.cases = cases if cases is not None else get_golden_cases()

    def run_suite(self) -> EvaluationSuiteReport:
        """Executes all cases deterministically and produces an EvaluationSuiteReport."""
        results: List[EvaluationResult] = []
        
        for case in self.cases:
            res = evaluate_case(case)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        overall_pass_rate = (passed / total) if total > 0 else 1.0

        category_summaries = summarize_evaluation_results(results)

        return EvaluationSuiteReport(
            datasetVersion=DATASET_VERSION,
            evaluatorVersion="4.0.3",
            totalCases=total,
            passedCases=passed,
            failedCases=failed,
            overallPassRate=overall_pass_rate,
            categorySummaries=category_summaries,
            results=results,
        )

    @classmethod
    def run_and_format_summary(cls, cases: Optional[List[EvaluationCase]] = None) -> str:
        """Runs the suite and returns a clean, human-readable summary table."""
        runner = cls(cases=cases)
        report = runner.run_suite()

        lines = [
            "=" * 60,
            f"ResumeIQ AI Intelligence Evaluation Report (v{report.dataset_version})",
            f"Timestamp: {report.timestamp}",
            "=" * 60,
            f"Overall Status: {'PASSED' if report.failed_cases == 0 else 'FAILED'}",
            f"Total Cases: {report.total_cases} | Passed: {report.passed_cases} | Failed: {report.failed_cases} ({report.overall_pass_rate * 100:.1f}%)",
            "-" * 60,
            "Category Breakdown:",
        ]

        for cat_name, summary in report.category_summaries.items():
            lines.append(
                f"  [{cat_name.upper():<12}] Total: {summary.total_cases:<3} | Passed: {summary.passed_cases:<3} | Failed: {summary.failed_cases:<3} | Pass Rate: {summary.pass_rate * 100:.1f}%"
            )

        if report.failed_cases > 0:
            lines.extend(["-" * 60, "Failures:"])
            for r in report.results:
                if not r.passed:
                    lines.append(f"  - [{r.case_id}] ({r.task_type}):")
                    for f in r.failures:
                        lines.append(f"      * {f}")

        lines.append("=" * 60)
        return "\n".join(lines)


def run_and_print_summary() -> None:
    """Convenience function to run benchmark evaluation suite and print the summary report."""
    summary = EvaluationRunner.run_and_format_summary()
    print(summary)


if __name__ == "__main__":
    run_and_print_summary()
