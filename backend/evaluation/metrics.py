"""
ResumeIQ Evaluation Metrics Engine

Computes deterministic, schema-compliant metrics comparing system predictions
(EvaluationPrediction) against expert ground truth expectations (GroundTruthRequirement).

Supports:
- Requirement coverage / recall
- Match status accuracy (StrongMatch, PartialMatch, Missing)
- Evidence grounding precision
- Acceptable evidence relevance
- Provenance section accuracy
- Gap type accuracy
- Evidence dimensions accuracy (meets_experience_years, quantifiable_impact)
- Deterministic metric aggregation across cases
"""

from typing import List, Dict, Any, Tuple, Optional
from app.ai.skills import normalize_skill_name
from app.schemas.candidate import CandidateEvidence
from evaluation.schemas.eval_case import (
    EvalCase,
    GroundTruthRequirement,
    EvaluationPrediction,
)
from evaluation.schemas.eval_report import MetricResult, CaseEvalResult


def extract_all_candidate_text(candidate: CandidateEvidence) -> str:
    """Extracts all text content from candidate evidence into a single lowercased string."""
    parts: List[str] = []

    if candidate.headline:
        parts.append(candidate.headline)
    if candidate.summary:
        parts.append(candidate.summary)

    for exp in candidate.experience:
        parts.append(exp.role)
        parts.append(exp.company)
        parts.extend(exp.bullets)
        parts.extend(exp.technologies)

    for proj in candidate.projects:
        parts.append(proj.title)
        parts.append(proj.description)
        parts.extend(proj.highlights)
        parts.extend(proj.tech_stack)

    for skill in candidate.skills:
        parts.append(skill.name)

    for edu in candidate.education:
        parts.append(edu.degree)
        parts.append(edu.institution)

    for cert in candidate.certifications:
        parts.append(cert.title)
        parts.append(cert.issuer)

    return " ".join(parts).lower()


