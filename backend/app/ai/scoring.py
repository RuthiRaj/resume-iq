from typing import Union
from app.schemas.common import ScoreBreakdown


def calculate_deterministic_ats_score(
    relevance: Union[int, float],
    keywords: Union[int, float],
    metrics: Union[int, float],
    formatting: Union[int, float],
) -> int:
    """
    Calculates the authoritative, deterministic ATS Readiness Score (0-100)
    using the mathematically reconciled weighting:
      - Relevance:  40%
      - Keywords:   30%
      - Metrics:    15%
      - Formatting: 15%
    Clamps inputs to [0, 100] and rounds to nearest integer.
    """
    rel = max(0.0, min(100.0, float(relevance)))
    kw = max(0.0, min(100.0, float(keywords)))
    met = max(0.0, min(100.0, float(metrics)))
    fmt = max(0.0, min(100.0, float(formatting)))

    weighted_total = (rel * 0.40) + (kw * 0.30) + (met * 0.15) + (fmt * 0.15)
    return int(round(weighted_total))


def reconcile_score_breakdown(score_breakdown: ScoreBreakdown) -> int:
    """Convenience helper to compute deterministic ATS score from a ScoreBreakdown schema."""
    return calculate_deterministic_ats_score(
        relevance=score_breakdown.relevance,
        keywords=score_breakdown.keywords,
        metrics=score_breakdown.metrics,
        formatting=score_breakdown.formatting,
    )
