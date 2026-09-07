import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.auth import AuthenticatedUser
from app.schemas.profile import ProfileDTO, ProfileResponse
from app.services.resume_service import (
    get_http_client,
    _get_firestore_base_url,
    _decode_firestore_doc,
    _encode_firestore_fields,
)


class ProfileService:

    @staticmethod
    async def get_profile(user: AuthenticatedUser) -> ProfileDTO:
        """Loads personal profile document for the authenticated user from Firestore."""
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/profile/main"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        for attempt in range(2):
            try:
                res = await client.get(doc_url, headers=headers, timeout=25.0)
                if res.status_code == 200:
                    decoded = _decode_firestore_doc(res.json())
                    return ProfileDTO.model_validate(decoded)
                elif res.status_code == 404:
                    # Profile has not been created yet in Firestore
                    break
                else:
                    if attempt == 0:
                        continue
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Profile persistence service timed out.",
                )
            except Exception as e:
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to fetch profile: {str(e)}",
                )

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

        fields_body = {"fields": _encode_firestore_fields(payload_dict)}

        for attempt in range(2):
            try:
                res = await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)
                if res.status_code in (200, 201):
                    decoded = _decode_firestore_doc(res.json())
                    saved_profile = ProfileDTO.model_validate(decoded)
                    return ProfileResponse(
                        success=True,
                        profile=saved_profile,
                        message="Profile saved successfully.",
                    )
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to persist profile in Firestore (status {res.status_code}).",
                )
            except HTTPException:
                raise
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Profile persistence service timed out during save.",
                )
            except Exception as e:
                if attempt == 0:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error saving profile: {str(e)}",
                )
