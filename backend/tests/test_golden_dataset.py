"""
Tests for ResumeIQ Golden Evaluation Dataset Integrity

Validates that:
- Benchmark dataset contains ~15 benchmark cases.
- Total requirement observations count is between 50 and 75.
- All case IDs are unique and match regex pattern ^[a-zA-Z0-9_\\-]+$.
- All ground truth requirement fields and enums are strictly valid.
- Prompt injection benchmark cases contain actual injection attack payloads.
- Expected min/max ATS scores remain None across benchmark cases.
- Helper functions get_golden_cases() and get_case_by_id() operate correctly.
"""

import pytest
import re
from evaluation.dataset import (
    GOLDEN_BENCHMARK_CASES,
    get_golden_cases,
    get_case_by_id,
)


def test_golden_dataset_case_count():
    """Verify that dataset contains exactly 15 benchmark cases."""
    cases = get_golden_cases()
    assert len(cases) == 15, f"Expected 15 benchmark cases, got {len(cases)}"


def test_unique_and_valid_case_ids():
    """Verify all case IDs are unique and conform to standard ID pattern."""
    case_ids = [c.case_id for c in get_golden_cases()]
    assert len(case_ids) == len(set(case_ids)), "Duplicate case_id found in golden dataset!"

    id_pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")
    for case_id in case_ids:
        assert id_pattern.match(case_id), f"Case ID '{case_id}' violates pattern rules!"


def test_total_ground_truth_requirement_count():
    """Verify total requirement count is within the target 50 to 75 range."""
    cases = get_golden_cases()
    total_reqs = sum(len(c.ground_truth_requirements) for c in cases)
    assert 50 <= total_reqs <= 75, (
        f"Total ground truth requirements count ({total_reqs}) is outside expected 50-75 range!"
    )


def test_requirement_field_integrity():
    """Verify all requirement names, match statuses, provenances, and gap types are valid."""
    valid_statuses = {"StrongMatch", "PartialMatch", "Missing"}
    valid_provenances = {"Experience", "Project", "SkillTag", "Education", "Certification", "Summary", "None"}
    valid_gap_types = {
        "None",
        "MissingEvidence",
        "InsufficientContext",
        "MissingProductionExperience",
        "InsufficientExperienceYears",
        "MissingQuantification",
        "AdjacentTechnology",
        "MissingSeniority",
        "MissingProjectEvidence",
        "MissingCertification",
        "ContradictoryEvidence",
    }

    for case in get_golden_cases():
        assert len(case.ground_truth_requirements) >= 1, f"Case {case.case_id} has no requirements!"
        for req in case.ground_truth_requirements:
            assert len(req.requirement_name) > 0, f"Empty requirement name in case {case.case_id}"
            assert req.expected_match_status in valid_statuses, (
                f"Invalid match status '{req.expected_match_status}' in case {case.case_id}"
            )
            if req.expected_provenance is not None:
                assert req.expected_provenance in valid_provenances, (
                    f"Invalid provenance '{req.expected_provenance}' in case {case.case_id}"
                )
            if req.expected_gap_type is not None:
                assert req.expected_gap_type in valid_gap_types, (
                    f"Invalid gap type '{req.expected_gap_type}' in case {case.case_id}"
                )


def test_prompt_injection_cases_contain_injection_payloads():
    """Verify prompt injection cases contain explicit adversarial instructions."""
    jd_case = get_case_by_id("case_013_prompt_injection_jd")
    assert jd_case is not None
    assert "SYSTEM OVERRIDE" in jd_case.input.job_description

    resume_case = get_case_by_id("case_014_prompt_injection_resume")
    assert resume_case is not None
    summary = resume_case.input.candidate_evidence.summary or ""
    assert "[System Note:" in summary or "SYSTEM OVERRIDE" in summary


def test_ats_score_bounds_are_none():
    """Verify expected_min_ats_score and expected_max_ats_score are None across all benchmark cases."""
    for case in get_golden_cases():
        assert case.expected_min_ats_score is None, (
            f"Case {case.case_id} has non-None min ATS score: {case.expected_min_ats_score}"
        )
        assert case.expected_max_ats_score is None, (
            f"Case {case.case_id} has non-None max ATS score: {case.expected_max_ats_score}"
        )


def test_get_case_by_id_helper():
    """Verify get_case_by_id returns correct case or None if missing."""
    case = get_case_by_id("case_001_exact_match")
    assert case is not None
    assert case.case_id == "case_001_exact_match"
    assert case.title.startswith("Senior Python")

    missing = get_case_by_id("non_existent_case_id")
    assert missing is None
