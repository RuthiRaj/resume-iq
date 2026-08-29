from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

GapType = Literal[
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
]

EvidenceSourceSection = Literal[
    "Experience",
    "Project",
    "SkillTag",
    "Education",
    "Certification",
    "Summary",
    "None",
]


class EvidenceDimensions(BaseModel):
    relevant_context: bool = Field(
        default=False,
        alias="relevantContext",
        description="Whether the evidence demonstrates relevant application of the skill",
    )
    production_context: bool = Field(
        default=False,
        alias="productionContext",
        description="Whether the evidence demonstrates real production/workplace usage",
    )
    quantifiable_impact: bool = Field(
        default=False,
        alias="quantifiableImpact",
        description="Whether the evidence includes measurable metrics or scale indicators",
    )
    meets_experience_years: bool = Field(
        default=False,
        alias="meetsExperienceYears",
        description="Whether the evidence indicates the required experience duration",
    )
    explicit_technology: bool = Field(
        default=False,
        alias="explicitTechnology",
        description="Whether the exact technology name is explicitly referenced",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RequirementMatch(BaseModel):
    requirement_name: str = Field(
        ..., alias="requirementName", min_length=1, max_length=150
    )
    category: Literal[
        "Language",
        "Framework",
        "Database",
        "Cloud",
        "DevOps",
        "Tool",
        "SoftSkill",
        "Domain",
        "Other",
    ] = Field(default="Other")
    importance: Literal["MustHave", "Preferred", "Unspecified"] = Field(
        default="MustHave"
    )
    match_status: Literal["StrongMatch", "PartialMatch", "Missing"] = Field(
        ..., alias="matchStatus"
    )
    resume_evidence: Optional[str] = Field(
        default="",
        alias="resumeEvidence",
        max_length=500,
        description="Grounded verbatim snippet from candidate resume demonstrating qualification",
    )
    job_source_evidence: Optional[str] = Field(
        default="",
        alias="jobSourceEvidence",
        max_length=500,
        description="Verbatim snippet from job description defining the requirement",
    )
    evidence_source_section: EvidenceSourceSection = Field(
        default="None",
        alias="evidenceSourceSection",
        description="Deterministically verified resume section where evidence originated",
    )
    evidence_dimensions: EvidenceDimensions = Field(
        default_factory=EvidenceDimensions,
        alias="evidenceDimensions",
        description="Structured evaluation of evidence dimensions",
    )
    match_reason: str = Field(
        default="",
        alias="matchReason",
        max_length=400,
        description="Factual explanation of why this requirement is classified as Strong/Partial/Missing",
    )
    gap_reason: Optional[str] = Field(
        default="",
        alias="gapReason",
        max_length=400,
        description="Concrete, actionable explanation of what requirement is missing or unmet",
    )
    gap_type: GapType = Field(
        default="None",
        alias="gapType",
        description="Structured classification of the requirement gap",
    )
    confidence: Literal["High", "Medium", "Low"] = Field(
        default="High",
        description="Confidence level of the evidence evaluation",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
