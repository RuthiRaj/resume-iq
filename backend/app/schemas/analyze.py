from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import (
    ScoreBreakdown,
    SkillMatchItem,
    SkillMissingItem,
    SkillPartialItem,
    AnalysisMetadata,
)
from app.schemas.job_description import StructuredJobDescription
from app.schemas.requirement_match import RequirementMatch
from app.schemas.remediation import RemediationSuggestion


class AnalyzeRequest(BaseModel):
    resume_id: str = Field(..., alias="resumeId", min_length=1, description="Resume ID or 'workspace'")
    target_role: str = Field(..., alias="targetRole", min_length=2, max_length=150)
    target_company: Optional[str] = Field(default="", alias="targetCompany", max_length=100)
    job_description: str = Field(
        ...,
        alias="jobDescription",
        min_length=30,
        max_length=25000,
        description="Target job description requirements (30 to 25,000 chars)",
    )

    model_config = ConfigDict(populate_by_name=True)


class AnalyzeResponse(BaseModel):
    ats_score: int = Field(..., alias="atsScore", ge=0, le=100)
    score_breakdown: ScoreBreakdown = Field(..., alias="scoreBreakdown")
    summary_feedback: str = Field(..., alias="summaryFeedback", min_length=10)
    matching_skills: List[SkillMatchItem] = Field(default_factory=list, alias="matchingSkills")
    missing_skills: List[SkillMissingItem] = Field(default_factory=list, alias="missingSkills")
    partial_skills: List[SkillPartialItem] = Field(default_factory=list, alias="partialSkills")
    job_intelligence: Optional[StructuredJobDescription] = Field(
        default=None, alias="jobIntelligence"
    )
    requirement_matches: List[RequirementMatch] = Field(
        default_factory=list, alias="requirementMatches"
    )
    remediation_suggestions: List[RemediationSuggestion] = Field(
        default_factory=list, alias="remediationSuggestions"
    )
    metadata: AnalysisMetadata

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
