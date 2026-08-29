import re
from typing import List, Set, Tuple
from app.schemas.remediation import ValidationResult, UnsupportedClaim, ClaimCategory
from app.ai.skills import normalize_skill_name

METRIC_NUMBER_PATTERN = re.compile(
    r"(\d+(\.\d+)?%|\$\d+(\.\d+)?|\b\d+\+?(\s*(years?|months?|users?|clients?|engineers?|developers?|members?|requests?|transactions?|services?|nodes?|clusters?|rps|qps|ms|s|gb|tb|pb|m|k|b))\b|\b(99\.\d+%)\b)",
    re.IGNORECASE,
)

LEADERSHIP_PATTERNS = re.compile(
    r"\b(led|lead|leading|managed|managing|mentored|mentoring|directed|directing|spearheaded|oversaw|headed|founded)\b",
    re.IGNORECASE,
)

TEAM_SIZE_PATTERN = re.compile(
    r"\b(team of \d+|\d+\s*(engineers?|developers?|direct reports?|team members?))\b",
    re.IGNORECASE,
)

SCALE_TERMS = {
    "enterprise",
    "multi-region",
    "global",
    "mission-critical",
    "high-availability",
    "petabyte",
    "terabyte",
}


def extract_numbers_and_metrics(text: str) -> Set[str]:
    """Extracts normalized metrics, percentages, and numerical quantities from text."""
    if not text:
        return set()
    matches = METRIC_NUMBER_PATTERN.findall(text)
    results = set()
    for m in matches:
        if isinstance(m, tuple):
            val = m[0]
        else:
            val = m
        if val and val.strip():
            results.add(re.sub(r"\s+", " ", val.strip().lower()))
    return results


def extract_leadership_claims(text: str) -> bool:
    """Checks if text claims leadership, management, or mentorship."""
    if not text:
        return False
    return bool(LEADERSHIP_PATTERNS.search(text))


def extract_team_size_claims(text: str) -> Set[str]:
    """Extracts team size or direct report numbers."""
    if not text:
        return set()
    matches = TEAM_SIZE_PATTERN.findall(text)
    results = set()
    for m in matches:
        val = m[0] if isinstance(m, tuple) else m
        if val and val.strip():
            results.add(val.strip().lower())
    return results


def validate_claims_against_source(
    proposed_bullet: str,
    source_evidence: str,
) -> ValidationResult:
    """
    Deterministically compares proposed rewritten bullet against source evidence or user facts.
    Detects ungrounded metrics, leadership inflation, invented team sizes, and enterprise scale.
    """
    if not proposed_bullet or not proposed_bullet.strip():
        return ValidationResult(is_valid=True, status="Validated", sanitized_bullet="")

    unsupported: List[UnsupportedClaim] = []
    source_clean = source_evidence or ""

    # 1. Metric / Number Validation
    source_metrics = extract_numbers_and_metrics(source_clean)
    proposed_metrics = extract_numbers_and_metrics(proposed_bullet)

    for metric in proposed_metrics:
        # Check if metric or the base number appears in source text
        base_num = re.search(r"\d+", metric)
        if base_num:
            num_str = base_num.group(0)
            if num_str not in source_clean:
                unsupported.append(
                    UnsupportedClaim(
                        category="Metric",
                        claim_text=metric,
                        reason=f"The metric '{metric}' does not appear in your verified evidence.",
                        prompt_for_user=f"What was the actual measurable impact, metric, or scale for this achievement?",
                    )
                )

    # 2. Leadership / Management Validation
    source_has_leadership = extract_leadership_claims(source_clean)
    proposed_has_leadership = extract_leadership_claims(proposed_bullet)
    if proposed_has_leadership and not source_has_leadership:
        unsupported.append(
            UnsupportedClaim(
                category="SeniorityRole",
                claim_text="Leadership / Management Role",
                reason="Introduced leadership responsibility (e.g. leading/managing) not present in original evidence.",
                prompt_for_user="Did you lead or manage other engineers on this project? If so, what were your responsibilities?",
            )
        )

    # 3. Team Size Validation
    source_team_sizes = extract_team_size_claims(source_clean)
    proposed_team_sizes = extract_team_size_claims(proposed_bullet)
    for team_claim in proposed_team_sizes:
        if team_claim not in source_clean and not source_team_sizes:
            unsupported.append(
                UnsupportedClaim(
                    category="TeamOrganization",
                    claim_text=team_claim,
                    reason=f"Introduced team size '{team_claim}' not verified in candidate evidence.",
                    prompt_for_user="How many engineers or contributors were on your team for this project?",
                )
            )

    # 4. Scale & Environment Validation
    norm_source_lower = source_clean.lower()
    norm_proposed_lower = proposed_bullet.lower()
    for scale_term in SCALE_TERMS:
        if scale_term in norm_proposed_lower and scale_term not in norm_source_lower:
            unsupported.append(
                UnsupportedClaim(
                    category="Scale",
                    claim_text=scale_term,
                    reason=f"Introduced enterprise scale/infrastructure environment claim '{scale_term}' not verified in candidate evidence.",
                    prompt_for_user=f"Did your work operate in a {scale_term} environment? If so, please specify the architecture details.",
                )
            )

    # 5. Synthesize final validation result
    is_valid = len(unsupported) == 0
    status = "Validated" if is_valid else "RequiresCandidateInput"
    sanitized_bullet = proposed_bullet.strip()

    return ValidationResult(
        is_valid=is_valid,
        status=status,
        unsupported_claims=unsupported,
        sanitized_bullet=sanitized_bullet,
    )
