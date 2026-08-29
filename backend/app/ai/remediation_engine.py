import hashlib
from typing import List, Optional, Tuple, Dict
from app.schemas.candidate import CandidateEvidence
from app.schemas.requirement_match import RequirementMatch, GapType, EvidenceSourceSection
from app.schemas.remediation import (
    RemediationSuggestion,
    RemediationEligibility,
    RemediationActionType,
    RemediationStatus,
    ValidationResult,
)
from app.ai.grounding import normalize_for_grounding, is_grounded_in_text
from app.ai.claim_validator import validate_claims_against_source
from app.ai.skills import normalize_skill_name


def generate_source_evidence_id(
    section: EvidenceSourceSection,
    experience_id: Optional[str],
    evidence_text: Optional[str],
) -> str:
    """Generates a stable, deterministic hash identifier for the source evidence to prevent stale edits."""
    norm_text = normalize_for_grounding(evidence_text or "")
    payload = f"{section}:{experience_id or 'none'}:{norm_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def locate_bullet_in_candidate_evidence(
    snippet: str, candidate_evidence: CandidateEvidence
) -> Tuple[str, Optional[int]]:
    """
    Locates the matching experience ID and bullet index in the candidate's experience list.
    """
    if not snippet or not snippet.strip():
        return "", None

    norm_snippet = normalize_for_grounding(snippet)

    for exp_idx, exp in enumerate(candidate_evidence.experience):
        exp_id = f"exp_{exp_idx}"
        for b_idx, bullet in enumerate(exp.bullets):
            if is_grounded_in_text(norm_snippet, bullet) or is_grounded_in_text(bullet, norm_snippet):
                return exp_id, b_idx

    for proj_idx, proj in enumerate(candidate_evidence.projects):
        proj_id = f"proj_{proj_idx}"
        for h_idx, hl in enumerate(proj.highlights):
            if is_grounded_in_text(norm_snippet, hl) or is_grounded_in_text(hl, norm_snippet):
                return proj_id, h_idx

    return "", None


def determine_remediation_eligibility_and_action(
    match_status: str,
    gap_type: GapType,
    provenance: EvidenceSourceSection,
    importance: str,
) -> Tuple[RemediationEligibility, RemediationActionType, str]:
    """
    Deterministically determines remediation eligibility, action type, and potential impact.
    The backend is the sole authority—the LLM cannot override these rules.
    """
    if match_status == "StrongMatch":
        return "Remediable", "None", "Low"

    # Hard experience gaps (e.g. 10+ years required vs 3 years actual)
    if gap_type == "InsufficientExperienceYears" or gap_type == "MissingSeniority":
        return "NotRemediable", "ExplainHardGap", "Low"

    # Standalone Skill Tag needing real production context
    if gap_type == "MissingProductionExperience" or provenance == "SkillTag":
        impact = "High" if importance == "MustHave" else "Medium"
        return "RequiresCandidateFacts", "AddProjectContext", impact

    # Missing Evidence completely
    if match_status == "Missing" or gap_type == "MissingEvidence" or provenance == "None":
        impact = "High" if importance == "MustHave" else "Medium"
        return "RequiresCandidateFacts", "PromptForMissingFacts", impact

    # Adjacent technology
    if gap_type == "AdjacentTechnology":
        return "PartiallyRemediable", "ClarifyAdjacentTechnology", "Medium"

    # Existing bullet with missing quantification or context
    if gap_type in ("MissingQuantification", "InsufficientContext") or provenance in ("Experience", "Project"):
        impact = "High" if importance == "MustHave" else "Medium"
        return "Remediable", "ImproveExistingBullet", impact

    return "Remediable", "ImproveExistingBullet", "Medium"


