import pytest
import jwt
import time
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.core.auth import get_authenticated_user, AuthenticatedUser


@pytest.mark.asyncio
async def test_auth_missing_credentials_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user(None)
    assert exc_info.value.status_code == 401
    assert "Missing Authorization header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_auth_empty_token_raises_401():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user(creds)
    assert exc_info.value.status_code == 401
    assert "Bearer token is empty" in exc_info.value.detail


@pytest.mark.asyncio
async def test_auth_invalid_token_format_raises_401():
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not_a_valid_jwt")
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user(creds)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_valid_mock_jwt_decodes_uid(monkeypatch):
    class MockSigningKey:
        key = "mock_public_key"

    class MockJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return MockSigningKey()

    from app.core import auth

    monkeypatch.setattr(auth, "get_jwks_client", lambda: MockJWKSClient())

    def mock_jwt_decode(token, key, algorithms, audience, issuer, options):
        return {
            "sub": "user_123_verified",
            "email": "test@resumeiq.com",
            "exp": time.time() + 3600,
            "iat": time.time(),
            "aud": "resumeiq-3cfe6",
            "iss": "https://securetoken.google.com/resumeiq-3cfe6",
        }

    monkeypatch.setattr(jwt, "decode", mock_jwt_decode)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid_mock_token")
    user = await get_authenticated_user(creds)
    assert isinstance(user, AuthenticatedUser)
    assert user.uid == "user_123_verified"
    assert user.email == "test@resumeiq.com"
    assert user.token == "valid_mock_token"


@pytest.mark.asyncio
async def test_auth_expired_jwt_raises_401(monkeypatch):
    class MockSigningKey:
        key = "mock_public_key"

    class MockJWKSClient:
        def get_signing_key_from_jwt(self, token):
            return MockSigningKey()

    from app.core import auth

    monkeypatch.setattr(auth, "get_jwks_client", lambda: MockJWKSClient())

    def mock_jwt_decode_expired(*args, **kwargs):
        raise jwt.ExpiredSignatureError("Signature has expired")

    monkeypatch.setattr(jwt, "decode", mock_jwt_decode_expired)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired_token")
    with pytest.raises(HTTPException) as exc_info:
        await get_authenticated_user(creds)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()
