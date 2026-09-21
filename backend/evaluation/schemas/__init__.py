"""
ResumeIQ Evaluation Schemas Package

Exports evaluation contracts:
- GroundTruthRequirement
- CandidateJobInput
- EvaluationMetadata
- EvaluationPrediction
- EvalCase
- MetricResult
- CaseEvalResult
- EvalReport
"""

from evaluation.schemas.eval_case import (
    GroundTruthRequirement,
    CandidateJobInput,
    EvaluationMetadata,
    EvaluationPrediction,
    EvalCase,
)
from evaluation.schemas.eval_report import (
    MetricResult,
    CaseEvalResult,
    EvalReport,
)

__all__ = [
    "GroundTruthRequirement",
    "CandidateJobInput",
    "EvaluationMetadata",
    "EvaluationPrediction",
    "EvalCase",
    "MetricResult",
    "CaseEvalResult",
    "EvalReport",
]
