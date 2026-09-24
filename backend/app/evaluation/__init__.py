"""
ResumeIQ AI Evaluation Framework (Phase 4.0.2)

Provides deterministic, offline-capable benchmarking and metrics for:
- Retrieval & Match Classification
- Grounding & Claim Validation
- Planning & Hard Gap Detection
- Prompt Security & Multi-Tenant Isolation
- Repeatability & Determinism
"""

from app.evaluation.schemas import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSuiteReport,
    EvaluationTaskType,
    ExpectedMatchClass,
    CategorySummary,
)
from app.evaluation.datasets import get_golden_cases, DATASET_VERSION
from app.evaluation.evaluators import (
    evaluate_case,
    evaluate_retrieval_case,
    evaluate_grounding_case,
    evaluate_planning_case,
    evaluate_security_case,
    evaluate_determinism_case,
)
from app.evaluation.metrics import (
    compute_category_summary,
    summarize_evaluation_results,
)
from app.evaluation.llm_boundary import (
    EvaluationModelProvider,
    OfflineMockEvaluationProvider,
)
from app.evaluation.runner import EvaluationRunner, run_and_print_summary

__all__ = [
    "DATASET_VERSION",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationSuiteReport",
    "EvaluationTaskType",
    "ExpectedMatchClass",
    "CategorySummary",
    "get_golden_cases",
    "evaluate_case",
    "evaluate_retrieval_case",
    "evaluate_grounding_case",
    "evaluate_planning_case",
    "evaluate_security_case",
    "evaluate_determinism_case",
    "compute_category_summary",
    "summarize_evaluation_results",
    "EvaluationModelProvider",
    "OfflineMockEvaluationProvider",
    "EvaluationRunner",
    "run_and_print_summary",
]
