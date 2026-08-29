import re
from typing import List, Dict, Optional, Tuple
from app.schemas.candidate import CandidateEvidence
from app.schemas.job_description import StructuredJobDescription, SkillRequirement
from app.schemas.requirement_match import (
    RequirementMatch,
    EvidenceDimensions,
    GapType,
    EvidenceSourceSection,
)
from app.ai.skills import normalize_skill_name, normalize_skill_category

METRIC_PATTERNS = re.compile(
    r"(\d+(\.\d+)?%|\$\d+(\.\d+)?|\d+\+?(\s*(years|months|users|clients|engineers|developers|members|people|contributors|requests|transactions|services|nodes|clusters|rps|qps|ms|s|gb|tb|pb|m|k|b))\b|\b(latency|throughput|reduced|improved|increased|optimized|scaled|slas?|99\.\d+%)\b)",
    re.IGNORECASE,
)

DEEP_REQUIREMENT_PATTERNS = re.compile(
    r"\b(\d+\+?\s*years?|production|expert|expertise|architect(ed|ing|ure)?|lead(ing)?|scale|scaling|deep|advanced|senior)\b",
    re.IGNORECASE,
)

YEARS_PATTERN = re.compile(r"\b(\d+)\+?\s*years?\b", re.IGNORECASE)


def normalize_for_grounding(text: str) -> str:
    """Standardizes whitespace, casing, and common unicode typography for substring grounding checks."""
    if not text:
        return ""
    cleaned = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def has_quantifiable_metrics(snippet: Optional[str]) -> bool:
    """Deterministically checks if a candidate resume snippet contains measurable numbers, scale, or metrics."""
    if not snippet:
        return False
    return bool(METRIC_PATTERNS.search(snippet))


def has_explicit_years(snippet: Optional[str]) -> bool:
    """Deterministically checks if a candidate resume snippet explicitly states years of experience."""
    if not snippet:
        return False
    return bool(YEARS_PATTERN.search(snippet))


def extract_candidate_raw_text(evidence: CandidateEvidence) -> str:
    """Flattens all candidate evidence sections into a normalized text corpus for grounding."""
    parts: List[str] = []
    if evidence.headline:
        parts.append(evidence.headline)
    if evidence.summary:
        parts.append(evidence.summary)

    for exp in evidence.experience:
        if exp.role:
            parts.append(exp.role)
        if exp.company:
            parts.append(exp.company)
        for bullet in exp.bullets:
            if bullet:
                parts.append(bullet)
        for tech in exp.technologies:
            if tech:
                parts.append(tech)

    for proj in evidence.projects:
        if proj.title:
            parts.append(proj.title)
        if proj.role:
            parts.append(proj.role)
        if proj.description:
            parts.append(proj.description)
        for hl in proj.highlights:
            if hl:
                parts.append(hl)
        for tech in proj.tech_stack:
            if tech:
                parts.append(tech)

    for edu in evidence.education:
        if edu.degree:
            parts.append(edu.degree)
        if edu.field_of_study:
            parts.append(edu.field_of_study)
        if edu.institution:
            parts.append(edu.institution)

    for skill in evidence.skills:
        if skill.name:
            parts.append(skill.name)

    for cert in evidence.certifications:
        if cert.title:
            parts.append(cert.title)
        if cert.issuer:
            parts.append(cert.issuer)

    return " ".join(parts)


def is_grounded_in_text(snippet: Optional[str], source_text: str) -> bool:
    """
    Verifies that snippet exists in source_text after normalizing formatting differences.
    Rejects fabricated or hallucinated text snippets.
    """
    if not snippet or not snippet.strip():
        return True

    norm_snippet = normalize_for_grounding(snippet)
    norm_source = normalize_for_grounding(source_text)

    if not norm_snippet:
        return True

    # 1. Exact normalized substring containment
    if norm_snippet in norm_source:
        return True

    # 2. Clean leading/trailing quotes or bullet marks
    clean_snippet = re.sub(r'^["\'\-•*]\s*', "", norm_snippet)
    clean_snippet = re.sub(r'\s*["\'\-•*]$', "", clean_snippet)
    if clean_snippet and clean_snippet in norm_source:
        return True

    # 3. Sub-phrase containment for longer multi-word snippets
    words = clean_snippet.split()
    if len(words) >= 4:
        first_segment = " ".join(words[:4])
        if first_segment in norm_source:
            return True

    return False