def construct_remediation_suggestion(
    match: RequirementMatch,
    candidate_evidence: CandidateEvidence,
    proposed_bullet: Optional[str] = None,
) -> Optional[RemediationSuggestion]:
    """
    Constructs a deterministic, truth-preserving RemediationSuggestion for a given RequirementMatch.
    Enforces the Truthfulness Boundary and runs Claim Preservation Validation.
    """
    # Strong matches do not require remediation
    if match.match_status == "StrongMatch":
        return None

    norm_name = normalize_skill_name(match.requirement_name)
    eligibility, action_type, potential_impact = determine_remediation_eligibility_and_action(
        match_status=match.match_status,
        gap_type=match.gap_type,
        provenance=match.evidence_source_section,
        importance=match.importance,
    )

    exp_id, bullet_idx = locate_bullet_in_candidate_evidence(
        match.resume_evidence or "", candidate_evidence
    )
    source_evidence_id = generate_source_evidence_id(
        section=match.evidence_source_section,
        experience_id=exp_id,
        evidence_text=match.resume_evidence,
    )

    rem_id = f"rem_{source_evidence_id}_{hashlib.md5(norm_name.encode()).hexdigest()[:6]}"

    # Truthfulness Boundary Enforcement:
    # If action_type requires candidate facts, suggested_bullet MUST BE EMPTY!
    if action_type in ("PromptForMissingFacts", "AddProjectContext", "ExplainHardGap"):
        suggested_bullet = ""
        if action_type == "ExplainHardGap":
            guidance = f"The job demands greater experience duration or seniority than evidenced. This gap cannot be bridged through bullet phrasing alone."
            missing_fact_prompt = ""
        elif action_type == "AddProjectContext":
            guidance = f"{norm_name} is currently listed in your skills without supporting work bullets. Add concrete project or work details demonstrating how you applied it."
            missing_fact_prompt = f"How and where have you applied {norm_name} in your work experience or projects? Describe your responsibilities and outcomes."
        else:
            guidance = f"No verified evidence of {norm_name} was found in your resume snapshot."
            missing_fact_prompt = f"If you have hands-on experience with {norm_name}, provide brief notes describing your project context and responsibilities."

        return RemediationSuggestion(
            id=rem_id,
            requirement_name=norm_name,
            importance=match.importance,
            gap_type=match.gap_type,
            eligibility=eligibility,
            action_type=action_type,
            target_section=match.evidence_source_section,
            source_evidence_id=source_evidence_id,
            original_evidence=match.resume_evidence or "",
            target_experience_id=exp_id,
            target_bullet_index=bullet_idx,
            suggested_bullet="",
            missing_fact_prompt=missing_fact_prompt,
            guidance=guidance,
            potential_impact=potential_impact,
            status="Draft",
            validation=ValidationResult(is_valid=True, status="Validated", sanitized_bullet=""),
        )

    # For ImproveExistingBullet or ClarifyAdjacentTechnology: Validate proposed bullet against source evidence
    raw_proposed = proposed_bullet.strip() if proposed_bullet and proposed_bullet.strip() else match.resume_evidence or ""
    validation_res = validate_claims_against_source(
        proposed_bullet=raw_proposed,
        source_evidence=match.resume_evidence or "",
    )

    if action_type == "ClarifyAdjacentTechnology":
        guidance = f"Clarify how your experience with {match.resume_evidence or 'adjacent tech'} directly translates to {norm_name}."
    elif match.gap_type == "MissingQuantification":
        guidance = f"Add measurable impact, scale, or metrics (e.g. latency %, requests/sec, user volume) to your {norm_name} bullet."
    else:
        guidance = f"Strengthen the technical scope and concrete outcomes of your {norm_name} bullet."

    return RemediationSuggestion(
        id=rem_id,
        requirement_name=norm_name,
        importance=match.importance,
        gap_type=match.gap_type,
        eligibility=eligibility,
        action_type=action_type,
        target_section=match.evidence_source_section,
        source_evidence_id=source_evidence_id,
        original_evidence=match.resume_evidence or "",
        target_experience_id=exp_id,
        target_bullet_index=bullet_idx,
        suggested_bullet=raw_proposed,
        missing_fact_prompt="",
        guidance=guidance,
        potential_impact=potential_impact,
        status=validation_res.status,
        validation=validation_res,
    )


def generate_remediation_suggestions(
    matches: List[RequirementMatch],
    candidate_evidence: CandidateEvidence,
    proposed_rewrites_by_name: Optional[Dict[str, str]] = None,
) -> List[RemediationSuggestion]:
    """Generates and validates remediation suggestions for all non-strong requirement matches."""
    proposed_rewrites = proposed_rewrites_by_name or {}
    suggestions: List[RemediationSuggestion] = []

    for m in matches:
        norm_name = normalize_skill_name(m.requirement_name)
        proposed_text = proposed_rewrites.get(norm_name)
        sug = construct_remediation_suggestion(
            match=m,
            candidate_evidence=candidate_evidence,
            proposed_bullet=proposed_text,
        )
        if sug:
            suggestions.append(sug)

    return suggestions
