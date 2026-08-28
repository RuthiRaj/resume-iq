import pytest
from app.ai.scoring import calculate_deterministic_ats_score, reconcile_score_breakdown
from app.schemas.common import ScoreBreakdown


def test_scoring_all_max_scores_yields_100():
    score = calculate_deterministic_ats_score(100, 100, 100, 100)
    assert score == 100


def test_scoring_all_zero_scores_yields_0():
    score = calculate_deterministic_ats_score(0, 0, 0, 0)
    assert score == 0


def test_scoring_reconciled_weights_example_1():
    # 80*0.4 (32) + 60*0.3 (18) + 40*0.15 (6) + 20*0.15 (3) = 59
    score = calculate_deterministic_ats_score(80, 60, 40, 20)
    assert score == 59


def test_scoring_reconciled_weights_example_2():
    # 40*0.4 (16) + 30*0.3 (9) + 15*0.15 (2.25) + 15*0.15 (2.25) = 29.5 -> rounds to 30
    score = calculate_deterministic_ats_score(40, 30, 15, 15)
    assert score == 30


def test_scoring_reconciled_weights_example_3():
    # 90*0.4 (36) + 85*0.3 (25.5) + 70*0.15 (10.5) + 80*0.15 (12) = 84.0 -> 84
    score = calculate_deterministic_ats_score(90, 85, 70, 80)
    assert score == 84


def test_scoring_clamping_out_of_bounds():
    # Negative values clamped to 0
    assert calculate_deterministic_ats_score(-10, -50, 0, 0) == 0
    # Values > 100 clamped to 100
    assert calculate_deterministic_ats_score(150, 200, 100, 100) == 100


def test_reconcile_score_breakdown_helper():
    breakdown = ScoreBreakdown(relevance=75, keywords=80, metrics=65, formatting=90)
    # 75*0.4 (30) + 80*0.3 (24) + 65*0.15 (9.75) + 90*0.15 (13.5) = 77.25 -> 77
    score = reconcile_score_breakdown(breakdown)
    assert score == 77
