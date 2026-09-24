import re
from typing import List, Dict, Set, Optional, Literal, Tuple
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.job_description import (
    StructuredJobDescription,
    JobInfo,
    SkillRequirement,
    SeniorityLevel,
)
from app.schemas.evidence import EvidenceItem
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.ai.skills import normalize_skill_name, normalize_skill_category, CANONICAL_SKILL_MAP

# Match Classification Taxonomy
# Note on 'semantic_match': Semantic embeddings/vector indexing are deferred to future vector infrastructure.
# Current hybrid matcher implements exact canonical matching, user confirmation for ungrounded tags,
# non-equivalence domain clustering ('related_but_unverified'), and missing requirements.
MatchClass = Literal[
    "direct_match",
    "semantic_match",
    "related_but_unverified",
    "missing",
    "user_confirmation_required",
]

# Distinct Technology Clusters for Non-Equivalence & Relatedness Detection
# Items within a cluster are related, but strictly non-equivalent.
TECHNOLOGY_CLUSTERS: List[Set[str]] = [
    {"javascript", "typescript"},
    {"react", "angular", "vue.js", "svelte"},
    {"docker", "kubernetes", "podman"},
    {"machine learning", "deep learning", "nlp", "computer vision"},
    {"postgresql", "mysql", "sqlite", "oracle", "sql server"},
    {"mongodb", "dynamodb", "cassandra", "redis", "elasticsearch"},
    {"aws", "google cloud", "microsoft azure"},
    {"fastapi", "django", "flask"},
    {"c++", "c#", "c", "rust"},
    {"kafka", "rabbitmq"},
]

SENIORITY_PATTERNS: List[Tuple[re.Pattern, SeniorityLevel]] = [
    (re.compile(r"\b(principal|distinguished)\b", re.IGNORECASE), "Principal"),
    (re.compile(r"\b(staff)\b", re.IGNORECASE), "Staff"),
    (re.compile(r"\b(lead|team lead|tech lead)\b", re.IGNORECASE), "Lead"),
    (re.compile(r"\b(senior|sr\.?|sr)\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\b(mid-level|mid level|intermediate)\b", re.IGNORECASE), "Mid"),
    (re.compile(r"\b(associate)\b", re.IGNORECASE), "Associate"),
    (re.compile(r"\b(junior|jr\.?|jr|entry-level|entry level)\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\b(intern|internship)\b", re.IGNORECASE), "Intern"),
]


def extract_seniority_from_text(title: str, text: str = "") -> SeniorityLevel:
    """
    Extracts explicit seniority level from job title or job description text.
    Returns 'Unspecified' if no explicit seniority indicator is found.
    Never fabricates seniority.
    """
    for pattern, level in SENIORITY_PATTERNS:
        if pattern.search(title):
            return level
    if text:
        for pattern, level in SENIORITY_PATTERNS:
            if pattern.search(text[:500]):
                return level
    return "Unspecified"


