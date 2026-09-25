import re
import asyncio
import httpx
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
    AchievementItem,
    InternshipItem,
    PublicationItem,
    AwardItem,
    VolunteeringItem,
)
from app.schemas.analyze import AnalyzeResponse
from app.core.logging import get_logger

logger = get_logger("app.services.resume_service")


def _validate_safe_id(val: str, field_name: str = "ID") -> str:
    """Validates that an identifier contains only safe alphanumeric characters, underscores, or hyphens."""
    if not val or not re.match(r"^[a-zA-Z0-9_\-]+$", val):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: must contain only alphanumeric characters, underscores, or hyphens.",
        )
    return val


_async_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Provides a thread-safe, persistent httpx.AsyncClient with connection pooling."""
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=30.0),
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
    return _async_client


async def close_http_client() -> None:
    """Closes the shared httpx.AsyncClient during application shutdown."""
    global _async_client
    if _async_client is not None and not _async_client.is_closed:
        await _async_client.aclose()
        _async_client = None


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
    res = {k: _decode_firestore_value(v) for k, v in fields.items()}
    if "id" not in res and "name" in doc:
        res["id"] = doc["name"].split("/")[-1]
    return res


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
    """
    Loads the candidate's master profile and subcollections from Firestore concurrently.
    Reuses connection pool to execute all 6 queries in parallel without blocking the event loop.
    """
    base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
    headers = {"Authorization": f"Bearer {user.token}"}
    client = get_http_client()

    async def _fetch_doc(url: str) -> Dict[str, Any]:
        try:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return _decode_firestore_doc(res.json())
            elif res.status_code != 404:
                logger.warning(
                    f"Firestore document fetch returned status {res.status_code}",
                    extra={"event": "firestore_read_error", "status_code": res.status_code, "component": "resume_service"},
                )
        except Exception as e:
            logger.warning(
                f"Failed to fetch Firestore doc: {str(e)}",
                extra={"event": "firestore_read_error", "error_type": type(e).__name__, "component": "resume_service"},
            )
        return {}

    async def _fetch_subcollection(url: str) -> List[Dict[str, Any]]:
        try:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                return [_decode_firestore_doc(d) for d in docs]
            elif res.status_code != 404:
                logger.warning(
                    f"Firestore subcollection fetch returned status {res.status_code}",
                    extra={"event": "firestore_read_error", "status_code": res.status_code, "component": "resume_service"},
                )
        except Exception as e:
            logger.warning(
                f"Failed to fetch Firestore subcollection: {str(e)}",
                extra={"event": "firestore_read_error", "error_type": type(e).__name__, "component": "resume_service"},
            )
        return []

    # Concurrent fetch across profile and all 10 subcollections
    profile_data, exp_docs, proj_docs, skill_docs, edu_docs, cert_docs, ach_docs, intern_docs, pub_docs, award_docs, vol_docs = await asyncio.gather(
        _fetch_doc(f"{base_url}/profile/main"),
        _fetch_subcollection(f"{base_url}/experience"),
        _fetch_subcollection(f"{base_url}/projects"),
        _fetch_subcollection(f"{base_url}/skills"),
        _fetch_subcollection(f"{base_url}/education"),
        _fetch_subcollection(f"{base_url}/certifications"),
        _fetch_subcollection(f"{base_url}/achievements"),
        _fetch_subcollection(f"{base_url}/internships"),
        _fetch_subcollection(f"{base_url}/publications"),
        _fetch_subcollection(f"{base_url}/awards"),
        _fetch_subcollection(f"{base_url}/volunteering"),
    )

    experience = [
        ExperienceItem(
            id=d.get("id", f"exp_{i}"),
            role=d.get("role", ""),
            company=d.get("company", ""),
            location=d.get("location", ""),
            start_date=d.get("startDate", ""),
            end_date="Present" if d.get("isCurrent") else d.get("endDate", ""),
            bullets=d.get("bullets", []),
            technologies=d.get("technologies", []),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(exp_docs)
    ]

    projects = [
        ProjectItem(
            id=d.get("id", f"proj_{i}"),
            title=d.get("title", ""),
            role=d.get("role", ""),
            description=d.get("description", ""),
            highlights=d.get("highlights", []),
            tech_stack=d.get("techStack", []),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(proj_docs)
    ]

    skills = [
        SkillItem(
            id=d.get("id", f"skill_{i}"),
            name=d.get("name", ""),
            category=d.get("category", "Technical"),
            proficiency=d.get("proficiency", "Intermediate"),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(skill_docs)
    ]

    education = [
        EducationItem(
            id=d.get("id", f"edu_{i}"),
            degree=d.get("degree", ""),
            institution=d.get("institution", ""),
            field_of_study=d.get("fieldOfStudy", ""),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(edu_docs)
    ]

    certifications = [
        CertificationItem(
            id=d.get("id", f"cert_{i}"),
            title=d.get("title", ""),
            issuer=d.get("issuer", ""),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(cert_docs)
    ]

    achievements = [
        AchievementItem(
            id=d.get("id", f"ach_{i}"),
            title=d.get("title", ""),
            issuer=d.get("issuer", ""),
            date=d.get("date", ""),
            description=d.get("description", ""),
            url=d.get("url", ""),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(ach_docs)
    ]

    internships = [
        InternshipItem(
            id=d.get("id", f"intern_{i}"),
            role=d.get("role", ""),
            company=d.get("company", ""),
            location=d.get("location", ""),
            start_date=d.get("startDate", ""),
            end_date="Present" if d.get("isCurrent") else d.get("endDate", ""),
            bullets=d.get("bullets", []),
            technologies=d.get("technologies", []),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(intern_docs)
    ]

    publications = [
        PublicationItem(
            id=d.get("id", f"pub_{i}"),
            title=d.get("title", ""),
            publisher=d.get("publisher", ""),
            publication_date=d.get("publicationDate", ""),
            url=d.get("url", ""),
            description=d.get("description", ""),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(pub_docs)
    ]

    awards = [
        AwardItem(
            id=d.get("id", f"award_{i}"),
            title=d.get("title", ""),
            issuer=d.get("issuer", ""),
            date=d.get("date", ""),
            description=d.get("description", ""),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(award_docs)
    ]

    volunteering = [
        VolunteeringItem(
            id=d.get("id", f"vol_{i}"),
            role=d.get("role", ""),
            organization=d.get("organization", ""),
            start_date=d.get("startDate", ""),
            end_date=d.get("endDate", ""),
            description=d.get("description", ""),
            highlights=d.get("highlights", []),
            source_document_id=d.get("sourceDocumentId"),
            source_document_name=d.get("sourceDocumentName"),
        )
        for i, d in enumerate(vol_docs)
    ]

    return CandidateEvidence(
        headline=profile_data.get("headline", ""),
        summary=profile_data.get("summary", ""),
        experience=experience,
        projects=projects,
        skills=skills,
        education=education,
        certifications=certifications,
        achievements=achievements,
        internships=internships,
        publications=publications,
        awards=awards,
        volunteering=volunteering,
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

    _validate_safe_id(resume_id, "resume ID")
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}"}
    client = get_http_client()

    try:
        res = await client.get(doc_url, headers=headers)
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
        achievements = [
            AchievementItem(
                id=a.get("id"),
                title=a.get("title", ""),
                issuer=a.get("issuer", ""),
                date=a.get("date", ""),
                description=a.get("description", ""),
                url=a.get("url", ""),
            )
            for a in snapshot.get("achievements", [])
        ]

        return CandidateEvidence(
            headline=profile.get("headline", ""),
            summary=snapshot.get("customSummary") or profile.get("summary", ""),
            experience=experiences,
            projects=projects,
            skills=skills,
            education=education,
            certifications=certifications,
            achievements=achievements,
        )

    # Priority 2: Legacy fallback
    return await load_master_profile(user)


async def persist_analysis_results(
    user: AuthenticatedUser, resume_id: str, analysis: AnalyzeResponse
) -> None:
    """Persists analysis results to the user's Firestore document asynchronously."""
    if resume_id == "workspace":
        return

    _validate_safe_id(resume_id, "resume ID")
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
    client = get_http_client()

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
            "jobIntelligence": analysis.job_intelligence.model_dump(by_alias=True) if analysis.job_intelligence else None,
            "requirementMatches": [m.model_dump(by_alias=True) for m in analysis.requirement_matches],
            "remediationSuggestions": [s.model_dump(by_alias=True) for s in analysis.remediation_suggestions],
            "metadata": analysis.metadata.model_dump(by_alias=True),
        },
    }
    fields_body = {"fields": _encode_firestore_fields(update_payload)}

    try:
        existing = await client.get(doc_url, headers=headers)
        existing_fields = existing.json().get("fields", {}) if existing.status_code == 200 else {}
        merged_fields = {**existing_fields, **fields_body["fields"]}
        await client.patch(doc_url, headers=headers, json={"fields": merged_fields})
    except Exception as e:
        logger.warning(
            f"Failed to persist analysis to Firestore: {str(e)}",
            extra={"event": "firestore_write_error", "error_type": type(e).__name__, "component": "resume_service"},
        )


