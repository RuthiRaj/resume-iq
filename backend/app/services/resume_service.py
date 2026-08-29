import requests
from typing import Dict, Any, Optional, List
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.analyze import AnalyzeResponse


def _decode_firestore_value(val: Any) -> Any:
    """Decodes a single Firestore REST JSON field value to a native Python object."""
    if not isinstance(val, dict):
        return val
    if "stringValue" in val:
        return val["stringValue"]
    if "booleanValue" in val:
        return val["booleanValue"]
    if "integerValue" in val:
        return int(val["integerValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "timestampValue" in val:
        return val["timestampValue"]
    if "nullValue" in val:
        return None
    if "arrayValue" in val:
        values = val.get("arrayValue", {}).get("values", [])
        return [_decode_firestore_value(v) for v in values]
    if "mapValue" in val:
        fields = val.get("mapValue", {}).get("fields", {})
        return {k: _decode_firestore_value(v) for k, v in fields.items()}
    return val


def _decode_firestore_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Decodes all fields in a Firestore REST document."""
    fields = doc.get("fields", {})
    return {k: _decode_firestore_value(v) for k, v in fields.items()}


def _encode_firestore_value(val: Any) -> Dict[str, Any]:
    """Encodes a native Python value into Firestore REST JSON format."""
    if val is None:
        return {"nullValue": None}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, list):
        return {
            "arrayValue": {
                "values": [_encode_firestore_value(v) for v in val]
            }
        }
    if isinstance(val, dict):
        return {
            "mapValue": {
                "fields": {k: _encode_firestore_value(v) for k, v in val.items()}
            }
        }
    return {"stringValue": str(val)}


def _encode_firestore_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """Encodes a dictionary of fields into a Firestore REST fields map."""
    return {k: _encode_firestore_value(v) for k, v in data.items()}


def _get_firestore_base_url() -> str:
    return f"https://firestore.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/databases/(default)/documents"


async def load_master_profile(user: AuthenticatedUser) -> CandidateEvidence:
    """Loads the candidate's master profile from Firestore."""
    base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
    headers = {"Authorization": f"Bearer {user.token}"}

    # 1. Main Profile
    profile_data: Dict[str, Any] = {}
    try:
        res = requests.get(f"{base_url}/profile/main", headers=headers, timeout=10)
        if res.status_code == 200:
            profile_data = _decode_firestore_doc(res.json())
    except Exception:
        pass

    # 2. Subcollections helper
    def fetch_subcollection(name: str) -> List[Dict[str, Any]]:
        try:
            res = requests.get(f"{base_url}/{name}", headers=headers, timeout=10)
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                return [_decode_firestore_doc(d) for d in docs]
        except Exception:
            pass
        return []

    exp_docs = fetch_subcollection("experience")
    proj_docs = fetch_subcollection("projects")
    skill_docs = fetch_subcollection("skills")
    edu_docs = fetch_subcollection("education")
    cert_docs = fetch_subcollection("certifications")

    experience = [
        ExperienceItem(
            role=d.get("role", ""),
            company=d.get("company", ""),
            location=d.get("location", ""),
            start_date=d.get("startDate", ""),
            end_date="Present" if d.get("isCurrent") else d.get("endDate", ""),
            bullets=d.get("bullets", []),
            technologies=d.get("technologies", []),
        )
        for d in exp_docs
    ]

    projects = [
        ProjectItem(
            title=d.get("title", ""),
            role=d.get("role", ""),
            description=d.get("description", ""),
            highlights=d.get("highlights", []),
            tech_stack=d.get("techStack", []),
        )
        for d in proj_docs
    ]

    skills = [
        SkillItem(
            name=d.get("name", ""),
            category=d.get("category", "Technical"),
            proficiency=d.get("proficiency", "Intermediate"),
        )
        for d in skill_docs
    ]

    education = [
        EducationItem(
            degree=d.get("degree", ""),
            institution=d.get("institution", ""),
            field_of_study=d.get("fieldOfStudy", ""),
        )
        for d in edu_docs
    ]

    certifications = [
        CertificationItem(
            title=d.get("title", ""),
            issuer=d.get("issuer", ""),
        )
        for d in cert_docs
    ]

    return CandidateEvidence(
        headline=profile_data.get("headline", ""),
        summary=profile_data.get("summary", ""),
        experience=experience,
        projects=projects,
        skills=skills,
        education=education,
        certifications=certifications,
    )


async def get_candidate_resume_data(
    user: AuthenticatedUser, resume_id: str
) -> CandidateEvidence:
    """
    Resolves candidate resume evidence strictly from Firestore scoped to user.uid.
    Prioritizes immutable resume.snapshot; falls back to master profile.
    """
    if resume_id == "workspace":
        return await load_master_profile(user)

    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}"}

    try:
        res = requests.get(doc_url, headers=headers, timeout=10)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to communicate with Firestore: {str(e)}",
        )

    if res.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID '{resume_id}' was not found or is inaccessible.",
        )
    elif res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if res.status_code == 403 else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Access denied or error loading resume document.",
        )

    resume_data = _decode_firestore_doc(res.json())
    snapshot = resume_data.get("snapshot")

    # Priority 1: Immutable Snapshot
    if snapshot and isinstance(snapshot, dict):
        profile = snapshot.get("profile", {})
        experiences = [
            ExperienceItem(
                role=e.get("role", ""),
                company=e.get("company", ""),
                location=e.get("location", ""),
                start_date=e.get("startDate", ""),
                end_date="Present" if e.get("isCurrent") else e.get("endDate", ""),
                bullets=e.get("bullets", []),
                technologies=e.get("technologies", []),
            )
            for e in snapshot.get("experience", [])
        ]
        projects = [
            ProjectItem(
                title=p.get("title", ""),
                role=p.get("role", ""),
                description=p.get("description", ""),
                highlights=p.get("highlights", []),
                tech_stack=p.get("techStack", []),
            )
            for p in snapshot.get("projects", [])
        ]
        skills = [
            SkillItem(
                name=s.get("name", ""),
                category=s.get("category", "Technical"),
                proficiency=s.get("proficiency", "Intermediate"),
            )
            for s in snapshot.get("skills", [])
        ]
        education = [
            EducationItem(
                degree=ed.get("degree", ""),
                institution=ed.get("institution", ""),
                field_of_study=ed.get("fieldOfStudy", ""),
            )
            for ed in snapshot.get("education", [])
        ]
        certifications = [
            CertificationItem(
                title=c.get("title", ""),
                issuer=c.get("issuer", ""),
            )
            for c in snapshot.get("certifications", [])
        ]

        return CandidateEvidence(
            headline=profile.get("headline", ""),
            summary=snapshot.get("customSummary") or profile.get("summary", ""),
            experience=experiences,
            projects=projects,
            skills=skills,
            education=education,
            certifications=certifications,
        )

    # Priority 2: Legacy fallback
    return await load_master_profile(user)


