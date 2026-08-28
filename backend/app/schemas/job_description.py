from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class JobInfo(BaseModel):
    role_title: str = Field(..., alias="roleTitle", min_length=1, max_length=150)
    company: Optional[str] = Field(default="", max_length=100)
    seniority_level: Literal[
        "Junior", "Mid", "Senior", "Lead", "Principal", "Executive", "Unspecified"
    ] = Field(default="Unspecified", alias="seniorityLevel")
    employment_type: Optional[str] = Field(default="", alias="employmentType", max_length=50)
    domain: Optional[str] = Field(default="", max_length=100)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class SkillRequirement(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
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
    source_evidence: Optional[str] = Field(
        default="",
        alias="sourceEvidence",
        max_length=300,
        description="Concise snippet from JD source text justifying this requirement",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ExperienceRequirement(BaseModel):
    minimum_years: Optional[int] = Field(default=None, alias="minimumYears", ge=0, le=50)
    required_level: Optional[str] = Field(default="", alias="requiredLevel", max_length=100)
    description: Optional[str] = Field(default="", max_length=300)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EducationRequirement(BaseModel):
    degree_level: Optional[str] = Field(default="", alias="degreeLevel", max_length=100)
    field_of_study: Optional[str] = Field(default="", alias="fieldOfStudy", max_length=100)
    is_required: bool = Field(default=False, alias="isRequired")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class StructuredJobDescription(BaseModel):
    job_info: JobInfo = Field(..., alias="jobInfo")
    must_have_skills: List[SkillRequirement] = Field(
        default_factory=list, alias="mustHaveSkills"
    )
    preferred_skills: List[SkillRequirement] = Field(
        default_factory=list, alias="preferredSkills"
    )
    technical_stack: List[str] = Field(
        default_factory=list,
        alias="technicalStack",
        description="Distinct technologies and platforms extracted across the job description",
    )
    responsibilities: List[str] = Field(
        default_factory=list,
        description="Concise core responsibilities faithfully extracted from JD",
    )
    experience: Optional[ExperienceRequirement] = Field(default=None)
    education: Optional[EducationRequirement] = Field(default=None)
    certifications: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list, alias="softSkills")
    summary: str = Field(
        default="",
        max_length=500,
        description="Concise synthesized summary of role expectations",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
