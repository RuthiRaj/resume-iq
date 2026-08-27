from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from app.core.firebase import get_firebase_app

security_scheme = HTTPBearer(auto_error=False)


async def get_current_uid(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> str:
    """Verifies Firebase ID token from Authorization Bearer header and extracts UID."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected 'Bearer <Firebase_ID_Token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    id_token = credentials.credentials.strip()
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    get_firebase_app()

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed: No UID found in token.",
            )
        return uid
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase ID token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
