from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ProfileDTO(BaseModel):
    full_name: Optional[str] = Field(default="", alias="fullName")
    headline: Optional[str] = Field(default="")
    email: Optional[str] = Field(default="")
    phone: Optional[str] = Field(default="")
    location: Optional[str] = Field(default="")
    website: Optional[str] = Field(default="")
    linkedin: Optional[str] = Field(default="")
    github: Optional[str] = Field(default="")
    summary: Optional[str] = Field(default="")
    target_roles: List[str] = Field(default_factory=list, alias="targetRoles")

    model_config = ConfigDict(populate_by_name=True)


class ProfileResponse(BaseModel):
    success: bool = True
    profile: ProfileDTO
    message: Optional[str] = "Profile saved successfully."

    model_config = ConfigDict(populate_by_name=True)
