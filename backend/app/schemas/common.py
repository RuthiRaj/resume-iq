from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class ScoreBreakdown(BaseModel):
    relevance: int = Field(..., ge=0, le=100)
    keywords: int = Field(..., ge=0, le=100)
    metrics: int = Field(..., ge=0, le=100)
    formatting: int = Field(..., ge=0, le=100)

    model_config = ConfigDict(populate_by_name=True)


class SkillMatchItem(BaseModel):
    name: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class SkillMissingItem(BaseModel):
    name: str = Field(..., min_length=1)
    priority: Literal["High", "Medium", "Low"]
    reason: str = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class SkillPartialItem(BaseModel):
    name: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class AnalysisMetadata(BaseModel):
    provider: str
    model: str
    analyzed_at: str = Field(..., alias="analyzedAt")
    job_description_hash: str = Field(..., alias="jobDescriptionHash")
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
