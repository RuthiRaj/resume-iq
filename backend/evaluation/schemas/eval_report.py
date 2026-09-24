"""
Evaluation Report Schemas for ResumeIQ AI Evaluation Framework

Defines contracts for:
- MetricResult: Individual evaluation metric outcome contract
- CaseEvalResult: Case-level evaluation results (metrics + predictions)
- EvalReport: Aggregate benchmark evaluation report
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from evaluation.schemas.eval_case import EvaluationMetadata, EvaluationPrediction


class MetricResult(BaseModel):
    """
    Contract representing the evaluation result of a single metric.
    Supports ratio metrics (precision, recall, accuracy), pass/fail assertions,
    threshold checks, and structured measurement details.
    """

    metric_name: str = Field(
        ...,
        alias="metricName",
        min_length=1,
        max_length=100,
        description="Metric identifier (e.g. 'requirement_extraction_recall', 'grounding_precision')",
    )
    value: float = Field(
        ..., description="Calculated metric value"
    )
    numerator: Optional[float] = Field(
        default=None, description="Numerator for ratio-based metrics"
    )
    denominator: Optional[float] = Field(
        default=None, description="Denominator for ratio-based metrics"
    )
    unit: Optional[str] = Field(
        default=None, description="Measurement unit (e.g. '%', 'ms', 'usd', 'ratio')"
    )
    passed: Optional[bool] = Field(
        default=None, description="Whether the metric satisfied the evaluation threshold"
    )
    threshold: Optional[float] = Field(
        default=None, description="Target evaluation threshold required to pass"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Structured breakdown or diagnostic details"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CaseEvalResult(BaseModel):
    """
    Represents evaluation outcomes for a single benchmark case run.
    Contains case ID, overall pass/fail status, metric results, prediction wrapper, and errors.
    """

    case_id: str = Field(
        ..., alias="caseId", description="Evaluated benchmark case ID"
    )
    passed: bool = Field(
        ..., description="Whether all threshold criteria passed for this case"
    )
    metrics: List[MetricResult] = Field(
        default_factory=list, description="Per-case metric evaluation results"
    )
    prediction: Optional[EvaluationPrediction] = Field(
        default=None, description="System prediction captured during run"
    )
    errors: List[str] = Field(
        default_factory=list, description="Error messages or diagnostic warnings"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvalReport(BaseModel):
    """
    Contract representing a complete benchmark evaluation run report.
    Contains run metadata, aggregate metrics, case-level results, failures, and warnings.
    """

    report_id: str = Field(
        ..., alias="reportId", description="Unique evaluation report ID"
    )
    eval_metadata: EvaluationMetadata = Field(
        ..., alias="evalMetadata", description="Run execution metadata"
    )
    cases_evaluated: int = Field(
        ..., alias="casesEvaluated", ge=0, description="Total cases executed"
    )
    cases_passed: Optional[int] = Field(
        default=0, alias="casesPassed", ge=0, description="Number of cases passed"
    )
    cases_failed: Optional[int] = Field(
        default=0, alias="casesFailed", ge=0, description="Number of cases failed"
    )
    aggregate_metrics: List[MetricResult] = Field(
        default_factory=list,
        alias="aggregateMetrics",
        description="Aggregate metric results across all evaluated cases",
    )
    case_results: List[CaseEvalResult] = Field(
        default_factory=list,
        alias="caseResults",
        description="Detailed evaluation results per case",
    )
    failures: List[Dict[str, Any]] = Field(
        default_factory=list, description="Structured failure diagnostics"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Non-fatal evaluation warnings"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
