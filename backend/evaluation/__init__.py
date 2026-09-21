"""
ResumeIQ AI Evaluation Framework Package
"""

from evaluation.metadata import (
    hash_candidate_evidence,
    hash_job_description,
    hash_prompt,
    generate_run_id,
    get_current_iso_utc,
    estimate_token_cost,
    EvaluationTimer,
    create_evaluation_metadata,
)
from evaluation.metrics import (
    evaluate_case_metrics,
    aggregate_benchmark_metrics,
    extract_all_candidate_text,
)
from evaluation.runner import (
    BenchmarkRunner,
    MockAiAnalyzerProvider,
)

__all__ = [
    "hash_candidate_evidence",
    "hash_job_description",
    "hash_prompt",
    "generate_run_id",
    "get_current_iso_utc",
    "estimate_token_cost",
    "EvaluationTimer",
    "create_evaluation_metadata",
    "evaluate_case_metrics",
    "aggregate_benchmark_metrics",
    "extract_all_candidate_text",
    "BenchmarkRunner",
    "MockAiAnalyzerProvider",
]
