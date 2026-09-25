"""
Metrics Aggregation Engine for ResumeIQ Phase 4.0.4 AI Evaluation Framework

Computes granular Information Retrieval and ranking metrics:
- Precision@K (P@1, P@3, P@5)
- Recall@K (R@1, R@3, R@5)
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (nDCG@1, nDCG@3, nDCG@5)
- Hit Rate (Hit@K)
- Aggregated rates across task categories (retrieval, grounding, planning, security, determinism)

All metric calculations are pure, deterministic, and 100% offline.
"""

import math
from typing import List, Dict, Any, Optional, Set
from app.evaluation.schemas import EvaluationResult, CategorySummary


def calculate_precision_at_k(
    retrieved_ids: List[str],
    graded_relevance: Dict[str, int],
    k: int = 5,
    relevance_threshold: int = 2,
) -> float:
    """
    Computes Precision@K: (number of relevant retrieved results in top K) / K.

    Binary relevance definition:
    - relevance >= relevance_threshold (default: 2) -> Relevant
    - relevance < relevance_threshold -> Not relevant

    Handles:
    - k <= 0 returns 0.0
    - Fewer than K retrieved items (denominator remains K per standard IR definition)
    - Deduplicates retrieved IDs in rank order to prevent duplicate inflation
    - Empty retrieval or empty relevance dict returns 0.0
    """
    if k <= 0:
        return 0.0
    if not retrieved_ids or not graded_relevance:
        return 0.0

    seen: Set[str] = set()
    deduped_top_k: List[str] = []
    for item_id in retrieved_ids:
        if item_id not in seen:
            seen.add(item_id)
            deduped_top_k.append(item_id)
        if len(deduped_top_k) == k:
            break

    relevant_count = sum(
        1 for item_id in deduped_top_k
        if graded_relevance.get(item_id, 0) >= relevance_threshold
    )
    return float(relevant_count) / float(k)


def calculate_recall_at_k(
    retrieved_ids: List[str],
    graded_relevance: Dict[str, int],
    k: int = 5,
    relevance_threshold: int = 2,
) -> float:
    """
    Computes Recall@K: (number of relevant retrieved results in top K) / (total relevant items).

    Binary relevance definition:
    - relevance >= relevance_threshold (default: 2) -> Relevant
    - relevance < relevance_threshold -> Not relevant

    Handles:
    - Zero relevant evidence items in ground truth: returns 1.0 if 0 relevant retrieved, else 0.0
    - Deduplicates retrieved IDs in rank order
    - Bounded to [0.0, 1.0]
    """
    if k <= 0:
        return 0.0

    total_relevant = sum(
        1 for rel in graded_relevance.values()
        if rel >= relevance_threshold
    )

    seen: Set[str] = set()
    deduped_top_k: List[str] = []
    for item_id in retrieved_ids:
        if item_id not in seen:
            seen.add(item_id)
            deduped_top_k.append(item_id)
        if len(deduped_top_k) == k:
            break

    relevant_retrieved = sum(
        1 for item_id in deduped_top_k
        if graded_relevance.get(item_id, 0) >= relevance_threshold
    )

    if total_relevant == 0:
        return 1.0 if relevant_retrieved == 0 else 0.0

    return min(1.0, float(relevant_retrieved) / float(total_relevant))


def calculate_mrr(
    retrieved_ids: List[str],
    graded_relevance: Dict[str, int],
    relevance_threshold: int = 2,
) -> float:
    """
    Computes Reciprocal Rank for a single query: 1 / rank of the first relevant result.

    Binary relevance definition:
    - relevance >= relevance_threshold (default: 2) -> Relevant

    Rank is 1-indexed (e.g. rank 1 -> 1.0, rank 2 -> 0.5, rank 3 -> 0.3333).
    Returns 0.0 if no relevant item is retrieved in the ranked list.
    """
    if not retrieved_ids or not graded_relevance:
        return 0.0

    seen: Set[str] = set()
    rank = 1
    for item_id in retrieved_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        if graded_relevance.get(item_id, 0) >= relevance_threshold:
            return 1.0 / float(rank)
        rank += 1

    return 0.0


def calculate_ndcg_at_k(
    retrieved_ids: List[str],
    graded_relevance: Dict[str, int],
    k: int = 5,
) -> float:
    """
    Computes Normalized Discounted Cumulative Gain at K (nDCG@K) using graded relevance.

    Formula:
      DCG@K = sum_{i=1}^{min(k, len(results))} ((2^{rel_i} - 1) / log2(i + 1))
      IDCG@K = sum_{i=1}^{min(k, len(ideal))} ((2^{ideal_rel_i} - 1) / log2(i + 1))
      nDCG@K = DCG@K / IDCG@K

    Relevance scale:
      3 = Core / Exact Match
      2 = Supporting Domain Evidence
      1 = Peripheral / Related Evidence
      0 = Irrelevant / Distractor

    If IDCG@K == 0.0:
      returns 1.0 if DCG@K == 0.0 (perfect retrieval of zero gain), else 0.0.
    """
    if k <= 0:
        return 0.0

    seen: Set[str] = set()
    deduped_retrieved: List[str] = []
    for item_id in retrieved_ids:
        if item_id not in seen:
            seen.add(item_id)
            deduped_retrieved.append(item_id)

    # 1. Compute DCG@K
    dcg = 0.0
    for idx, item_id in enumerate(deduped_retrieved[:k]):
        rel = graded_relevance.get(item_id, 0)
        if rel > 0:
            dcg += (math.pow(2.0, rel) - 1.0) / math.log2(idx + 2.0)

    # 2. Compute IDCG@K from ideal ordering of all available positive relevance scores
    positive_rels = sorted([r for r in graded_relevance.values() if r > 0], reverse=True)[:k]
    idcg = 0.0
    for idx, rel in enumerate(positive_rels):
        idcg += (math.pow(2.0, rel) - 1.0) / math.log2(idx + 2.0)

    if idcg == 0.0:
        return 1.0 if dcg == 0.0 else 0.0

    return min(1.0, dcg / idcg)


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
