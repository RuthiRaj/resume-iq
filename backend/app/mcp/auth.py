"""
MCP Authentication helper for ResumeIQ.

Extracts and validates the Firebase ID Token from the incoming MCP HTTP request
using exactly the same JWT validation path as the existing FastAPI REST layer.

The UID is ALWAYS derived from the verified token — never from a caller-supplied
parameter. This preserves strict tenant isolation.
"""
import jwt
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR

from app.core.auth import AuthenticatedUser, get_jwks_client
from app.core.config import settings


def _extract_bearer_token(ctx: Context) -> str:
    """
    Extracts the raw Firebase ID token from the MCP request's Authorization header.
    Raises MCPError(INVALID_PARAMS) if the header is absent or malformed.
    """
    headers = ctx.headers
    if not headers:
        raise MCPError(
            INVALID_PARAMS,
            "Missing Authorization header. Pass 'Authorization: Bearer <Firebase_ID_Token>'.",
        )

    auth_header: Optional[str] = headers.get("authorization") or headers.get("Authorization")
    if not auth_header:
        raise MCPError(
            INVALID_PARAMS,
            "Missing Authorization header. Pass 'Authorization: Bearer <Firebase_ID_Token>'.",
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise MCPError(
            INVALID_PARAMS,
            "Malformed Authorization header. Expected 'Bearer <Firebase_ID_Token>'.",
        )

    return parts[1].strip()


def resolve_mcp_user(ctx: Context) -> AuthenticatedUser:
    """
    Validates the Firebase ID Token from the MCP request context.

    Uses the identical JWT validation path as the REST layer:
    - PyJWKClient against Google's public JWKS endpoint
    - RS256 signature, expiration, issuer, and audience checks
    - UID extracted from verified 'sub' claim only

    Returns AuthenticatedUser on success.
    Raises MCPError on any auth failure (no stack traces, no credentials leaked).
    """
    id_token = _extract_bearer_token(ctx)

    project_id = settings.FIREBASE_PROJECT_ID
    if not project_id:
        raise MCPError(INTERNAL_ERROR, "Backend Firebase project is not configured.")

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
            raise MCPError(INVALID_PARAMS, "Token validation failed: no valid UID found.")

        return AuthenticatedUser(
            uid=uid.strip(),
            token=id_token,
            email=decoded.get("email"),
        )

    except MCPError:
        raise
    except jwt.ExpiredSignatureError:
        raise MCPError(INVALID_PARAMS, "Firebase ID token has expired. Refresh your session.")
    except jwt.InvalidTokenError:
        raise MCPError(INVALID_PARAMS, "Invalid Firebase ID token.")
    except Exception:
        # Never leak internal details or credentials
        raise MCPError(INVALID_PARAMS, "Authentication failed. Provide a valid Firebase ID token.")
