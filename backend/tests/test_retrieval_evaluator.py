"""
Tests for Phase 4.0.4 Retrieval Evaluator & Information Retrieval Metrics

Comprehensive unit tests verifying:
1. Analytical hand-calculated correctness of Precision@K (P@1, P@3, P@5)
2. Analytical hand-calculated correctness of Recall@K (R@1, R@3, R@5)
3. Analytical hand-calculated correctness of Mean Reciprocal Rank (MRR)
4. Analytical hand-calculated correctness of graded nDCG@K (nDCG@1, nDCG@3, nDCG@5)
5. Edge case handling (empty lists, fewer results than K, duplicate IDs, zero relevant docs)
6. Graded ranking quality evaluation on Phase 4.0.4 benchmark cases (CASE_036 - CASE_045)
7. Multi-evidence, distractor rejection, technology boundary, and tenant isolation behavior
"""

import math
import pytest
from typing import Dict, List
from app.evaluation.metrics import (
    calculate_precision_at_k,
    calculate_recall_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    compute_category_summary,
)
from app.evaluation.schemas import EvaluationCase, EvaluationResult
from app.evaluation.datasets import get_golden_cases, DATASET_VERSION
from app.evaluation.evaluators import evaluate_retrieval_case, evaluate_security_case


# =============================================================================
# 1. PRECISION@K ANALYTICAL TESTS
# =============================================================================

def test_precision_at_k_hand_calculated():
    """
    Test Precision@K against exact analytical hand calculation.
    
    Relevance map:
      doc_1: 3 (relevant)
      doc_2: 2 (relevant)
      doc_3: 1 (not relevant)
      doc_4: 0 (not relevant)
      doc_5: 3 (relevant)
      
    Retrieved: [doc_1, doc_2, doc_3, doc_4, doc_5]
    
    P@1: [doc_1] -> 1/1 = 1.000
    P@3: [doc_1, doc_2, doc_3] -> 2/3 ≈ 0.6667
    P@5: [doc_1, doc_2, doc_3, doc_4, doc_5] -> 3/5 = 0.600
    """
    relevance: Dict[str, int] = {
        "doc_1": 3,
        "doc_2": 2,
        "doc_3": 1,
        "doc_4": 0,
        "doc_5": 3,
    }
    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"]

    p1 = calculate_precision_at_k(retrieved, relevance, k=1, relevance_threshold=2)
    assert p1 == pytest.approx(1.0, abs=1e-5)

    p3 = calculate_precision_at_k(retrieved, relevance, k=3, relevance_threshold=2)
    assert p3 == pytest.approx(2.0 / 3.0, abs=1e-5)

    p5 = calculate_precision_at_k(retrieved, relevance, k=5, relevance_threshold=2)
    assert p5 == pytest.approx(3.0 / 5.0, abs=1e-5)


def test_precision_at_k_edge_cases():
    """Test Precision@K on edge cases."""
    relevance = {"doc_1": 3, "doc_2": 2}

    # Empty retrieval
    assert calculate_precision_at_k([], relevance, k=5) == 0.0

    # Empty relevance map
    assert calculate_precision_at_k(["doc_1"], {}, k=5) == 0.0

    # k <= 0
    assert calculate_precision_at_k(["doc_1"], relevance, k=0) == 0.0
    assert calculate_precision_at_k(["doc_1"], relevance, k=-1) == 0.0

    # Fewer retrieved items than k (denominator remains k per standard IR definition)
    # Retrieved 1 relevant doc out of k=5 -> 1/5 = 0.2
    assert calculate_precision_at_k(["doc_1"], relevance, k=5) == pytest.approx(0.2, abs=1e-5)

    # Duplicate IDs in retrieved list do not inflate precision
    assert calculate_precision_at_k(["doc_1", "doc_1", "doc_1"], relevance, k=3) == pytest.approx(1.0 / 3.0, abs=1e-5)

    # No relevant items retrieved
    assert calculate_precision_at_k(["doc_unknown", "doc_unrelated"], relevance, k=2) == 0.0


# =============================================================================
# 2. RECALL@K ANALYTICAL TESTS
# =============================================================================

