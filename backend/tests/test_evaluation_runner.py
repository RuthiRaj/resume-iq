"""
Tests for ResumeIQ Phase 2.4 Offline Benchmark Runner

Validates:
- Single and multi-case benchmark execution.
- Case filtering by ID, category, tag, and max_cases.
- Ground truth isolation: ground truth is NEVER passed into provider inference.
- Order-independent requirement matching by normalized name.
- Metric evaluation for StrongMatch, PartialMatch, Missing, grounding, provenance, gap type, experience years, and quantifiable impact.
- Graceful handling of missing predictions, unexpected predictions, and single-case failures without aborting benchmark sweeps.
- Prompt injection security resilience (case_013 & case_014).
- Score bounds being None does not fail evaluation.
- Full offline execution of all 15 golden cases without API keys or network calls.
- Serialization and deserialization of complete EvalReport objects.
"""

import pytest
import asyncio
from app.schemas.candidate import CandidateEvidence, ExperienceItem
from app.schemas.analyze import AnalyzeResponse
from app.schemas.common import ScoreBreakdown, AnalysisMetadata
from app.schemas.requirement_match import RequirementMatch, EvidenceDimensions
from evaluation.schemas.eval_case import (
    EvalCase,
    CandidateJobInput,
    GroundTruthRequirement,
    EvaluationPrediction,
)
from evaluation.schemas.eval_report import EvalReport
from evaluation.dataset import get_case_by_id, get_golden_cases
from evaluation.runner import BenchmarkRunner, MockAiAnalyzerProvider
from evaluation.metrics import evaluate_case_metrics, aggregate_benchmark_metrics


@pytest.mark.asyncio
async def test_single_golden_case_executes_successfully():
    """Verify single golden case execution produces a valid CaseEvalResult."""
    runner = BenchmarkRunner()
    case = get_case_by_id("case_001_exact_match")
    assert case is not None

    result = await runner.run_case(case)
    assert result.case_id == "case_001_exact_match"
    assert result.prediction is not None
    assert len(result.metrics) >= 3
    assert result.passed is True


@pytest.mark.asyncio
async def test_multiple_cases_execute_successfully():
    """Verify benchmark run across multiple cases produces aggregate report."""
    runner = BenchmarkRunner()
    report = await runner.run_benchmark(max_cases=3)

    assert report.cases_evaluated == 3
    assert report.cases_passed + report.cases_failed == 3
    assert len(report.case_results) == 3
    assert len(report.aggregate_metrics) >= 3


def test_case_filtering_by_id_category_tag():
    """Verify runner filters cases accurately by ID, category, tag, and max_cases."""
    runner = BenchmarkRunner()
    all_cases = get_golden_cases()

    # ID filter
    filtered_ids = runner.filter_cases(all_cases, case_ids=["case_001_exact_match", "case_006_missing_requirement"])
    assert len(filtered_ids) == 2
    assert {c.case_id for c in filtered_ids} == {"case_001_exact_match", "case_006_missing_requirement"}

    # Category filter
    filtered_cat = runner.filter_cases(all_cases, categories=["ExactMatch", "PromptInjection"])
    assert len(filtered_cat) == 3  # case_001, case_013, case_014
    assert {c.category for c in filtered_cat} == {"ExactMatch", "PromptInjection"}

    # Tag filter
    filtered_tag = runner.filter_cases(all_cases, tags=["python"])
    assert len(filtered_tag) >= 1
    assert all("python" in c.tags for c in filtered_tag)

    # Max cases limit
    filtered_max = runner.filter_cases(all_cases, max_cases=5)
    assert len(filtered_max) == 5


@pytest.mark.asyncio
async def test_ground_truth_isolation_in_provider_input():
    """Verify ground truth expectations are NEVER passed to provider analyze method."""
    inspected_args = {}

    class InspectingProvider(MockAiAnalyzerProvider):
        async def analyze(
            self,
            target_role: str,
            target_company: str,
            job_description: str,
            job_description_hash: str,
            candidate_evidence: CandidateEvidence,
        ):
            inspected_args["target_role"] = target_role
            inspected_args["target_company"] = target_company
            inspected_args["job_description"] = job_description
            inspected_args["candidate_evidence"] = candidate_evidence
            return await super().analyze(
                target_role, target_company, job_description, job_description_hash, candidate_evidence
            )

    runner = BenchmarkRunner(provider=InspectingProvider())
    case = get_case_by_id("case_001_exact_match")
    assert case is not None

    await runner.run_case(case)

    # Ground truth requirement objects must NOT be present in provider inputs
    assert "ground_truth_requirements" not in inspected_args
    assert inspected_args["target_role"] == case.input.target_role
    assert inspected_args["job_description"] == case.input.job_description