async def persist_analysis_results(
    user: AuthenticatedUser, resume_id: str, analysis: AnalyzeResponse
) -> None:
    """Persists analysis results to the user's Firestore document."""
    if resume_id == "workspace":
        return

    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}

    update_payload = {
        "score": analysis.ats_score,
        "atsScore": analysis.ats_score,
        "scoreBreakdown": analysis.score_breakdown.model_dump(by_alias=True),
        "lastAnalyzedAt": analysis.metadata.analyzed_at,
        "targetRole": analysis.metadata.target_role,
        "targetCompany": analysis.metadata.target_company or "",
        "analysisResults": {
            "summaryFeedback": analysis.summary_feedback,
            "matchingSkills": [s.model_dump(by_alias=True) for s in analysis.matching_skills],
            "missingSkills": [s.model_dump(by_alias=True) for s in analysis.missing_skills],
            "partialSkills": [s.model_dump(by_alias=True) for s in analysis.partial_skills],
            "metadata": analysis.metadata.model_dump(by_alias=True),
        },
    }
    fields_body = {"fields": _encode_firestore_fields(update_payload)}

    try:
        existing = requests.get(doc_url, headers=headers, timeout=10)
        existing_fields = existing.json().get("fields", {}) if existing.status_code == 200 else {}
        merged_fields = {**existing_fields, **fields_body["fields"]}
        requests.patch(doc_url, headers=headers, json={"fields": merged_fields}, timeout=10)
    except Exception as e:
        print(f"Warning: Failed to persist analysis to Firestore: {e}")


async def get_resume_document(
    user: AuthenticatedUser, resume_id: str
) -> Optional[Dict[str, Any]]:
    """Retrieves raw decoded resume document from Firestore."""
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}"}
    try:
        res = requests.get(doc_url, headers=headers, timeout=10)
        if res.status_code == 200:
            return _decode_firestore_doc(res.json())
    except Exception:
        pass
    return None


async def save_resume_snapshot(
    user: AuthenticatedUser, resume_id: str, resume_data: Dict[str, Any]
) -> bool:
    """Saves or updates a resume document with its snapshot in Firestore."""
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
    fields_body = {"fields": _encode_firestore_fields(resume_data)}
    try:
        res = requests.patch(doc_url, headers=headers, json=fields_body, timeout=10)
        return res.status_code in (200, 201)
    except Exception as e:
        print(f"Error saving resume snapshot: {e}")
        return False


class ResumeService:
    get_candidate_resume_data = staticmethod(get_candidate_resume_data)
    persist_analysis_results = staticmethod(persist_analysis_results)
    get_resume_document = staticmethod(get_resume_document)
    save_resume_snapshot = staticmethod(save_resume_snapshot)