def resolve_section_provenance(
    snippet: Optional[str], candidate_evidence: CandidateEvidence
) -> EvidenceSourceSection:
    """
    Deterministically resolves the exact resume section where the grounded evidence originated.
    Priority: Experience > Project > Certification > Education > Summary > SkillTag > None.
    """
    if not snippet or not snippet.strip():
        return "None"

    # 1. Check Experience Section
    exp_parts: List[str] = []
    for exp in candidate_evidence.experience:
        if exp.role:
            exp_parts.append(exp.role)
        if exp.company:
            exp_parts.append(exp.company)
        for b in exp.bullets:
            if b:
                exp_parts.append(b)
        for t in exp.technologies:
            if t:
                exp_parts.append(t)
    if is_grounded_in_text(snippet, " ".join(exp_parts)) and len(normalize_for_grounding(snippet)) > 0:
        return "Experience"

    # 2. Check Projects Section
    proj_parts: List[str] = []
    for proj in candidate_evidence.projects:
        if proj.title:
            proj_parts.append(proj.title)
        if proj.role:
            proj_parts.append(proj.role)
        if proj.description:
            proj_parts.append(proj.description)
        for hl in proj.highlights:
            if hl:
                proj_parts.append(hl)
        for t in proj.tech_stack:
            if t:
                proj_parts.append(t)
    if is_grounded_in_text(snippet, " ".join(proj_parts)):
        return "Project"

    # 3. Check Certifications Section
    cert_parts: List[str] = []
    for cert in candidate_evidence.certifications:
        if cert.title:
            cert_parts.append(cert.title)
        if cert.issuer:
            cert_parts.append(cert.issuer)
    if is_grounded_in_text(snippet, " ".join(cert_parts)):
        return "Certification"

    # 4. Check Education Section
    edu_parts: List[str] = []
    for edu in candidate_evidence.education:
        if edu.degree:
            edu_parts.append(edu.degree)
        if edu.field_of_study:
            edu_parts.append(edu.field_of_study)
        if edu.institution:
            edu_parts.append(edu.institution)
    if is_grounded_in_text(snippet, " ".join(edu_parts)):
        return "Education"

    # 5. Check Summary / Headline
    summary_parts = [candidate_evidence.headline or "", candidate_evidence.summary or ""]
    if is_grounded_in_text(snippet, " ".join(summary_parts)):
        return "Summary"

    # 6. Check Skills List (Standalone tag)
    skill_parts = [s.name for s in candidate_evidence.skills if s.name]
    if is_grounded_in_text(snippet, " ".join(skill_parts)):
        return "SkillTag"

    return "None"