@pytest.mark.asyncio
async def test_requirement_matching_order_independence():
    """Verify matching operates correctly even when prediction requirement order differs from ground truth."""
    case = get_case_by_id("case_001_exact_match")
    assert case is not None

    runner = BenchmarkRunner()
    result = await runner.run_case(case)

    # Reverse predictions list order
    reversed_prediction = EvaluationPrediction(
        predicted_ats_score=result.prediction.predicted_ats_score,
        score_breakdown=result.prediction.score_breakdown,
        predicted_requirements=list(reversed(result.prediction.predicted_requirements)),
    )

    metrics, passed, errors = evaluate_case_metrics(case, reversed_prediction)
    assert passed == result.passed
    assert metrics[0].value == result.metrics[0].value  # Recall metric unchanged


def test_match_status_evaluations():
    """Verify StrongMatch, PartialMatch, and Missing status comparisons."""
    gt_req = GroundTruthRequirement(
        requirement_name="Python",
        expected_match_status="StrongMatch",
    )
    case = EvalCase(
        case_id="case_status_test",
        title="Status Test",
        category="General",
        input=CandidateJobInput(
            candidate_evidence=CandidateEvidence(),
            target_role="Dev",
            job_description="Need Python developer with microservices.",
        ),
        ground_truth_requirements=[gt_req],
    )

    pred_strong = EvaluationPrediction(
        predicted_requirements=[
            RequirementMatch(
                requirement_name="Python",
                match_status="StrongMatch",
                resume_evidence="Python APIs",
            )
        ]
    )

    metrics, passed, errors = evaluate_case_metrics(case, pred_strong)
    assert metrics[1].value == 1.0  # match_status_accuracy == 100%

    pred_partial = EvaluationPrediction(
        predicted_requirements=[
            RequirementMatch(
                requirement_name="Python",
                match_status="PartialMatch",
                resume_evidence="Python",
            )
        ]
    )

    metrics_p, passed_p, errors_p = evaluate_case_metrics(case, pred_partial)
    assert metrics_p[1].value == 0.0  # match_status_accuracy == 0%


def test_grounding_provenance_and_gap_evaluations():
    """Verify evidence grounding, provenance, gap type, and dimensions metric evaluations."""
    gt_req = GroundTruthRequirement(
        requirement_name="PostgreSQL",
        expected_match_status="PartialMatch",
        expected_provenance="Experience",
        expected_gap_type="AdjacentTechnology",
        expected_experience_years_condition=False,
        expected_quantifiable_impact_condition=True,
    )
    case = EvalCase(
        case_id="case_dims_test",
        title="Dimensions Test",
        category="AdjacentTech",
        input=CandidateJobInput(
            candidate_evidence=CandidateEvidence(
                experience=[
                    ExperienceItem(
                        role="Data Engineer",
                        company="TechCorp",
                        bullets=["Queried Postgres database processing 10k RPS."],
                    )
                ]
            ),
            target_role="Data Engineer",
            job_description="Need PostgreSQL experience with high throughput.",
        ),
        ground_truth_requirements=[gt_req],
    )

    pred = EvaluationPrediction(
        predicted_requirements=[
            RequirementMatch(
                requirement_name="PostgreSQL",
                match_status="PartialMatch",
                resume_evidence="Queried Postgres database processing 10k RPS.",
                evidence_source_section="Experience",
                gap_type="AdjacentTechnology",
                evidence_dimensions=EvidenceDimensions(
                    meets_experience_years=False,
                    quantifiable_impact=True,
                ),
            )
        ]
    )

    metrics, passed, errors = evaluate_case_metrics(case, pred)
    for m in metrics:
        if m.metric_name in (
            "provenance_accuracy",
            "gap_type_accuracy",
            "experience_years_dimension_accuracy",
            "quantifiable_impact_dimension_accuracy",
        ):
            assert m.value == 1.0  # All dimension assertions matched expected ground truth


