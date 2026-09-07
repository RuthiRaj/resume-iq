import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.profile import ProfileDTO, ProfileResponse
from app.services.profile_service import ProfileService

mock_user = AuthenticatedUser(uid="test_user_p123", email="user@resumeiq.test", token="mock_token_123")


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.asyncio
async def test_get_profile_service(monkeypatch):
    mock_doc = {
        "fields": {
            "fullName": {"stringValue": "Taylor Swift"},
            "website": {"stringValue": "https://taylor.dev"},
            "linkedin": {"stringValue": "https://linkedin.com/in/taylor"},
            "github": {"stringValue": "https://github.com/taylor"},
            "summary": {"stringValue": "Experienced distributed systems architect with 10+ years."},
            "targetRoles": {
                "arrayValue": {
                    "values": [
                        {"stringValue": "Platform Engineer"},
                        {"stringValue": "Staff Architect"},
                    ]
                }
            },
        }
    }

    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_doc
    mock_client.get.return_value = mock_resp

    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: mock_client)

    profile = await ProfileService.get_profile(mock_user)
    assert profile.full_name == "Taylor Swift"
    assert profile.website == "https://taylor.dev"
    assert profile.linkedin == "https://linkedin.com/in/taylor"
    assert profile.github == "https://github.com/taylor"
    assert profile.summary == "Experienced distributed systems architect with 10+ years."
    assert profile.target_roles == ["Platform Engineer", "Staff Architect"]


@pytest.mark.asyncio
async def test_save_profile_service(monkeypatch):
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "fields": {
            "fullName": {"stringValue": "Jordan Lee"},
            "website": {"stringValue": "https://jordan.io"},
            "linkedin": {"stringValue": "https://linkedin.com/in/jordan"},
            "github": {"stringValue": "https://github.com/jordan"},
            "summary": {"stringValue": "Cloud infrastructure engineer."},
            "targetRoles": {
                "arrayValue": {
                    "values": [
                        {"stringValue": "Cloud Architect"},
                        {"stringValue": "SRE Lead"},
                    ]
                }
            },
        }
    }
    mock_client.patch.return_value = mock_resp

    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: mock_client)

    req = ProfileDTO(
        fullName="Jordan Lee",
        website="https://jordan.io",
        linkedin="https://linkedin.com/in/jordan",
        github="https://github.com/jordan",
        summary="Cloud infrastructure engineer.",
        targetRoles=["Cloud Architect", "SRE Lead"],
    )

    res = await ProfileService.save_profile(mock_user, req)
    assert res.success is True
    assert res.profile.full_name == "Jordan Lee"
    assert res.profile.website == "https://jordan.io"
    assert res.profile.target_roles == ["Cloud Architect", "SRE Lead"]
    assert mock_client.patch.called


def test_profile_endpoints(override_auth, monkeypatch):
    client = TestClient(app)

    async def mock_get(user):
        return ProfileDTO(
            fullName="Alex Morgan",
            website="https://alex.dev",
            targetRoles=["Staff Engineer"],
        )

    async def mock_save(user, data):
        return ProfileResponse(
            success=True,
            profile=data,
            message="Profile saved successfully.",
        )

    monkeypatch.setattr(ProfileService, "get_profile", mock_get)
    monkeypatch.setattr(ProfileService, "save_profile", mock_save)

    # Test GET
    res_get = client.get("/api/v1/profile")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["fullName"] == "Alex Morgan"
    assert data["website"] == "https://alex.dev"

    # Test POST
    payload = {
        "fullName": "Alex Morgan",
        "website": "https://alexmorgan.tech",
        "targetRoles": ["Principal Architect", "VP Engineering"],
        "summary": "Engineering executive with deep cloud expertise.",
    }
    res_post = client.post("/api/v1/profile", json=payload)
    assert res_post.status_code == 200
    post_data = res_post.json()
    assert post_data["success"] is True
    assert post_data["profile"]["website"] == "https://alexmorgan.tech"
    assert post_data["profile"]["targetRoles"] == ["Principal Architect", "VP Engineering"]
