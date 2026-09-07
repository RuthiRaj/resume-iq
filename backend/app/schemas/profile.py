import re
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

DANGEROUS_SCHEMES = ("javascript:", "data:", "vbscript:", "file:", "blob:", "about:")


def validate_url_field(url: Optional[str], field_name: str, max_len: int = 500) -> str:
    """Validates that a URL is safe, non-malformed, and does not use executable schemes."""
    if not url:
        return ""
    val = str(url).strip()
    if not val:
        return ""
    if len(val) > max_len:
        raise ValueError(f"{field_name} exceeds maximum length of {max_len} characters.")
    lower = val.lower()
    if any(lower.startswith(d) for d in DANGEROUS_SCHEMES):
        raise ValueError(f"{field_name} contains an unpermitted or dangerous URL scheme.")
    if ":" in val:
        scheme = val.split(":", 1)[0].lower().strip()
        if scheme not in ("http", "https"):
            raise ValueError(f"{field_name} must use http or https scheme.")
    if re.search(r"[\r\n\t<>\"']", val):
        raise ValueError(f"{field_name} contains invalid or unsafe characters.")
    return val


def validate_email_field(email: Optional[str], max_len: int = 254) -> str:
    """Validates email format if provided; allows empty string."""
    if not email:
        return ""
    val = str(email).strip()
    if not val:
        return ""
    if len(val) > max_len:
        raise ValueError(f"Email exceeds maximum length of {max_len} characters.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", val):
        raise ValueError("Invalid email address format.")
    return val


class ProfileDTO(BaseModel):
    full_name: Optional[str] = Field(default="", alias="fullName", max_length=150)
    headline: Optional[str] = Field(default="", max_length=200)
    email: Optional[str] = Field(default="", max_length=254)
    phone: Optional[str] = Field(default="", max_length=50)
    location: Optional[str] = Field(default="", max_length=150)
    website: Optional[str] = Field(default="", max_length=500)
    linkedin: Optional[str] = Field(default="", max_length=500)
    github: Optional[str] = Field(default="", max_length=500)
    summary: Optional[str] = Field(default="", max_length=5000)
    target_roles: List[str] = Field(default_factory=list, alias="targetRoles", max_length=30)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("full_name", "headline", "phone", "location", "summary", mode="before")
    @classmethod
    def clean_text_fields(cls, v):
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return validate_email_field(v)

    @field_validator("website", mode="before")
    @classmethod
    def check_website(cls, v):
        return validate_url_field(v, "Personal website")

    @field_validator("linkedin", mode="before")
    @classmethod
    def check_linkedin(cls, v):
        return validate_url_field(v, "LinkedIn URL")

    @field_validator("github", mode="before")
    @classmethod
    def check_github(cls, v):
        return validate_url_field(v, "GitHub URL")

    @field_validator("target_roles", mode="before")
    @classmethod
    def clean_target_roles(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("targetRoles must be a list of strings.")
        if len(v) > 30:
            raise ValueError("targetRoles cannot exceed 30 items.")
        cleaned = []
        seen = set()
        for item in v:
            if not isinstance(item, str):
                continue
            role = item.strip()
            if not role:
                continue
            if len(role) > 100:
                raise ValueError("Target role item exceeds maximum length of 100 characters.")
            if role.lower() not in seen:
                seen.add(role.lower())
                cleaned.append(role)
        return cleaned


class ProfileResponse(BaseModel):
    success: bool = True
    profile: ProfileDTO
    message: Optional[str] = "Profile saved successfully."

    model_config = ConfigDict(populate_by_name=True)