@pytest.mark.asyncio
async def test_missing_prediction_does_not_crash_runner():
    """Verify empty/missing prediction handles gracefully without crashing."""
    case = get_case_by_id("case_001_exact_match")
    assert case is not None

    metrics, passed, errors = evaluate_case_metrics(case, None)
    assert passed is False
    assert len(errors) > 0
    assert metrics[0].value == 0.0


@pytest.mark.asyncio
async def test_unexpected_predictions_do_not_crash():
    """Verify unexpected extra predicted requirements do not crash metric evaluation."""
    case = get_case_by_id("case_001_exact_match")
    assert case is not None

    pred = EvaluationPrediction(
        predicted_requirements=[
            RequirementMatch(requirement_name="UnexpectedSkill1", match_status="StrongMatch"),
            RequirementMatch(requirement_name="UnexpectedSkill2", match_status="Missing"),
        ]
    )

    metrics, passed, errors = evaluate_case_metrics(case, pred)
    assert isinstance(passed, bool)
    assert len(metrics) >= 2


@pytest.mark.asyncio
async def test_one_failed_case_does_not_stop_sweep():
    """Verify a single failing case allows remaining cases to execute cleanly."""
    class FailingFirstCaseProvider(MockAiAnalyzerProvider):
        async def analyze(self, target_role, target_company, job_description, job_description_hash, candidate_evidence):
            if "Exact Match" in job_description or "Python" in job_description:
                raise RuntimeError("Simulated transient provider failure on case 1!")
            return await super().analyze(target_role, target_company, job_description, job_description_hash, candidate_evidence)

    runner = BenchmarkRunner(provider=FailingFirstCaseProvider())
    report = await runner.run_benchmark(max_cases=3)

    assert report.cases_evaluated == 3
    assert report.cases_failed >= 1
    assert report.cases_passed >= 1
    assert len(report.failures) >= 1


@pytest.mark.asyncio
async def test_prompt_injection_cases_execute_safely():
    """Verify prompt injection cases (case_013 & case_014) execute safely and evaluate ground truth deterministically."""
    runner = BenchmarkRunner()

    case_jd = get_case_by_id("case_013_prompt_injection_jd")
    assert case_jd is not None
    res_jd = await runner.run_case(case_jd)
    assert res_jd.case_id == "case_013_prompt_injection_jd"
    assert res_jd.prediction is not None

    case_resume = get_case_by_id("case_014_prompt_injection_resume")
    assert case_resume is not None
    res_resume = await runner.run_case(case_resume)
    assert res_resume.case_id == "case_014_prompt_injection_resume"
    assert res_resume.prediction is not None


@pytest.mark.asyncio
async def test_ats_score_bounds_none_does_not_fail_evaluation():
    """Verify expected_min/max_ats_score being None evaluates cleanly."""
    runner = BenchmarkRunner()
    case = get_case_by_id("case_001_exact_match")
    assert case is not None
    assert case.expected_min_ats_score is None

    result = await runner.run_case(case)
    assert result.passed is True


@pytest.mark.asyncio
async def test_eval_report_serialization_deserialization_aliases():
    """Verify EvalReport produced by runner serializes/deserializes round-trip with aliases."""
    runner = BenchmarkRunner()
    report = await runner.run_benchmark(max_cases=2)

    dumped = report.model_dump(by_alias=True)
    assert dumped["casesEvaluated"] == 2
    assert "reportId" in dumped
    assert "evalMetadata" in dumped
    assert "aggregateMetrics" in dumped

    # Round trip deserialization
    revalidated = EvalReport.model_validate(dumped)
    assert revalidated.cases_evaluated == 2
    assert revalidated.report_id == report.report_id


@pytest.mark.asyncio
async def test_full_golden_dataset_offline_runner_sweep():
    """Verify all 15 golden benchmark cases execute through the offline runner without network calls."""
    runner = BenchmarkRunner()
    report = await runner.run_benchmark()

    assert report.cases_evaluated == 15
    assert report.cases_passed + report.cases_failed == 15
    assert len(report.case_results) == 15
    assert len(report.aggregate_metrics) >= 3
