"""
Ingestion Service for ResumeIQ

Orchestrates document text extraction, structured AI candidate parsing,
persistence of reviewable pending ingestion drafts under users/{uid}/ingestions/{ingestion_id},
and safe master workspace hydration upon explicit user confirmation.
"""

import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.core.auth import AuthenticatedUser
from app.schemas.ingestion import (
    IngestionDraft,
    ParsedCandidateProfile,
    IngestionConfirmResponse,
)
from app.services.document_extractor import extract_document_text, sanitize_filename
from app.ai.ingestion_parser import parse_resume_text
from app.services.profile_service import ProfileService
from app.services.resume_service import (
    get_http_client,
    _get_firestore_base_url,
    _decode_firestore_doc,
    _encode_firestore_fields,
    _validate_safe_id,
)


class IngestionService:

    @staticmethod
    async def ingest_resume(
        user: AuthenticatedUser,
        filename: str,
        content: bytes,
    ) -> IngestionDraft:
        """
        Processes an uploaded resume binary (PDF, DOCX, TXT):
        1. Validates and extracts raw text securely.
        2. Executes AI parsing to construct a ParsedCandidateProfile draft.
        3. Persists the draft under users/{uid}/ingestions/{ingestion_id} in Firestore.
        4. Leaves master profile and candidate evidence collections completely UNTOUCHED.
        """
        clean_name = sanitize_filename(filename)
        raw_text = extract_document_text(filename=clean_name, content=content)

        ingestion_id = f"ingest_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Parse raw text into structured profile draft
        parsed_data = await parse_resume_text(raw_text)

        draft = IngestionDraft(
            ingestion_id=ingestion_id,
            document_name=clean_name,
            document_type="Resume",
            file_size_bytes=len(content),
            status="Parsed",
            raw_text_snippet=raw_text[:500] if raw_text else "",
            raw_text_char_count=len(raw_text),
            parsed_data=parsed_data,
            error_message=None,
            created_at=now_iso,
            updated_at=now_iso,
            completed_at=None,
        )

        # Store draft in Firestore under users/{uid}/ingestions/{ingestion_id}
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/ingestions/{ingestion_id}"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        client = get_http_client()

        payload_dict = draft.model_dump(by_alias=True)
        fields_body = {"fields": _encode_firestore_fields(payload_dict)}

        for attempt in range(2):
            try:
                res = await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)
                if res.status_code in (200, 201):
                    return draft
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to persist ingestion draft in Firestore (status {res.status_code}).",
                )
            except HTTPException:
                raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Ingestion persistence service timed out.",
                )
            except Exception as exc:
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist ingestion draft due to an internal error.",
                ) from exc

        return draft

    @staticmethod
    async def get_ingestion_draft(user: AuthenticatedUser, ingestion_id: str) -> IngestionDraft:
        """Loads a specific ingestion draft for the authenticated user from Firestore."""
        clean_id = ingestion_id.replace("/", "").replace("\\", "").strip()
        if not clean_id or not clean_id.startswith("ingest_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ingestion draft ID format.",
            )

        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/ingestions/{clean_id}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        for attempt in range(2):
            try:
                res = await client.get(doc_url, headers=headers, timeout=25.0)
                if res.status_code == 200:
                    decoded = _decode_firestore_doc(res.json())
                    return IngestionDraft.model_validate(decoded)
                elif res.status_code == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ingestion draft '{clean_id}' not found.",
                    )
                else:
                    if attempt == 0:
                        continue
            except HTTPException:
                raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Ingestion service timed out while fetching draft.",
                )
            except Exception as exc:
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve ingestion draft due to an internal error.",
                ) from exc

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion draft '{clean_id}' not found.",
        )

    @staticmethod
    async def confirm_and_hydrate_ingestion(
        user: AuthenticatedUser,
        ingestion_id: str,
        reviewed_data: ParsedCandidateProfile,
    ) -> IngestionConfirmResponse:
        """
        Confirms an ingestion draft and hydrates user-reviewed candidate data into master workspace:
        1. Verifies draft exists and is in 'Parsed' status (rejects duplicate confirmation).
        2. Merges/saves Profile data into users/{uid}/profile/main.
        3. Merges/saves Experience, Education, Skills, Projects, and Certifications into users/{uid}/{collection}.
        4. Updates draft status to 'Completed'.
        5. Failure safety: Subcollection writes complete before status update.
        """
        clean_id = ingestion_id.replace("/", "").replace("\\", "").strip()
        if not clean_id or not clean_id.startswith("ingest_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ingestion draft ID format.",
            )

        draft = await IngestionService.get_ingestion_draft(user, clean_id)

        if draft.status == "Completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ingestion draft has already been confirmed and imported into master workspace.",
            )

        if draft.status not in ("Parsed", "Pending"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ingestion draft with status '{draft.status}' cannot be confirmed.",
            )

        base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        client = get_http_client()

        summary: Dict[str, int] = {
            "profileUpdated": 0,
            "experience": 0,
            "education": 0,
            "skills": 0,
            "projects": 0,
            "certifications": 0,
        }

        # Helper to fetch subcollection documents
        async def _fetch_subcollection(col_name: str) -> List[Dict[str, Any]]:
            try:
                res = await client.get(f"{base_url}/{col_name}", headers=headers)
                if res.status_code == 200:
                    docs = res.json().get("documents", [])
                    return [_decode_firestore_doc(d) for d in docs]
            except Exception:
                pass
            return []

        # Helper to patch or put document
        async def _save_doc(col_name: str, doc_id: str, payload_dict: Dict[str, Any]) -> None:
            doc_url = f"{base_url}/{col_name}/{doc_id}"
            fields_body = {"fields": _encode_firestore_fields(payload_dict)}
            res = await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)
            if res.status_code not in (200, 201):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save {col_name} entity to master workspace (status {res.status_code}).",
                )

        # 1. Hydrate Profile
        if reviewed_data.profile:
            await ProfileService.save_profile(user, reviewed_data.profile)
            summary["profileUpdated"] = 1

        # 2. Hydrate Experience
        existing_exp = await _fetch_subcollection("experience")
        exp_map = {
            f"{d.get('company', '').strip().lower()}:{d.get('role', '').strip().lower()}": d.get("id")
            for d in existing_exp
            if d.get("company") and d.get("role")
        }

        for exp in reviewed_data.evidence.experience:
            if not exp.role and not exp.company:
                continue
            key = f"{(exp.company or '').strip().lower()}:{(exp.role or '').strip().lower()}"
            matched_id = exp_map.get(key) or f"exp_ingest_{uuid.uuid4().hex[:8]}"
            payload = {
                "role": exp.role or "",
                "company": exp.company or "",
                "location": exp.location or "",
                "startDate": exp.start_date or "",
                "endDate": exp.end_date or "",
                "isCurrent": (exp.end_date or "").strip().lower() in ("present", "current"),
                "bullets": exp.bullets or [],
                "technologies": exp.technologies or [],
            }
            await _save_doc("experience", matched_id, payload)
            summary["experience"] += 1

        # 3. Hydrate Education
        existing_edu = await _fetch_subcollection("education")
        edu_map = {
            f"{d.get('institution', '').strip().lower()}:{d.get('degree', '').strip().lower()}": d.get("id")
            for d in existing_edu
            if d.get("institution") and d.get("degree")
        }

        for edu in reviewed_data.evidence.education:
            if not edu.degree and not edu.institution:
                continue
            key = f"{(edu.institution or '').strip().lower()}:{(edu.degree or '').strip().lower()}"
            matched_id = edu_map.get(key) or f"edu_ingest_{uuid.uuid4().hex[:8]}"
            payload = {
                "degree": edu.degree or "",
                "institution": edu.institution or "",
                "fieldOfStudy": edu.field_of_study or "",
            }
            await _save_doc("education", matched_id, payload)
            summary["education"] += 1

        # 4. Hydrate Skills
        existing_skills = await _fetch_subcollection("skills")
        skill_map = {
            d.get("name", "").strip().lower(): d.get("id")
            for d in existing_skills
            if d.get("name")
        }

        for sk in reviewed_data.evidence.skills:
            if not sk.name:
                continue
            key = sk.name.strip().lower()
            matched_id = skill_map.get(key) or f"skill_ingest_{uuid.uuid4().hex[:8]}"
            payload = {
                "name": sk.name,
                "category": sk.category or "Technical",
                "proficiency": sk.proficiency or "Intermediate",
            }
            await _save_doc("skills", matched_id, payload)
            summary["skills"] += 1

        # 5. Hydrate Projects
        existing_proj = await _fetch_subcollection("projects")
        proj_map = {
            d.get("title", "").strip().lower(): d.get("id")
            for d in existing_proj
            if d.get("title")
        }

        for proj in reviewed_data.evidence.projects:
            if not proj.title:
                continue
            key = proj.title.strip().lower()
            matched_id = proj_map.get(key) or f"proj_ingest_{uuid.uuid4().hex[:8]}"
            payload = {
                "title": proj.title,
                "role": proj.role or "",
                "description": proj.description or "",
                "highlights": proj.highlights or [],
                "techStack": proj.tech_stack or [],
            }
            await _save_doc("projects", matched_id, payload)
            summary["projects"] += 1

        # 6. Hydrate Certifications
        existing_cert = await _fetch_subcollection("certifications")
        cert_map = {
            f"{d.get('title', '').strip().lower()}:{d.get('issuer', '').strip().lower()}": d.get("id")
            for d in existing_cert
            if d.get("title")
        }

        for cert in reviewed_data.evidence.certifications:
            if not cert.title:
                continue
            key = f"{(cert.title or '').strip().lower()}:{(cert.issuer or '').strip().lower()}"
            matched_id = cert_map.get(key) or f"cert_ingest_{uuid.uuid4().hex[:8]}"
            payload = {
                "title": cert.title,
                "issuer": cert.issuer or "",
            }
            await _save_doc("certifications", matched_id, payload)
            summary["certifications"] += 1

        # 7. Mark Draft as Completed
        now_iso = datetime.now(timezone.utc).isoformat()
        draft_doc_url = f"{base_url}/ingestions/{clean_id}"
        draft_update_payload = {
            "status": "Completed",
            "parsedData": reviewed_data.model_dump(by_alias=True),
            "updatedAt": now_iso,
            "completedAt": now_iso,
        }
        draft_fields = {"fields": _encode_firestore_fields(draft_update_payload)}
        await client.patch(draft_doc_url, headers=headers, json=draft_fields, timeout=25.0)

        return IngestionConfirmResponse(
            success=True,
            ingestion_id=clean_id,
            status="Completed",
            message="Candidate career evidence successfully imported into master workspace.",
            hydrated_summary=summary,
        )