def evaluate_case_metrics(
    eval_case: EvalCase,
    prediction: Optional[EvaluationPrediction],
) -> Tuple[List[MetricResult], bool, List[str]]:
    """
    Evaluates per-case metrics comparing prediction against ground-truth requirements.
    Returns: (metrics_list, passed_boolean, errors_list)
    """
    metrics: List[MetricResult] = []
    errors: List[str] = []

    gt_reqs = eval_case.ground_truth_requirements
    if not prediction:
        errors.append("No prediction captured for benchmark case.")
        empty_recall = MetricResult(
            metric_name="requirement_coverage_recall",
            value=0.0,
            numerator=0.0,
            denominator=float(len(gt_reqs)),
            unit="ratio",
            passed=False,
            threshold=0.75,
            details={"notes": "Prediction was missing or errored."},
        )
        return [empty_recall], False, errors

    pred_reqs = prediction.predicted_requirements
    cand_text = extract_all_candidate_text(eval_case.input.candidate_evidence)

    # Build normalized lookup map for predictions
    pred_map: Dict[str, Any] = {}
    for p in pred_reqs:
        norm_key = normalize_skill_name(p.requirement_name)
        pred_map[norm_key] = p

    # 1. Requirement Coverage / Recall
    matched_count = 0
    for gt in gt_reqs:
        gt_key = normalize_skill_name(gt.requirement_name)
        if gt_key in pred_map:
            matched_count += 1

    total_gt = float(len(gt_reqs))
    recall_val = (float(matched_count) / total_gt) if total_gt > 0 else 1.0
    metrics.append(
        MetricResult(
            metric_name="requirement_coverage_recall",
            value=round(recall_val, 4),
            numerator=float(matched_count),
            denominator=total_gt,
            unit="ratio",
            passed=recall_val >= 0.75,
            threshold=0.75,
            details={"matched": matched_count, "total_expected": int(total_gt)},
        )
    )

    # 2. Match Status Accuracy
    correct_status_count = 0
    total_matched = 0
    for gt in gt_reqs:
        gt_key = normalize_skill_name(gt.requirement_name)
        if gt_key in pred_map:
            total_matched += 1
            pred = pred_map[gt_key]
            if pred.match_status == gt.expected_match_status:
                correct_status_count += 1
            else:
                errors.append(
                    f"Match status mismatch for '{gt.requirement_name}': "
                    f"expected={gt.expected_match_status}, predicted={pred.match_status}"
                )

    status_acc = (float(correct_status_count) / float(total_matched)) if total_matched > 0 else 1.0
    metrics.append(
        MetricResult(
            metric_name="match_status_accuracy",
            value=round(status_acc, 4),
            numerator=float(correct_status_count),
            denominator=float(total_matched),
            unit="ratio",
            passed=status_acc >= 0.50,
            threshold=0.50,
            details={"correct_status": correct_status_count, "total_matched": total_matched},
        )
    )

    # 3. Evidence Grounding Precision
    grounded_count = 0
    pred_with_evidence = 0
    for p in pred_reqs:
        ev = (p.resume_evidence or "").strip().lower()
        if ev:
            pred_with_evidence += 1
            if ev in cand_text or any(token in cand_text for token in ev.split() if len(token) > 3):
                grounded_count += 1

    grounding_prec = (
        (float(grounded_count) / float(pred_with_evidence)) if pred_with_evidence > 0 else 1.0
    )
    metrics.append(
        MetricResult(
            metric_name="evidence_grounding_precision",
            value=round(grounding_prec, 4),
            numerator=float(grounded_count),
            denominator=float(pred_with_evidence),
            unit="ratio",
            passed=grounding_prec >= 0.80,
            threshold=0.80,
            details={"grounded": grounded_count, "total_predicted_evidence": pred_with_evidence},
        )
    )

    # 4. Provenance Accuracy
    prov_correct = 0
    prov_total = 0
    for gt in gt_reqs:
        if gt.expected_provenance is not None and gt.expected_provenance != "None":
            prov_total += 1
            gt_key = normalize_skill_name(gt.requirement_name)
            if gt_key in pred_map:
                pred = pred_map[gt_key]
                if pred.evidence_source_section == gt.expected_provenance:
                    prov_correct += 1

    if prov_total > 0:
        prov_acc = float(prov_correct) / float(prov_total)
        metrics.append(
            MetricResult(
                metric_name="provenance_accuracy",
                value=round(prov_acc, 4),
                numerator=float(prov_correct),
                denominator=float(prov_total),
                unit="ratio",
                passed=prov_acc >= 0.50,
                threshold=0.50,
                details={"correct_provenance": prov_correct, "total_provenance": prov_total},
            )
        )

    # 5. Gap Type Accuracy
    gap_correct = 0
    gap_total = 0
    for gt in gt_reqs:
        if gt.expected_gap_type is not None:
            gap_total += 1
            gt_key = normalize_skill_name(gt.requirement_name)
            if gt_key in pred_map:
                pred = pred_map[gt_key]
                if pred.gap_type == gt.expected_gap_type:
                    gap_correct += 1

    if gap_total > 0:
        gap_acc = float(gap_correct) / float(gap_total)
        metrics.append(
            MetricResult(
                metric_name="gap_type_accuracy",
                value=round(gap_acc, 4),
                numerator=float(gap_correct),
                denominator=float(gap_total),
                unit="ratio",
                passed=gap_acc >= 0.50,
                threshold=0.50,
                details={"correct_gap_type": gap_correct, "total_gap_type": gap_total},
            )
        )

    # 6. Experience Years & Quantifiable Impact Dimensions Accuracy
    exp_years_correct = 0
    exp_years_total = 0
    quant_impact_correct = 0
    quant_impact_total = 0

    for gt in gt_reqs:
        gt_key = normalize_skill_name(gt.requirement_name)
        if gt_key in pred_map:
            pred = pred_map[gt_key]

            if gt.expected_experience_years_condition is not None:
                exp_years_total += 1
                if (
                    pred.evidence_dimensions.meets_experience_years
                    == gt.expected_experience_years_condition
                ):
                    exp_years_correct += 1

            if gt.expected_quantifiable_impact_condition is not None:
                quant_impact_total += 1
                if (
                    pred.evidence_dimensions.quantifiable_impact
                    == gt.expected_quantifiable_impact_condition
                ):
                    quant_impact_correct += 1

    if exp_years_total > 0:
        exp_years_acc = float(exp_years_correct) / float(exp_years_total)
        metrics.append(
            MetricResult(
                metric_name="experience_years_dimension_accuracy",
                value=round(exp_years_acc, 4),
                numerator=float(exp_years_correct),
                denominator=float(exp_years_total),
                unit="ratio",
                passed=exp_years_acc >= 0.50,
                threshold=0.50,
                details={"correct": exp_years_correct, "total": exp_years_total},
            )
        )

    if quant_impact_total > 0:
        quant_impact_acc = float(quant_impact_correct) / float(quant_impact_total)
        metrics.append(
            MetricResult(
                metric_name="quantifiable_impact_dimension_accuracy",
                value=round(quant_impact_acc, 4),
                numerator=float(quant_impact_correct),
                denominator=float(quant_impact_total),
                unit="ratio",
                passed=quant_impact_acc >= 0.50,
                threshold=0.50,
                details={"correct": quant_impact_correct, "total": quant_impact_total},
            )
        )

    # Overall case pass criteria: recall >= 0.75 and match status accuracy >= 0.50
    case_passed = recall_val >= 0.75 and status_acc >= 0.50
    return metrics, case_passed, errors


def aggregate_benchmark_metrics(case_results: List[CaseEvalResult]) -> List[MetricResult]:
    """
    Computes aggregate metrics across all evaluated benchmark cases.
    Performs deterministic ratio accumulation across case results.
    """
    sums: Dict[str, Tuple[float, float, float]] = {}

    for case_res in case_results:
        for m in case_res.metrics:
            name = m.metric_name
            num = m.numerator if m.numerator is not None else m.value
            den = m.denominator if m.denominator is not None else 1.0
            thresh = m.threshold if m.threshold is not None else 0.5

            if name not in sums:
                sums[name] = (0.0, 0.0, thresh)
            cur_num, cur_den, t = sums[name]
            sums[name] = (cur_num + num, cur_den + den, t)

    aggregates: List[MetricResult] = []
    for name, (total_num, total_den, thresh) in sums.items():
        avg_val = (total_num / total_den) if total_den > 0 else 1.0
        aggregates.append(
            MetricResult(
                metric_name=name,
                value=round(avg_val, 4),
                numerator=round(total_num, 2),
                denominator=round(total_den, 2),
                unit="ratio",
                passed=avg_val >= thresh,
                threshold=thresh,
                details={"total_cases": len(case_results)},
            )
        )

    return aggregates
