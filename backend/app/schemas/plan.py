"""
ResumePlan Schema for ResumeIQ

Defines the strongly-typed Pydantic v2 contract for the Standalone Resume Planning Layer.
The ResumePlan sits deterministically between Evidence Ranking and LLM Generation.
It represents the explicit planning decisions:
- Target page budget & section ordering
- Selected vs. excluded workspace evidence with deterministic rationales
- Prioritized skills, ATS keywords, and requirement strategy
- Hard gaps and prohibited claims that must not be hallucinated
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.evidence import EvidenceSourceType
from app.schemas.requirement_match import GapType
from app.ai.retrieval.hybrid_matcher import MatchClass


class SectionPlan(BaseModel):
    """Planning representation for an individual resume section."""
    section_name: str = Field(
        ...,
        alias="sectionName",
        description="Section identifier (e.g. Header, Summary, Skills, Experience, Projects, Education, Certifications, Achievements)",
    )
    included: bool = Field(
        default=True,
        description="Whether this section is planned to be included in the resume output",
    )
    selected_evidence_ids: List[str] = Field(
        default_factory=list,
        alias="selectedEvidenceIds",
        description="Ordered list of EvidenceItem IDs chosen for this section",
    )
    priority: int = Field(
        default=1,
        ge=1,
        description="Section priority rank (1 = highest priority)",
    )
    order: int = Field(
        default=1,
        ge=1,
        description="Render order index in the final resume layout",
    )
    rationale: str = Field(
        default="",
        description="Deterministic reasoning for inclusion, evidence count, and order",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class SelectedEvidenceItem(BaseModel):
    """Reference and rationale for an evidence item selected for inclusion."""
    evidence_id: str = Field(..., alias="evidenceId", description="Unique EvidenceItem ID")
    source_type: EvidenceSourceType = Field(..., alias="sourceType")
    source_item_id: str = Field(..., alias="sourceItemId", description="Underlying workspace item ID")
    title: str = Field(default="", description="Title or concise label of the evidence item")
    rank_score: float = Field(default=0.0, ge=0.0, le=1.0, alias="rankScore")
    selection_reason: str = Field(
        default="",
        alias="selectionReason",
        description="Deterministic justification for selecting this evidence item",
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        alias="matchedSkills",
        description="Target job requirements or skills directly matched by this item",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ExcludedEvidenceItem(BaseModel):
    """Reference and deterministic rationale for an evidence item excluded from the resume."""
    evidence_id: str = Field(..., alias="evidenceId", description="Unique EvidenceItem ID")
    source_type: EvidenceSourceType = Field(..., alias="sourceType")
    source_item_id: str = Field(..., alias="sourceItemId", description="Underlying workspace item ID")
    title: str = Field(default="", description="Title or concise label of the excluded item")
    rank_score: float = Field(default=0.0, ge=0.0, le=1.0, alias="rankScore")
    exclusion_reason: str = Field(
        default="",
        alias="exclusionReason",
        description="Deterministic reason for exclusion (e.g. page_budget_constraint, lower_relevance_than_selected, unrelated_domain)",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class PrioritizedSkill(BaseModel):
    """Individual skill prioritized during resume planning."""
    name: str = Field(..., description="Canonical skill name")
    category: str = Field(default="Other", description="Taxonomy category")
    importance: Literal["MustHave", "Preferred", "Unspecified"] = Field(default="MustHave")
    match_class: MatchClass = Field(default="direct_match", alias="matchClass")
    is_directly_demonstrated: bool = Field(
        default=True,
        alias="isDirectlyDemonstrated",
        description="True if candidate workspace contains verified evidence, False if unverified or missing",
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        alias="evidenceIds",
        description="Supporting EvidenceItem IDs from the candidate's workspace",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class HardGap(BaseModel):
    """
    Explicit representation of an unmet job requirement.
    The resume generator is strictly prohibited from fabricating or hallucinating claims for this gap.
    """
    requirement_name: str = Field(..., alias="requirementName")
    category: str = Field(default="Other")
    gap_type: GapType = Field(default="MissingEvidence", alias="gapType")
    reason: str = Field(default="", description="Factual explanation of why this requirement is unmet")
    prohibited_claim_instruction: str = Field(
        default="",
        alias="prohibitedClaimInstruction",
        description="Explicit directive for the generator instructing it not to invent evidence for this gap",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RequirementStrategy(BaseModel):
    """Strategic guidance for tailoring the resume to the target role."""
    focus_areas: List[str] = Field(default_factory=list, alias="focusAreas")
    summary_theme: str = Field(default="", alias="summaryTheme")
    highlighted_domains: List[str] = Field(default_factory=list, alias="highlightedDomains")
    notes: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ResumePlan(BaseModel):
    """
    Authoritative, deterministic planning contract for ResumeIQ resume generation.
    Connects Evidence Ranking with Grounded Resume Generation.
    """
    plan_id: str = Field(..., alias="planId", description="Unique plan identifier e.g. plan_...")
    user_id: str = Field(default="", alias="userId", description="Authenticated user ID owning this plan")
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    target_page_budget: int = Field(
        default=1,
        ge=1,
        le=5,
        alias="targetPageBudget",
        description="Target page budget constraint (e.g. 1 or 2 pages)",
    )
    section_order: List[str] = Field(
        default_factory=list,
        alias="sectionOrder",
        description="Planned display order of sections (e.g. ['Header', 'Summary', 'Skills', 'Experience', 'Projects', 'Education', 'Certifications', 'Achievements'])",
    )
    sections: List[SectionPlan] = Field(default_factory=list)
    selected_evidence: List[SelectedEvidenceItem] = Field(default_factory=list, alias="selectedEvidence")
    excluded_evidence: List[ExcludedEvidenceItem] = Field(default_factory=list, alias="excludedEvidence")
    prioritized_skills: List[PrioritizedSkill] = Field(default_factory=list, alias="prioritizedSkills")
    prioritized_keywords: List[str] = Field(default_factory=list, alias="prioritizedKeywords")
    requirement_strategy: RequirementStrategy = Field(
        default_factory=RequirementStrategy,
        alias="requirementStrategy",
    )
    hard_gaps: List[HardGap] = Field(default_factory=list, alias="hardGaps")
    related_but_unverified_requirements: List[str] = Field(
        default_factory=list,
        alias="relatedButUnverifiedRequirements",
        description="Technologies where candidate has related experience but not the required skill",
    )
    user_confirmation_required: List[str] = Field(
        default_factory=list,
        alias="userConfirmationRequired",
        description="Skills listed as standalone tags without supporting work/project narratives",
    )
    planning_metadata: Dict[str, Any] = Field(default_factory=dict, alias="planningMetadata")
    created_at: str = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