def test_recall_at_k_hand_calculated():
    """
    Test Recall@K against exact analytical hand calculation.
    
    Relevance map:
      doc_1: 3 (relevant)
      doc_2: 2 (relevant)
      doc_3: 1 (not relevant)
      doc_4: 0 (not relevant)
      doc_5: 3 (relevant)
      
    Total relevant in ground truth = 3 (doc_1, doc_2, doc_5).
    
    Retrieved: [doc_1, doc_2, doc_3, doc_4, doc_5]
    
    R@1: 1 relevant retrieved / 3 total = 1/3 ≈ 0.3333
    R@3: 2 relevant retrieved / 3 total = 2/3 ≈ 0.6667
    R@5: 3 relevant retrieved / 3 total = 3/3 = 1.000
    """
    relevance: Dict[str, int] = {
        "doc_1": 3,
        "doc_2": 2,
        "doc_3": 1,
        "doc_4": 0,
        "doc_5": 3,
    }
    retrieved = ["doc_1", "doc_2", "doc_3", "doc_4", "doc_5"]

    r1 = calculate_recall_at_k(retrieved, relevance, k=1, relevance_threshold=2)
    assert r1 == pytest.approx(1.0 / 3.0, abs=1e-5)

    r3 = calculate_recall_at_k(retrieved, relevance, k=3, relevance_threshold=2)
    assert r3 == pytest.approx(2.0 / 3.0, abs=1e-5)

    r5 = calculate_recall_at_k(retrieved, relevance, k=5, relevance_threshold=2)
    assert r5 == pytest.approx(1.0, abs=1e-5)


def test_recall_at_k_edge_cases():
    """Test Recall@K edge cases."""
    # Zero relevant items in ground truth
    zero_rel = {"doc_1": 1, "doc_2": 0}
    assert calculate_recall_at_k(["doc_1"], zero_rel, k=5) == 1.0

    # k <= 0
    rel = {"doc_1": 3}
    assert calculate_recall_at_k(["doc_1"], rel, k=0) == 0.0

    # Duplicate IDs do not double count recall
    assert calculate_recall_at_k(["doc_1", "doc_1"], rel, k=2) == pytest.approx(1.0, abs=1e-5)


# =============================================================================
# 3. MEAN RECIPROCAL RANK (MRR) ANALYTICAL TESTS
# =============================================================================

def test_mrr_hand_calculated():
    """
    Test MRR for various first-relevant rank positions.
    """
    relevance = {"doc_rel": 3, "doc_irrel": 0}

    # Rank 1 -> 1/1 = 1.0
    assert calculate_mrr(["doc_rel", "doc_irrel"], relevance) == pytest.approx(1.0, abs=1e-5)

    # Rank 2 -> 1/2 = 0.5
    assert calculate_mrr(["doc_irrel", "doc_rel"], relevance) == pytest.approx(0.5, abs=1e-5)

    # Rank 3 -> 1/3 ≈ 0.33333
    assert calculate_mrr(["doc_irrel", "doc_other", "doc_rel"], relevance) == pytest.approx(1.0 / 3.0, abs=1e-5)

    # Rank 4 -> 1/4 = 0.25
    assert calculate_mrr(["d1", "d2", "d3", "doc_rel"], relevance) == pytest.approx(0.25, abs=1e-5)

    # No relevant result -> 0.0
    assert calculate_mrr(["doc_irrel", "doc_other"], relevance) == 0.0

    # Empty list -> 0.0
    assert calculate_mrr([], relevance) == 0.0


# =============================================================================
# 4. nDCG@K ANALYTICAL TESTS
# =============================================================================

def test_ndcg_at_k_hand_calculated():
    """
    Test nDCG@K against exact analytical logarithmic calculations.
    
    Relevance map:
      doc_1: 3
      doc_2: 2
      doc_3: 1
      doc_4: 0
      
    Formula:
      DCG@K = sum_{i=1}^K ((2^{rel_i} - 1) / log2(i + 1))
      
    Ideal ordering: [doc_1 (3), doc_2 (2), doc_3 (1), doc_4 (0)]
      IDCG@1 = (2^3 - 1)/log2(2) = 7.0 / 1.0 = 7.0
      IDCG@3 = 7.0/1.0 + (2^2 - 1)/log2(3) + (2^1 - 1)/log2(4)
             = 7.0 + 3.0/1.5849625 + 1.0/2.0
             = 7.0 + 1.892789 + 0.5 = 9.392789
    """
    relevance = {"doc_1": 3, "doc_2": 2, "doc_3": 1, "doc_4": 0}

    # Case A: Perfect ranking [doc_1, doc_2, doc_3, doc_4]
    perfect = ["doc_1", "doc_2", "doc_3", "doc_4"]
    assert calculate_ndcg_at_k(perfect, relevance, k=1) == pytest.approx(1.0, abs=1e-5)
    assert calculate_ndcg_at_k(perfect, relevance, k=3) == pytest.approx(1.0, abs=1e-5)
    assert calculate_ndcg_at_k(perfect, relevance, k=5) == pytest.approx(1.0, abs=1e-5)

    # Case B: Suboptimal reverse ranking [doc_3 (1), doc_2 (2), doc_1 (3), doc_4 (0)]
    suboptimal = ["doc_3", "doc_2", "doc_1", "doc_4"]
    
    # DCG@1 = (2^1 - 1)/log2(2) = 1.0
    # nDCG@1 = 1.0 / 7.0 ≈ 0.142857
    ndcg1 = calculate_ndcg_at_k(suboptimal, relevance, k=1)
    assert ndcg1 == pytest.approx(1.0 / 7.0, abs=1e-5)

    # DCG@3 = 1.0/1.0 + 3.0/log2(3) + 7.0/log2(4) = 1.0 + 1.892789 + 3.5 = 6.392789
    # nDCG@3 = 6.392789 / 9.392789 ≈ 0.680606
    ndcg3 = calculate_ndcg_at_k(suboptimal, relevance, k=3)
    expected_ndcg3 = (1.0 + 3.0 / math.log2(3) + 7.0 / math.log2(4)) / (7.0 + 3.0 / math.log2(3) + 1.0 / math.log2(4))
    assert ndcg3 == pytest.approx(expected_ndcg3, abs=1e-5)


