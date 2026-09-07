from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ExperienceItem(BaseModel):
    id: Optional[str] = None
    role: str
    company: str
    location: Optional[str] = ""
    start_date: Optional[str] = Field(default="", alias="startDate")
    end_date: Optional[str] = Field(default="", alias="endDate")
    bullets: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ProjectItem(BaseModel):
    id: Optional[str] = None
    title: str
    role: Optional[str] = ""
    description: str = ""
    highlights: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list, alias="techStack")

    model_config = ConfigDict(populate_by_name=True)


class SkillItem(BaseModel):
    name: str
    category: str = "Technical"
    proficiency: str = "Intermediate"


class EducationItem(BaseModel):
    degree: str
    institution: str
    field_of_study: str = Field(default="", alias="fieldOfStudy")

    model_config = ConfigDict(populate_by_name=True)


class CertificationItem(BaseModel):
    title: str
    issuer: str


class CandidateEvidence(BaseModel):
    headline: Optional[str] = ""
    summary: str = ""
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    skills: List[SkillItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
