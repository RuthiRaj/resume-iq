"""
Metrics Aggregation Engine for ResumeIQ Phase 4.0.2 AI Evaluation Framework

Computes aggregated rates and raw counts across benchmark categories:
- Retrieval (Precision@k, Recall@k, Hit Rate, Match-Class Accuracy, False Positives)
- Grounding (Unsupported Claim Rejection Rate, Supported Acceptance Rate, Provenance Preservation Rate)
- Planning (Hard Gap Detection Rate, Prohibited Claim Coverage, Grounded Selection Rate)
- Security (Unauthorized Rejection Rate, Prompt-Injection Resistance Rate)
- Determinism (Repeatability / Invariant Consistency)
"""

from typing import List, Dict, Any
from app.evaluation.schemas import EvaluationResult, CategorySummary


def compute_category_summary(task_type: str, results: List[EvaluationResult]) -> CategorySummary:
    """Computes aggregated metrics and pass rate for a specific evaluation task category."""
    cat_results = [r for r in results if r.task_type == task_type]
    total = len(cat_results)
    if total == 0:
        return CategorySummary(
            taskType=task_type,
            totalCases=0,
            passedCases=0,
            failedCases=0,
            passRate=1.0,
            aggregatedMetrics={},
        )

    passed = sum(1 for r in cat_results if r.passed)
    failed = total - passed
    pass_rate = passed / total

    # Aggregate metric values
    agg_metrics: Dict[str, float] = {}
    metric_keys = {k for r in cat_results for k in r.metrics.keys()}
    
    for k in metric_keys:
        vals = [r.metrics[k] for r in cat_results if k in r.metrics]
        if vals:
            agg_metrics[f"avg_{k}"] = sum(vals) / len(vals)
            agg_metrics[f"total_{k}"] = sum(vals)

    return CategorySummary(
        taskType=task_type,
        totalCases=total,
        passedCases=passed,
        failedCases=failed,
        passRate=pass_rate,
        aggregatedMetrics=agg_metrics,
    )


def summarize_evaluation_results(results: List[EvaluationResult]) -> Dict[str, CategorySummary]:
    """Generates a mapping of task_type to CategorySummary across all evaluation categories."""
    task_types = {"retrieval", "grounding", "planning", "security", "determinism"}
    # Also include any task types present in results
    task_types.update(r.task_type for r in results)
    
    return {
        t: compute_category_summary(t, results)
        for t in sorted(list(task_types))
        if any(r.task_type == t for r in results)
    }
