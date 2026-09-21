import pytest
from pydantic import ValidationError
from app.schemas.candidate import CandidateEvidence, ExperienceItem, SkillItem
from app.schemas.common import ScoreBreakdown
from app.schemas.requirement_match import RequirementMatch, EvidenceDimensions
from evaluation.schemas.eval_case import (
    EvalCase,
    CandidateJobInput,
    GroundTruthRequirement,
    EvaluationMetadata,
    EvaluationPrediction,
)
from evaluation.schemas.eval_report import (
    EvalReport,
    CaseEvalResult,
    MetricResult,
)


def test_valid_eval_case_parsing():
    """Test that a complete EvalCase can be constructed and parsed successfully."""
    candidate = CandidateEvidence(
        headline="Senior Python Engineer",
        summary="Experienced backend engineer.",
        experience=[
            ExperienceItem(
                role="Senior Developer",
                company="TechCorp",
                bullets=["Architected Python microservices handling 20M daily requests."],
                technologies=["Python", "FastAPI"],
            )
        ],
        skills=[SkillItem(name="Python", category="Language")],
    )

    case_input = CandidateJobInput(
        candidate_evidence=candidate,
        target_role="Senior Python Developer",
        target_company="Stripe",
        job_description="We are looking for a Senior Python Developer with microservices experience.",
    )

    gt_requirement = GroundTruthRequirement(
        requirement_name="Python",
        category="Language",
        importance="MustHave",
        expected_match_status="StrongMatch",
        acceptable_evidence=["Architected Python microservices"],
        expected_provenance="Experience",
        expected_gap_type="None",
        expected_experience_years_condition=True,
        expected_quantifiable_impact_condition=True,
        notes="Candidate has strong production Python experience.",
    )

    eval_case = EvalCase(
        case_id="case_001_python_test",
        title="Python Senior Developer Exact Match Test",
        description="Verifies strong match classification for Python backend developer.",
        category="ExactMatch",
        input=case_input,
        ground_truth_requirements=[gt_requirement],
        expected_min_ats_score=80,
        expected_max_ats_score=100,
        tags=["python", "backend", "senior"],
    )

    dumped = eval_case.model_dump(by_alias=True)
    assert dumped["caseId"] == "case_001_python_test"
    assert dumped["category"] == "ExactMatch"
    assert dumped["input"]["targetRole"] == "Senior Python Developer"
    assert dumped["groundTruthRequirements"][0]["requirementName"] == "Python"
    assert dumped["groundTruthRequirements"][0]["expectedMatchStatus"] == "StrongMatch"

    # Verify round-trip re-validation
    revalidated = EvalCase.model_validate(dumped)
    assert revalidated.case_id == "case_001_python_test"
    assert revalidated.ground_truth_requirements[0].expected_match_status == "StrongMatch"


def test_ground_truth_match_statuses():
    """Test that GroundTruthRequirement supports StrongMatch, PartialMatch, and Missing."""
    gt_strong = GroundTruthRequirement(
        requirement_name="Python",
        expected_match_status="StrongMatch",
    )
    gt_partial = GroundTruthRequirement(
        requirement_name="AWS",
        expected_match_status="PartialMatch",
        expected_gap_type="AdjacentTechnology",
    )
    gt_missing = GroundTruthRequirement(
        requirement_name="Rust",
        expected_match_status="Missing",
        expected_gap_type="MissingEvidence",
    )

    assert gt_strong.expected_match_status == "StrongMatch"
    assert gt_partial.expected_match_status == "PartialMatch"
    assert gt_partial.expected_gap_type == "AdjacentTechnology"
    assert gt_missing.expected_match_status == "Missing"
    assert gt_missing.expected_gap_type == "MissingEvidence"


def test_optional_metadata_fields_can_be_absent():
    """Test that token, latency, and cost fields can be completely absent in EvaluationMetadata."""
    meta_minimal = EvaluationMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    assert meta_minimal.provider == "groq"
    assert meta_minimal.model == "llama-3.3-70b-versatile"
    assert meta_minimal.prompt_tokens is None
    assert meta_minimal.completion_tokens is None
    assert meta_minimal.execution_time_ms is None
    assert meta_minimal.estimated_cost is None

    # Serialization check
    dumped = meta_minimal.model_dump(by_alias=True, exclude_none=True)
    assert "promptTokens" not in dumped
    assert "executionTimeMs" not in dumped


def test_invalid_data_rejected_by_enum_and_types():
    """Test that invalid match status or category strings raise ValidationError."""
    with pytest.raises(ValidationError):
        GroundTruthRequirement(
            requirement_name="Python",
            expected_match_status="InvalidStatusName",  # Invalid enum
        )

    with pytest.raises(ValidationError):
        EvalCase(
            case_id="case_invalid!",  # Invalid character '!' in pattern
            title="Invalid Case",
            input=CandidateJobInput(
                candidate_evidence=CandidateEvidence(),
                target_role="Dev",
                job_description="Short text minimum 30 chars requirement check.",
            ),
        )


def test_eval_report_serialization_deserialization():
    """Test full report creation, metric aggregation, serialization and deserialization."""
    metadata = EvaluationMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
        prompt_version="v1.0",
        run_id="run_2026_09_09_001",
        executed_at="2026-09-09T21:00:00Z",
    )

    metric_recall = MetricResult(
        metric_name="requirement_extraction_recall",
        value=0.95,
        numerator=19.0,
        denominator=20.0,
        unit="ratio",
        passed=True,
        threshold=0.90,
    )

    metric_grounding = MetricResult(
        metric_name="grounding_precision",
        value=1.0,
        numerator=15.0,
        denominator=15.0,
        unit="ratio",
        passed=True,
        threshold=1.0,
    )

    prediction = EvaluationPrediction(
        predicted_ats_score=85,
        score_breakdown=ScoreBreakdown(
            relevance=85, keywords=80, metrics=90, formatting=85
        ),
        predicted_requirements=[
            RequirementMatch(
                requirement_name="Python",
                category="Language",
                match_status="StrongMatch",
                resume_evidence="Architected Python microservices",
            )
        ],
    )

    case_result = CaseEvalResult(
        case_id="case_001_python_test",
        passed=True,
        metrics=[metric_recall, metric_grounding],
        prediction=prediction,
    )

    report = EvalReport(
        report_id="report_2026_09_09_001",
        eval_metadata=metadata,
        cases_evaluated=1,
        cases_passed=1,
        cases_failed=0,
        aggregate_metrics=[metric_recall, metric_grounding],
        case_results=[case_result],
    )

    dumped = report.model_dump(by_alias=True)
    assert dumped["reportId"] == "report_2026_09_09_001"
    assert dumped["casesEvaluated"] == 1
    assert dumped["aggregateMetrics"][0]["metricName"] == "requirement_extraction_recall"
    assert dumped["caseResults"][0]["prediction"]["predictedAtsScore"] == 85

    # Test round-trip deserialization
    revalidated = EvalReport.model_validate(dumped)
    assert revalidated.report_id == "report_2026_09_09_001"
    assert revalidated.cases_passed == 1
    assert revalidated.case_results[0].prediction.predicted_ats_score == 85