async def get_resume_document(
    user: AuthenticatedUser, resume_id: str
) -> Optional[Dict[str, Any]]:
    """Retrieves raw decoded resume document from Firestore asynchronously."""
    _validate_safe_id(resume_id, "resume ID")
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}"}
    client = get_http_client()
    try:
        res = await client.get(doc_url, headers=headers)
        if res.status_code == 200:
            return _decode_firestore_doc(res.json())
        elif res.status_code != 404:
            logger.warning(
                f"Firestore get_resume_document returned status {res.status_code}",
                extra={"event": "firestore_read_error", "status_code": res.status_code, "component": "resume_service"},
            )
    except Exception as e:
        logger.warning(
            f"Failed to get resume document: {str(e)}",
            extra={"event": "firestore_read_error", "error_type": type(e).__name__, "component": "resume_service"},
        )
    return None


async def save_resume_snapshot(
    user: AuthenticatedUser, resume_id: str, resume_data: Dict[str, Any]
) -> bool:
    """Saves or updates a resume document with its snapshot in Firestore asynchronously."""
    _validate_safe_id(resume_id, "resume ID")
    doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/resumes/{resume_id}"
    headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
    fields_body = {"fields": _encode_firestore_fields(resume_data)}
    client = get_http_client()
    try:
        res = await client.patch(doc_url, headers=headers, json=fields_body)
        return res.status_code in (200, 201)
    except Exception as e:
        logger.error(
            f"Error saving resume snapshot: {str(e)}",
            extra={"event": "firestore_write_error", "error_type": type(e).__name__, "component": "resume_service"},
        )
        return False


class ResumeService:
    get_candidate_resume_data = staticmethod(get_candidate_resume_data)
    persist_analysis_results = staticmethod(persist_analysis_results)
    get_resume_document = staticmethod(get_resume_document)
    save_resume_snapshot = staticmethod(save_resume_snapshot)
