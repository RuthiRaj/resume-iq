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
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class ProjectItem(BaseModel):
    id: Optional[str] = None
    title: str
    role: Optional[str] = ""
    description: str = ""
    highlights: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list, alias="techStack")
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class SkillItem(BaseModel):
    id: Optional[str] = None
    name: str
    category: str = "Technical"
    proficiency: str = "Intermediate"
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class EducationItem(BaseModel):
    id: Optional[str] = None
    degree: str
    institution: str
    field_of_study: str = Field(default="", alias="fieldOfStudy")
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class CertificationItem(BaseModel):
    id: Optional[str] = None
    title: str
    issuer: str
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class AchievementItem(BaseModel):
    id: Optional[str] = None
    title: str
    issuer: Optional[str] = ""
    date: Optional[str] = ""
    description: Optional[str] = ""
    url: Optional[str] = ""
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")
    verification_status: Optional[str] = Field(default="verified", alias="verificationStatus")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class InternshipItem(BaseModel):
    id: Optional[str] = None
    role: str
    company: str
    location: Optional[str] = ""
    start_date: Optional[str] = Field(default="", alias="startDate")
    end_date: Optional[str] = Field(default="", alias="endDate")
    bullets: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")

    model_config = ConfigDict(populate_by_name=True)


class PublicationItem(BaseModel):
    id: Optional[str] = None
    title: str
    publisher: Optional[str] = ""
    publication_date: Optional[str] = Field(default="", alias="publicationDate")
    url: Optional[str] = ""
    description: Optional[str] = ""
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")

    model_config = ConfigDict(populate_by_name=True)


class AwardItem(BaseModel):
    id: Optional[str] = None
    title: str
    issuer: Optional[str] = ""
    date: Optional[str] = ""
    description: Optional[str] = ""
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")

    model_config = ConfigDict(populate_by_name=True)


class VolunteeringItem(BaseModel):
    id: Optional[str] = None
    role: str
    organization: str
    start_date: Optional[str] = Field(default="", alias="startDate")
    end_date: Optional[str] = Field(default="", alias="endDate")
    description: Optional[str] = ""
    highlights: List[str] = Field(default_factory=list)
    source_document_id: Optional[str] = Field(default=None, alias="sourceDocumentId")
    source_document_name: Optional[str] = Field(default=None, alias="sourceDocumentName")

    model_config = ConfigDict(populate_by_name=True)


class CandidateEvidence(BaseModel):
    headline: Optional[str] = ""
    summary: str = ""
    experience: List[ExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    skills: List[SkillItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    achievements: List[AchievementItem] = Field(default_factory=list)
    internships: List[InternshipItem] = Field(default_factory=list)
    publications: List[PublicationItem] = Field(default_factory=list)
    awards: List[AwardItem] = Field(default_factory=list)
    volunteering: List[VolunteeringItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)