def test_ndcg_edge_cases():
    """Test nDCG edge cases."""
    # Zero positive relevance in ground truth
    zero_rel = {"doc_1": 0, "doc_2": 0}
    assert calculate_ndcg_at_k(["doc_1", "doc_2"], zero_rel, k=5) == 1.0

    # k <= 0
    rel = {"doc_1": 3}
    assert calculate_ndcg_at_k(["doc_1"], rel, k=0) == 0.0

    # Empty retrieved
    assert calculate_ndcg_at_k([], rel, k=3) == 0.0


# =============================================================================
# 5. PHASE 4.0.4 BENCHMARK CASES EVALUATION
# =============================================================================

def test_case_036_graded_ranking_quality():
    """CASE_036: Evaluates that Exact (3) > Supporting (2) > Peripheral (1) > Irrelevant (0) produces high nDCG."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_036")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["ndcg_at_1"] == pytest.approx(1.0, abs=1e-2)
    assert res.metrics["ndcg_at_3"] >= 0.85
    assert res.metrics["p_at_1"] == 1.0
    assert res.metrics["mrr"] == 1.0


def test_case_037_multi_evidence_retrieval():
    """CASE_037: Evaluates retrieval of multiple genuine relevant items across backend and database."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_037")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["hit_rate"] == 1.0
    assert res.metrics["r_at_3"] >= 0.50
    assert res.metrics["r_at_5"] >= 0.66
    assert res.metrics["p_at_1"] == 1.0


def test_case_038_hard_keyword_distractor_rejection():
    """CASE_038: Evaluates rejection of 'JavaScript' and 'Java coffee shop' distractors for Java query."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_038")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["hit_rate"] == 1.0
    assert res.metrics["false_positive_count"] == 0.0


def test_case_039_technology_boundary_react():
    """CASE_039: Verifies Angular or Vue cannot satisfy React requirement as direct match."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_039")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["match_class_accuracy"] == 1.0


def test_case_040_technology_boundary_docker():
    """CASE_040: Verifies Docker containerization boundary vs Kubernetes/Terraform."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_040")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["match_class_accuracy"] == 1.0


def test_case_041_recency_metrics_ranking():
    """CASE_041: Verifies recent verified achievement ranks above older role."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_041")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["p_at_1"] == 1.0
    assert res.metrics["mrr"] == 1.0


def test_case_042_deterministic_tie_breaking():
    """CASE_042: Verifies tie-breaking between equivalent quality project evidence."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_042")
    res1 = evaluate_retrieval_case(case)
    res2 = evaluate_retrieval_case(case)
    assert res1.passed is True
    assert res1.actual["retrievedIds"] == res2.actual["retrievedIds"]


def test_case_043_missing_requirement_abstention():
    """CASE_043: Verifies candidate lacking Rust requirement correctly flags related_but_unverified."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_043")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.actual["matchClasses"].get("Rust") == "related_but_unverified"


def test_case_044_multi_role_cross_experience():
    """CASE_044: Verifies multi-role cross-experience retrieval covering full-stack requirements."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_044")
    res = evaluate_retrieval_case(case)
    assert res.passed is True
    assert res.metrics["hit_rate"] == 1.0


def test_case_045_tenant_isolated_retrieval():
    """CASE_045: Proves evaluating user cannot retrieve candidate evidence belonging to another tenant."""
    cases = get_golden_cases()
    case = next(c for c in cases if c.case_id == "CASE_045")
    res = evaluate_security_case(case)
    assert res.passed is True
    assert res.metrics.get("unauthorized_leak_count", 0.0) == 0.0