def parse_job_description_deterministic(
    target_role: str,
    job_description_text: str = "",
    target_company: str = "",
) -> StructuredJobDescription:
    """
    Deterministically parses user-provided Job Description text into a StructuredJobDescription.
    Extracts skills, seniority, and keywords without external LLM calls or hallucinations.
    """
    seniority = extract_seniority_from_text(target_role, job_description_text)
    job_info = JobInfo(
        roleTitle=target_role,
        company=target_company or "",
        seniorityLevel=seniority,
    )

    combined_text = f"{target_role} {job_description_text}".lower()

    must_haves: List[SkillRequirement] = []
    preferred: List[SkillRequirement] = []
    seen_skills: Set[str] = set()

    preferred_section_start = -1
    for marker in ("preferred", "nice to have", "plus", "bonus", "optional"):
        idx = combined_text.find(marker)
        if idx != -1 and (preferred_section_start == -1 or idx < preferred_section_start):
            preferred_section_start = idx

    for raw_skill, canonical_name in sorted(CANONICAL_SKILL_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r"\b" + re.escape(raw_skill) + r"\b"
        match = re.search(pattern, combined_text)
        if match:
            if canonical_name in seen_skills:
                continue
            seen_skills.add(canonical_name)

            category = normalize_skill_category(canonical_name, "Other")
            match_pos = match.start()

            is_preferred = (preferred_section_start != -1 and match_pos >= preferred_section_start)
            importance = "Preferred" if is_preferred else "MustHave"

            req = SkillRequirement(
                name=canonical_name,
                category=category,
                importance=importance,
                sourceEvidence=match.group(0),
            )
            if is_preferred:
                preferred.append(req)
            else:
                must_haves.append(req)

    # Fallback to role title keywords if no dictionary skills matched
    if not must_haves and not preferred:
        role_tokens = [tok for tok in re.findall(r"\b[a-zA-Z0-9_\-\+#\.]+\b", target_role) if len(tok) > 1]
        for tok in role_tokens:
            norm_name = normalize_skill_name(tok)
            if norm_name not in seen_skills:
                seen_skills.add(norm_name)
                must_haves.append(
                    SkillRequirement(
                        name=norm_name,
                        category=normalize_skill_category(norm_name, "Other"),
                        importance="MustHave",
                        sourceEvidence=target_role,
                    )
                )

    return StructuredJobDescription(
        jobInfo=job_info,
        mustHaveSkills=must_haves,
        preferredSkills=preferred,
        technicalStack=sorted(list(seen_skills)),
    )


def find_related_technology(req_tech: str, candidate_techs: Set[str]) -> Optional[str]:
    """
    Checks if a candidate possesses a related technology from the same domain cluster,
    strictly enforcing that the technologies are non-equivalent.
    """
    norm_req = normalize_skill_name(req_tech).lower()
    norm_candidate = {normalize_skill_name(t).lower() for t in candidate_techs}

    for cluster in TECHNOLOGY_CLUSTERS:
        if norm_req in cluster:
            for member in cluster:
                if member != norm_req and member in norm_candidate:
                    return normalize_skill_name(member)
    return None


class RequirementMatchResult(BaseModel):
    """
    Structured outcome of matching a single job requirement against candidate evidence.
    Retains explicit match classification, matched technology, evidence provenance, and explanations.
    """
    requirement_name: str = Field(..., alias="requirementName")
    category: str = "Other"
    importance: Literal["MustHave", "Preferred", "Unspecified"] = "MustHave"
    match_class: MatchClass = Field(..., alias="matchClass")
    matched_technology: Optional[str] = Field(default=None, alias="matchedTechnology")
    candidate_evidence_ids: List[str] = Field(default_factory=list, alias="candidateEvidenceIds")
    evidence_snippets: List[str] = Field(default_factory=list, alias="evidenceSnippets")
    provenance_sources: List[str] = Field(default_factory=list, alias="provenanceSources")
    explanation: str = Field(default="")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    has_metrics: bool = Field(default=False, alias="hasMetrics")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class HybridMatchResponse(BaseModel):
    """
    Aggregate response evaluating all JD requirements against candidate evidence.
    """
    matches: List[RequirementMatchResult] = Field(default_factory=list)
    direct_match_count: int = Field(default=0, alias="directMatchCount")
    semantic_match_count: int = Field(default=0, alias="semanticMatchCount")
    related_unverified_count: int = Field(default=0, alias="relatedUnverifiedCount")
    missing_count: int = Field(default=0, alias="missingCount")
    user_confirmation_count: int = Field(default=0, alias="userConfirmationCount")
    overall_coverage_score: float = Field(default=0.0, ge=0.0, le=100.0, alias="overallCoverageScore")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class HybridMatcher:
    """
    Deterministic hybrid matching engine for ResumeIQ.
    Combines lexical/exact skill matching with non-equivalence clustering,
    producing grounded, verified match classifications without hallucination.
    """

    @staticmethod
    def parse_job_description_deterministic(
        target_role: str,
        job_description_text: str = "",
        target_company: str = "",
    ) -> StructuredJobDescription:
        """Deterministically parses user-provided Job Description text into a StructuredJobDescription."""
        return parse_job_description_deterministic(
            target_role=target_role,
            job_description_text=job_description_text,
            target_company=target_company,
        )

    @classmethod
    def match_job_requirements(
        cls,
        job_description: StructuredJobDescription,
        evidence_graph: CareerEvidenceGraph,
        semantic_matches_by_req: Optional[Dict[str, List[str]]] = None,
    ) -> HybridMatchResponse:
        """
        Evaluates must-have and preferred requirements from StructuredJobDescription
        against candidate CareerEvidenceGraph.
        """
        all_reqs: List[Tuple[SkillRequirement, str]] = []
        for s in job_description.must_have_skills:
            all_reqs.append((s, "MustHave"))
        for s in job_description.preferred_skills:
            all_reqs.append((s, "Preferred"))

        candidate_skills = set(evidence_graph.get_skills_demonstrated())
        candidate_techs = set(evidence_graph.get_technologies_demonstrated())
        all_candidate_tech_and_skills = candidate_skills | candidate_techs

        results: List[RequirementMatchResult] = []
        direct_count = 0
        semantic_count = 0
        related_count = 0
        missing_count = 0
        confirmation_count = 0

        for req, importance in all_reqs:
            norm_req_name = normalize_skill_name(req.name)
            norm_category = normalize_skill_category(norm_req_name, req.category)

            # 1. Exact / Canonical Match Attempt
            exact_items = evidence_graph.find_by_skill(norm_req_name)
            if not exact_items:
                exact_items = evidence_graph.find_by_technology(norm_req_name)

            if exact_items:
                evidence_ids = [item.evidence_id for item in exact_items]
                provenance = [f"{item.source_type}:{item.source_item_id}" for item in exact_items]
                snippets = [item.title for item in exact_items]
                has_metrics = any(len(item.metrics) > 0 for item in exact_items)

                # Check if only standalone skill tag without narrative evidence
                only_tag = all(item.source_type == "skills" for item in exact_items)
                if only_tag and importance == "MustHave":
                    match_class: MatchClass = "user_confirmation_required"
                    explanation = f"'{norm_req_name}' is listed as a skill tag in workspace, but lacks accomplishment bullets or project evidence."
                    confidence = 0.85
                    confirmation_count += 1
                else:
                    match_class = "direct_match"
                    explanation = f"Verified direct evidence found for '{norm_req_name}' in candidate workspace ({len(exact_items)} item(s))."
                    confidence = 1.0
                    direct_count += 1

                results.append(
                    RequirementMatchResult(
                        requirementName=norm_req_name,
                        category=norm_category,
                        importance=importance,
                        matchClass=match_class,
                        matchedTechnology=norm_req_name,
                        candidateEvidenceIds=evidence_ids,
                        evidenceSnippets=snippets,
                        provenanceSources=provenance,
                        explanation=explanation,
                        confidence=confidence,
                        hasMetrics=has_metrics,
                    )
                )
                continue

            # 2. Non-Equivalence & Related Technology Check
            related_tech = find_related_technology(norm_req_name, all_candidate_tech_and_skills)
            if related_tech:
                related_items = evidence_graph.find_by_skill(related_tech) or evidence_graph.find_by_technology(related_tech)
                evidence_ids = [item.evidence_id for item in related_items]
                provenance = [f"{item.source_type}:{item.source_item_id}" for item in related_items]
                snippets = [item.title for item in related_items]
                has_metrics = any(len(item.metrics) > 0 for item in related_items)

                results.append(
                    RequirementMatchResult(
                        requirementName=norm_req_name,
                        category=norm_category,
                        importance=importance,
                        matchClass="related_but_unverified",
                        matchedTechnology=related_tech,
                        candidateEvidenceIds=evidence_ids,
                        evidenceSnippets=snippets,
                        provenanceSources=provenance,
                        explanation=f"Candidate demonstrates related experience with '{related_tech}', but '{norm_req_name}' is not explicitly verified in workspace.",
                        confidence=0.75,
                        hasMetrics=has_metrics,
                    )
                )
                related_count += 1
                continue

            # 3. Dense Semantic Match Check (for domain concepts/responsibilities not in non-equivalence clusters)
            semantic_matched_items: List[EvidenceItem] = []
            if semantic_matches_by_req and norm_req_name in semantic_matches_by_req:
                semantic_eids = semantic_matches_by_req[norm_req_name]
                for eid in semantic_eids:
                    item = evidence_graph._items_by_id.get(eid)
                    if item:
                        semantic_matched_items.append(item)

            if semantic_matched_items:
                evidence_ids = [item.evidence_id for item in semantic_matched_items]
                provenance = [f"{item.source_type}:{item.source_item_id}" for item in semantic_matched_items]
                snippets = [item.title for item in semantic_matched_items]
                has_metrics = any(len(item.metrics) > 0 for item in semantic_matched_items)

                results.append(
                    RequirementMatchResult(
                        requirementName=norm_req_name,
                        category=norm_category,
                        importance=importance,
                        matchClass="semantic_match",
                        matchedTechnology=norm_req_name,
                        candidateEvidenceIds=evidence_ids,
                        evidenceSnippets=snippets,
                        provenanceSources=provenance,
                        explanation=f"Demonstrated conceptual alignment found via semantic retrieval for '{norm_req_name}'.",
                        confidence=0.85,
                        hasMetrics=has_metrics,
                    )
                )
                semantic_count += 1
                continue

            # 4. Missing Requirement
            results.append(
                RequirementMatchResult(
                    requirementName=norm_req_name,
                    category=norm_category,
                    importance=importance,
                    matchClass="missing",
                    matchedTechnology=None,
                    candidateEvidenceIds=[],
                    evidenceSnippets=[],
                    provenanceSources=[],
                    explanation=f"No verified evidence found in candidate workspace for '{norm_req_name}'.",
                    confidence=1.0,
                    hasMetrics=False,
                )
            )
            missing_count += 1

        # Calculate Overall Coverage Score (0 - 100)
        total_reqs = len(all_reqs)
        if total_reqs == 0:
            coverage_score = 100.0
        else:
            score_numerator = 0.0
            score_denominator = 0.0
            for r in results:
                weight = 2.0 if r.importance == "MustHave" else 1.0
                score_denominator += weight
                if r.match_class == "direct_match":
                    score_numerator += weight * 1.0
                elif r.match_class == "semantic_match":
                    score_numerator += weight * 0.9
                elif r.match_class == "user_confirmation_required":
                    score_numerator += weight * 0.8
                elif r.match_class == "related_but_unverified":
                    score_numerator += weight * 0.4

            coverage_score = round((score_numerator / score_denominator) * 100.0, 1)

        return HybridMatchResponse(
            matches=results,
            directMatchCount=direct_count,
            semanticMatchCount=semantic_count,
            relatedUnverifiedCount=related_count,
            missingCount=missing_count,
            userConfirmationCount=confirmation_count,
            overallCoverageScore=coverage_score,
        )
