from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

EvidenceSourceType = Literal[
    "profile",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "achievements",
    "internships",
    "publications",
    "awards",
    "volunteering",
    "documents",
]

VerificationStatus = Literal[
    "verified",
    "unverified",
    "user_confirmed",
    "missing",
    "related_unverified",
]

EvidenceRelationshipType = Literal[
    "demonstrates_skill",
    "uses_technology",
    "held_role",
    "produced_achievement",
    "matches_requirement",
    "supports_claim",
]


class EvidenceItem(BaseModel):
    """
    Unified, normalized evidence item extracted from a candidate's workspace.
    Maintains exact provenance (source_type + source_item_id) for zero-hallucination tracking.
    """
    evidence_id: str = Field(..., alias="evidenceId", description="Unique identifier e.g. ev_exp_0")
    user_id: str = Field(..., alias="userId", description="Authenticated user Firebase UID")
    source_type: EvidenceSourceType = Field(..., alias="sourceType")
    source_item_id: str = Field(..., alias="sourceItemId", description="Underlying workspace item ID e.g. exp_0")
    title: str = Field(..., description="Concise title e.g. 'Software Engineer at Stripe' or 'Project X'")
    description: str = Field(default="", description="Full narrative description or summary text")
    skills: List[str] = Field(default_factory=list, description="Canonical skills demonstrated")
    technologies: List[str] = Field(default_factory=list, description="Specific technologies/tools used")
    responsibilities: List[str] = Field(default_factory=list, description="Core responsibilities or tasks")
    achievements: List[str] = Field(default_factory=list, description="Specific achievement or bullet strings")
    metrics: List[str] = Field(default_factory=list, description="Verifiable metrics extracted from text")
    dates: Optional[str] = Field(default="", description="Date range or occurrence date")
    role: Optional[str] = Field(default="", description="Job title, role, or capacity")
    domain: Optional[str] = Field(default="", description="Industry domain or functional discipline")
    source_document_id: Optional[str] = Field(
        default=None,
        alias="sourceDocumentId",
        description="Persistent ID of the ingested document that introduced this evidence (e.g. ingest_...)",
    )
    source_document_name: Optional[str] = Field(
        default=None,
        alias="sourceDocumentName",
        description="Sanitized file name of the original uploaded document",
    )
    verification_status: VerificationStatus = Field(default="verified", alias="verificationStatus")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Deterministic evidence confidence score")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvidenceProvenanceDetail(BaseModel):
    """
    Granular provenance tracing contract connecting a resume claim/evidence item
    back to its workspace source entity and original uploaded document draft.
    """
    evidence_id: str = Field(..., alias="evidenceId")
    user_id: str = Field(..., alias="userId")
    source_type: EvidenceSourceType = Field(..., alias="sourceType")
    source_item_id: str = Field(..., alias="sourceItemId")
    title: str = Field(default="")
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    ingestion_draft_status: Optional[str] = Field(default=None, alias="ingestionDraftStatus")
    file_url: Optional[str] = Field(default=None, alias="fileUrl")
    verification_status: VerificationStatus = Field(default="verified", alias="verificationStatus")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)



class EvidenceRelationship(BaseModel):
    """
    Represents a directed relationship from an evidence item to a skill, technology, role, or claim.
    """
    source_evidence_id: str = Field(..., alias="sourceEvidenceId")
    target_id: str = Field(..., alias="targetId", description="Normalized target value (e.g. 'React', 'exp_0')")
    target_type: str = Field(..., alias="targetType", description="Target entity type (e.g. 'Skill', 'Role')")
    relationship_type: EvidenceRelationshipType = Field(..., alias="relationshipType")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvidenceGraphQuery(BaseModel):
    """
    Query parameters for filtering evidence items within the Career Evidence Graph.
    """
    skill: Optional[str] = None
    technology: Optional[str] = None
    role: Optional[str] = None
    source_type: Optional[EvidenceSourceType] = Field(default=None, alias="sourceType")
    has_metrics: Optional[bool] = Field(default=None, alias="hasMetrics")
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, alias="minConfidence")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvidenceQueryResult(BaseModel):
    """
    Result payload for a Career Evidence Graph query.
    """
    items: List[EvidenceItem] = Field(default_factory=list)
    total_count: int = Field(default=0, alias="totalCount")
    skills_matched: List[str] = Field(default_factory=list, alias="skillsMatched")
    technologies_matched: List[str] = Field(default_factory=list, alias="technologiesMatched")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
