"""
ResumeIQ Golden Evaluation Dataset Package
"""

from evaluation.dataset.golden_cases import (
    GOLDEN_BENCHMARK_CASES,
    get_golden_cases,
    get_case_by_id,
)

__all__ = ["GOLDEN_BENCHMARK_CASES", "get_golden_cases", "get_case_by_id"]