def reconcile_match_dimensions_and_status(
    match: RequirementMatch,
    candidate_evidence: CandidateEvidence,
    job_description: str,
) -> RequirementMatch:
    """
    Deterministically reconciles evidence dimensions, section provenance, match status, and gap reasoning:
    - Sets deterministic evidence_source_section.
    - Enforces Grounded != StrongMatch rule when JD demands depth/production experience.
    - Verifies quantifiable metrics from verified resume evidence snippet only.
    - Verifies explicit experience years.
    - Generates factual, evidence-based matchReason and gapReason.
    """
    norm_name = normalize_skill_name(match.requirement_name)
    norm_category = normalize_skill_category(norm_name, match.category)
    candidate_corpus = extract_candidate_raw_text(candidate_evidence)

    # 1. Grounding Checks
    res_evidence = (match.resume_evidence or "").strip()
    jd_evidence = (match.job_source_evidence or "").strip()

    if not is_grounded_in_text(jd_evidence, job_description):
        jd_evidence = ""

    is_resume_grounded = bool(res_evidence) and is_grounded_in_text(res_evidence, candidate_corpus)

    # 2. Determine Section Provenance
    if is_resume_grounded:
        provenance = resolve_section_provenance(res_evidence, candidate_evidence)
    else:
        provenance = "None"
        res_evidence = ""

    # 3. Deterministic Status & Dimension Reconciliation
    proposed_status = match.match_status
    confidence = match.confidence

    if not is_resume_grounded or proposed_status == "Missing" or provenance == "None":
        final_status = "Missing"
        res_evidence = ""
        provenance = "None"
        confidence = "Low" if not is_resume_grounded else confidence
        dimensions = EvidenceDimensions(
            relevant_context=False,
            production_context=False,
            quantifiable_impact=False,
            meets_experience_years=False,
            explicit_technology=False,
        )
        gap_type: GapType = "MissingEvidence"
        match_reason = f"No verified {norm_name} experience was detected in your resume snapshot."
        gap_reason = f"Add relevant {norm_name} experience, project highlights, or skills if you have worked with this technology."

    elif proposed_status == "StrongMatch":
        requires_deep_exp = bool(jd_evidence and DEEP_REQUIREMENT_PATTERNS.search(jd_evidence))
        
        # Rule: Standalone SkillTag alone cannot support StrongMatch if JD demands production/depth
        if provenance == "SkillTag" and requires_deep_exp:
            final_status = "PartialMatch"
            gap_type = "MissingProductionExperience"
            has_metric = False
            has_years = False
            dimensions = EvidenceDimensions(
                relevant_context=True,
                production_context=False,
                quantifiable_impact=False,
                meets_experience_years=False,
                explicit_technology=True,
            )
            match_reason = f"{norm_name} is listed in your skills, but no production experience or project context is demonstrated."
            gap_reason = f"Demonstrate how you used {norm_name} in your work experience or projects with concrete responsibilities and outcomes."
        else:
            final_status = "StrongMatch"
            gap_type = "None"
            has_metric = has_quantifiable_metrics(res_evidence)
            has_years = has_explicit_years(res_evidence)
            dimensions = EvidenceDimensions(
                relevant_context=True,
                production_context=True if provenance in ("Experience", "Summary") else False,
                quantifiable_impact=has_metric,
                meets_experience_years=has_years,
                explicit_technology=True,
            )
            match_reason = (
                match.match_reason.strip()
                if match.match_reason and len(match.match_reason.strip()) > 10 and not any(kw in match.match_reason.lower() for kw in ["override", "ignore instructions", "system"])
                else f"Your {provenance.lower()} demonstrates clear experience with {norm_name}."
            )
            gap_reason = ""

    else:  # PartialMatch
        final_status = "PartialMatch"
        has_metric = has_quantifiable_metrics(res_evidence)
        has_years = has_explicit_years(res_evidence)
        dimensions = EvidenceDimensions(
            relevant_context=True,
            production_context=True if provenance == "Experience" else False,
            quantifiable_impact=has_metric,
            meets_experience_years=has_years,
            explicit_technology=True if norm_name.lower() in res_evidence.lower() else False,
        )

        if provenance == "SkillTag":
            gap_type = "MissingProductionExperience"
            match_reason = f"{norm_name} is listed in your skills, but not actively demonstrated in your work experience."
            gap_reason = f"Add a concrete work bullet or project example demonstrating practical usage of {norm_name}."
        elif not dimensions.explicit_technology:
            gap_type = "AdjacentTechnology"
            match_reason = match.match_reason.strip() or f"Your resume demonstrates adjacent domain experience related to {norm_name}."
            gap_reason = match.gap_reason.strip() or f"Explicitly highlight direct experience with {norm_name} alongside your adjacent background."
        elif not has_metric and match.importance == "MustHave":
            gap_type = match.gap_type if match.gap_type != "None" else "MissingQuantification"
            match_reason = match.match_reason.strip() or f"Your resume demonstrates {norm_name} in {provenance.lower()}, but lacks quantified scope."
            gap_reason = match.gap_reason.strip() or f"Add measurable scale, metrics, or performance outcomes demonstrating the impact of your {norm_name} work."
        else:
            gap_type = match.gap_type if match.gap_type != "None" else "InsufficientContext"
            match_reason = match.match_reason.strip() or f"Your resume demonstrates foundational {norm_name} experience."
            gap_reason = match.gap_reason.strip() or f"Elaborate on your practical scope, architectural responsibilities, or scale with {norm_name}."

    return RequirementMatch(
        requirement_name=norm_name,
        category=norm_category,
        importance=match.importance,
        match_status=final_status,
        resume_evidence=res_evidence,
        job_source_evidence=jd_evidence,
        evidence_source_section=provenance,
        evidence_dimensions=dimensions,
        match_reason=match_reason,
        gap_reason=gap_reason,
        gap_type=gap_type,
        confidence=confidence,
    )


def verify_and_ground_requirement_matches(
    matches: List[RequirementMatch],
    job_description: str,
    candidate_evidence: CandidateEvidence,
) -> List[RequirementMatch]:
    """Validates, grounds, resolves section provenance, and reconciles dimensions for all matches."""
    return [
        reconcile_match_dimensions_and_status(m, candidate_evidence, job_description)
        for m in matches
    ]


