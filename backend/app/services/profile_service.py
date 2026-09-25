import httpx
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.auth import AuthenticatedUser
from app.core.logging import get_logger, get_request_id
from app.core.retry import async_retry_transient
from app.schemas.profile import ProfileDTO, ProfileResponse
from app.services.resume_service import (
    get_http_client,
    _get_firestore_base_url,
    _decode_firestore_doc,
    _encode_firestore_fields,
)

logger = get_logger("app.services.profile")

SUBCOLLECTIONS = [
    "experience",
    "projects",
    "skills",
    "education",
    "certifications",
    "achievements",
    "internships",
    "publications",
    "awards",
    "volunteering",
    "resumes",
    "roadmaps",
    "ingestions",
]


class ProfileService:

    @staticmethod
    async def get_profile(user: AuthenticatedUser) -> ProfileDTO:
        """Loads personal profile document for the authenticated user from Firestore."""
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/profile/main"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        async def _fetch():
            res = await client.get(doc_url, headers=headers, timeout=25.0)
            if res.status_code == 200:
                decoded = _decode_firestore_doc(res.json())
                return ProfileDTO.model_validate(decoded)
            elif res.status_code == 404:
                return None
            elif res.status_code in (429, 502, 503, 504):
                raise HTTPException(
                    status_code=res.status_code,
                    detail=f"Firestore returned transient status {res.status_code}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to retrieve profile (status {res.status_code}).",
                )

        try:
            profile = await async_retry_transient(_fetch, max_retries=2, operation_name="get_profile")
            if profile is not None:
                return profile
        except HTTPException as he:
            if he.status_code in (429, 502, 503, 504):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Profile persistence service is temporarily unavailable. Please retry.",
                )
            raise

        return ProfileDTO(
            email=user.email or "",
            full_name="",
            headline="",
            phone="",
            location="",
            website="",
            linkedin="",
            github="",
            summary="",
            target_roles=[],
        )

    @staticmethod
    async def save_profile(user: AuthenticatedUser, profile_data: ProfileDTO) -> ProfileResponse:
        """Saves personal profile document for the authenticated user in Firestore."""
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/profile/main"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        client = get_http_client()

        payload_dict = profile_data.model_dump(by_alias=True)
        if not payload_dict.get("email") and user.email:
            payload_dict["email"] = user.email

        mask_params = [f"updateMask.fieldPaths={k}" for k in payload_dict.keys()]
        patch_url = f"{doc_url}?{'&'.join(mask_params)}"
        fields_body = {"fields": _encode_firestore_fields(payload_dict)}

        async def _save():
            res = await client.patch(patch_url, headers=headers, json=fields_body, timeout=25.0)
            if res.status_code in (200, 201):
                decoded = _decode_firestore_doc(res.json())
                saved_profile = ProfileDTO.model_validate(decoded)
                return ProfileResponse(
                    success=True,
                    profile=saved_profile,
                    message="Profile saved successfully.",
                )
            elif res.status_code in (429, 502, 503, 504):
                raise HTTPException(
                    status_code=res.status_code,
                    detail=f"Firestore save returned transient status {res.status_code}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to persist profile in Firestore (status {res.status_code}).",
                )

        try:
            return await async_retry_transient(_save, max_retries=2, operation_name="save_profile")
        except HTTPException as he:
            if he.status_code in (429, 502, 503, 504):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Profile persistence service is temporarily unavailable. Please retry.",
                )
            raise

    @staticmethod
    async def export_user_data(user: AuthenticatedUser) -> Dict[str, Any]:
        """
        Exports all user-owned career data into a single structured, tenant-isolated JSON archive.
        GDPR Data Portability compliant. Strictly excludes credentials, keys, and internal telemetry.
        """
        base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        async def _fetch_doc(url: str) -> Dict[str, Any]:
            try:
                res = await client.get(url, headers=headers, timeout=20.0)
                if res.status_code == 200:
                    return _decode_firestore_doc(res.json())
            except Exception as e:
                logger.warning(f"Error reading doc during export: {e}", extra={"event": "export_read_warning"})
            return {}

        async def _fetch_subcollection(col_name: str) -> List[Dict[str, Any]]:
            try:
                url = f"{base_url}/{col_name}"
                res = await client.get(url, headers=headers, timeout=20.0)
                if res.status_code == 200:
                    docs = res.json().get("documents", [])
                    return [_decode_firestore_doc(d) for d in docs]
            except Exception as e:
                logger.warning(f"Error reading {col_name} during export: {e}", extra={"event": "export_read_warning"})
            return []

        # Read profile and all subcollections in parallel
        profile_task = _fetch_doc(f"{base_url}/profile/main")
        subcol_tasks = [_fetch_subcollection(c) for c in SUBCOLLECTIONS]

        results = await asyncio.gather(profile_task, *subcol_tasks)
        profile_data = results[0]
        subcol_data = {col_name: results[i + 1] for i, col_name in enumerate(SUBCOLLECTIONS)}

        logger.info(
            f"Exported candidate data for user {user.uid}",
            extra={"event": "user_data_export", "user_id": user.uid, "request_id": get_request_id()},
        )

        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user.uid,
            "email": user.email or "",
            "profile": profile_data,
            "master_workspace": {
                "experience": subcol_data.get("experience", []),
                "projects": subcol_data.get("projects", []),
                "skills": subcol_data.get("skills", []),
                "education": subcol_data.get("education", []),
                "certifications": subcol_data.get("certifications", []),
                "achievements": subcol_data.get("achievements", []),
                "internships": subcol_data.get("internships", []),
                "publications": subcol_data.get("publications", []),
                "awards": subcol_data.get("awards", []),
                "volunteering": subcol_data.get("volunteering", []),
            },
            "targeted_variants": subcol_data.get("resumes", []),
            "career_roadmaps": subcol_data.get("roadmaps", []),
            "ingestion_drafts": subcol_data.get("ingestions", []),
        }

    @staticmethod
    async def delete_account(user: AuthenticatedUser) -> Dict[str, Any]:
        """
        Deletes all user-owned records, subcollections, and profile documents in Firestore,
        plus Cloudinary uploads and Firebase Auth user account.
        GDPR Right to Erasure compliant. Strictly tenant-isolated to user.uid.
        """
        base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()
        total_deleted_docs = 0
        cleaned_collections: List[str] = []
        errors: List[str] = []

        # 1. Delete profile main document
        try:
            profile_url = f"{base_url}/profile/main"
            del_res = await client.delete(profile_url, headers=headers, timeout=15.0)
            if del_res.status_code in (200, 204):
                total_deleted_docs += 1
                cleaned_collections.append("profile")
            elif del_res.status_code != 404:
                errors.append(f"profile: status {del_res.status_code}")
        except Exception as e:
            logger.warning(f"Error deleting profile doc: {e}", extra={"event": "account_delete_warning"})
            errors.append(f"profile: {str(e)}")

        # 2. Delete all subcollection documents
        for col in SUBCOLLECTIONS:
            try:
                list_url = f"{base_url}/{col}"
                res = await client.get(list_url, headers=headers, timeout=20.0)
                if res.status_code == 200:
                    docs = res.json().get("documents", [])
                    col_had_err = False
                    for doc in docs:
                        doc_name = doc.get("name")
                        if doc_name:
                            doc_id = doc_name.split("/")[-1]
                            doc_del_url = f"{base_url}/{col}/{doc_id}"
                            del_res = await client.delete(doc_del_url, headers=headers, timeout=15.0)
                            if del_res.status_code in (200, 204):
                                total_deleted_docs += 1
                            elif del_res.status_code != 404:
                                col_had_err = True
                                errors.append(f"{col}/{doc_id}: status {del_res.status_code}")
                    if not col_had_err:
                        cleaned_collections.append(col)
                elif res.status_code == 404:
                    cleaned_collections.append(col)
                else:
                    errors.append(f"{col}: list status {res.status_code}")
            except Exception as e:
                logger.warning(f"Error deleting subcollection {col}: {e}", extra={"event": "account_delete_warning"})
                errors.append(f"{col}: {str(e)}")

        # 3. Clean up Cloudinary assets if configured
        try:
            if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
                import cloudinary
                import cloudinary.api
                cloudinary.config(
                    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                    api_key=settings.CLOUDINARY_API_KEY,
                    api_secret=settings.CLOUDINARY_API_SECRET,
                    secure=True,
                )
                # Delete files tagged with user_id or in user folder
                cloudinary.api.delete_resources_by_tag(f"user_{user.uid}")
                cleaned_collections.append("cloudinary_storage")
        except Exception as e:
            logger.warning(f"Cloudinary cleanup notice: {e}", extra={"event": "cloudinary_cleanup_warning"})
            errors.append(f"cloudinary: {str(e)}")

        # 4. Attempt Firebase Auth user deletion via Admin SDK if initialized
        try:
            import firebase_admin
            from firebase_admin import auth as admin_auth
            if firebase_admin._apps:
                admin_auth.delete_user(user.uid)
                cleaned_collections.append("firebase_auth")
        except Exception as e:
            logger.warning(f"Firebase Auth deletion notice: {e}", extra={"event": "firebase_auth_delete_warning"})
            errors.append(f"firebase_auth: {str(e)}")

        is_complete = (len(errors) == 0)

        logger.info(
            f"Purged account data for user {user.uid} (is_complete={is_complete})",
            extra={
                "event": "account_purged",
                "user_id": user.uid,
                "deleted_documents_count": total_deleted_docs,
                "is_complete": is_complete,
                "errors_count": len(errors),
                "request_id": get_request_id(),
            },
        )

        return {
            "success": is_complete,
            "user_id": user.uid,
            "deleted_documents_count": total_deleted_docs,
            "cleaned_collections": list(set(cleaned_collections)),
            "errors": errors,
            "message": "Account and all associated candidate workspace data successfully deleted." if is_complete else "Account deletion encountered partial warnings or errors.",
        }
