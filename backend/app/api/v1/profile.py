from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.profile import ProfileDTO, ProfileResponse
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["Profile"])
account_router = APIRouter(prefix="/account", tags=["Account"])


@router.get("", response_model=ProfileDTO, summary="Get authenticated user's personal profile")
async def get_profile_endpoint(
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ProfileDTO:
    return await ProfileService.get_profile(current_user)


@router.post("", response_model=ProfileResponse, summary="Save or update authenticated user's personal profile")
@router.put("", response_model=ProfileResponse, summary="Save or update authenticated user's personal profile")
async def save_profile_endpoint(
    req: ProfileDTO,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ProfileResponse:
    return await ProfileService.save_profile(current_user, req)


@router.get("/export", summary="Export all authenticated candidate data in structured JSON format (GDPR)")
async def export_profile_endpoint(
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    return await ProfileService.export_user_data(current_user)


@account_router.delete("", summary="Permanently delete authenticated user account and all workspace data (GDPR Right to Erasure)")
@router.delete("", summary="Permanently delete authenticated user account and all workspace data")
async def delete_account_endpoint(
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    return await ProfileService.delete_account(current_user)