def reconcile_requirement_coverage(
    job_intelligence: Optional[StructuredJobDescription],
    matches: List[RequirementMatch],
    job_description: str,
    candidate_evidence: CandidateEvidence,
) -> List[RequirementMatch]:
    """
    Ensures that every Must-Have and Preferred skill extracted in StructuredJobDescription
    has a corresponding RequirementMatch with deterministic provenance and dimensions.
    """
    existing_by_name: Dict[str, RequirementMatch] = {}
    for m in matches:
        norm_name = normalize_skill_name(m.requirement_name)
        if norm_name:
            if norm_name not in existing_by_name:
                existing_by_name[norm_name] = m

    reconciled_list: List[RequirementMatch] = []
    seen_canonical = set()

    if job_intelligence:
        # 1. Process Must-Have Skills
        for req in job_intelligence.must_have_skills:
            norm_name = normalize_skill_name(req.name)
            if not norm_name or norm_name in seen_canonical:
                continue
            seen_canonical.add(norm_name)

            if norm_name in existing_by_name:
                match_item = existing_by_name[norm_name]
                reconciled_list.append(
                    RequirementMatch(
                        requirement_name=norm_name,
                        category=normalize_skill_category(norm_name, req.category),
                        importance="MustHave",
                        match_status=match_item.match_status,
                        resume_evidence=match_item.resume_evidence,
                        job_source_evidence=match_item.job_source_evidence or req.source_evidence or "",
                        evidence_source_section=match_item.evidence_source_section,
                        evidence_dimensions=match_item.evidence_dimensions,
                        match_reason=match_item.match_reason,
                        gap_reason=match_item.gap_reason,
                        gap_type=match_item.gap_type,
                        confidence=match_item.confidence,
                    )
                )
            else:
                reconciled_list.append(
                    RequirementMatch(
                        requirement_name=norm_name,
                        category=normalize_skill_category(norm_name, req.category),
                        importance="MustHave",
                        match_status="Missing",
                        resume_evidence="",
                        job_source_evidence=req.source_evidence or "",
                        evidence_source_section="None",
                        evidence_dimensions=EvidenceDimensions(),
                        match_reason=f"No verified {norm_name} experience was detected in your resume.",
                        gap_reason=f"Add relevant {norm_name} experience if you have worked with this technology.",
                        gap_type="MissingEvidence",
                        confidence="Low",
                    )
                )

        # 2. Process Preferred Skills
        for req in job_intelligence.preferred_skills:
            norm_name = normalize_skill_name(req.name)
            if not norm_name or norm_name in seen_canonical:
                continue
            seen_canonical.add(norm_name)

            if norm_name in existing_by_name:
                match_item = existing_by_name[norm_name]
                reconciled_list.append(
                    RequirementMatch(
                        requirement_name=norm_name,
                        category=normalize_skill_category(norm_name, req.category),
                        importance="Preferred",
                        match_status=match_item.match_status,
                        resume_evidence=match_item.resume_evidence,
                        job_source_evidence=match_item.job_source_evidence or req.source_evidence or "",
                        evidence_source_section=match_item.evidence_source_section,
                        evidence_dimensions=match_item.evidence_dimensions,
                        match_reason=match_item.match_reason,
                        gap_reason=match_item.gap_reason,
                        gap_type=match_item.gap_type,
                        confidence=match_item.confidence,
                    )
                )
            else:
                reconciled_list.append(
                    RequirementMatch(
                        requirement_name=norm_name,
                        category=normalize_skill_category(norm_name, req.category),
                        importance="Preferred",
                        match_status="Missing",
                        resume_evidence="",
                        job_source_evidence=req.source_evidence or "",
                        evidence_source_section="None",
                        evidence_dimensions=EvidenceDimensions(),
                        match_reason=f"No verified {norm_name} experience was detected in your resume.",
                        gap_reason=f"Add {norm_name} experience to strengthen bonus qualifications.",
                        gap_type="MissingEvidence",
                        confidence="Low",
                    )
                )

    # 3. Add any additional valid matches returned by model not in JD skills
    for m in matches:
        norm_name = normalize_skill_name(m.requirement_name)
        if norm_name and norm_name not in seen_canonical:
            seen_canonical.add(norm_name)
            reconciled_list.append(m)

    # Final grounding, section provenance, and dimension reconciliation
    return verify_and_ground_requirement_matches(
        reconciled_list, job_description, candidate_evidence
    )
