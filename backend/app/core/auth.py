import jwt
from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

GOOGLE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    """Returns a singleton cached PyJWKClient for Google's public key certificates."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client


@dataclass
class AuthenticatedUser:
    uid: str
    token: str
    email: Optional[str] = None


async def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> AuthenticatedUser:
    """
    Cryptographically verifies the Firebase ID Token from Authorization Bearer header.
    Validates RSA signature against Google's public JWKS certificates, checks expiration,
    issuer, audience (project ID), and extracts the authenticated UID.
    """
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

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FIREBASE_PROJECT_ID is not configured on the backend server.",
        )

    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        decoded = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )

        uid = decoded.get("sub")
        if not uid or not isinstance(uid, str) or not uid.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed: No valid UID subject found in token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return AuthenticatedUser(
            uid=uid.strip(),
            token=id_token,
            email=decoded.get("email"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase ID token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_uid(
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> str:
    """Convenience dependency returning only the verified UID."""
    return user.uid
