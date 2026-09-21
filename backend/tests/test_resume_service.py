import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
import httpx
from app.core.auth import AuthenticatedUser
from app.services.resume_service import (
    _decode_firestore_value,
    _decode_firestore_doc,
    _encode_firestore_value,
    _encode_firestore_fields,
    get_candidate_resume_data,
    load_master_profile,
    get_http_client,
)


def test_firestore_value_codec():
    # Test primitive types
    assert _decode_firestore_value({"stringValue": "hello"}) == "hello"
    assert _decode_firestore_value({"integerValue": "42"}) == 42
    assert _decode_firestore_value({"booleanValue": True}) is True
    assert _decode_firestore_value({"nullValue": None}) is None

    # Test arrays and maps
    raw_map = {
        "mapValue": {
            "fields": {
                "name": {"stringValue": "Alex"},
                "skills": {
                    "arrayValue": {
                        "values": [
                            {"stringValue": "Python"},
                            {"stringValue": "TypeScript"},
                        ]
                    }
                },
            }
        }
    }
    decoded = _decode_firestore_value(raw_map)
    assert decoded == {"name": "Alex", "skills": ["Python", "TypeScript"]}

    # Test encoder
    encoded = _encode_firestore_value({"score": 90, "active": True, "tags": ["AI"]})
    assert encoded["mapValue"]["fields"]["score"] == {"integerValue": "90"}
    assert encoded["mapValue"]["fields"]["active"] == {"booleanValue": True}
    assert encoded["mapValue"]["fields"]["tags"]["arrayValue"]["values"][0] == {"stringValue": "AI"}


@pytest.mark.asyncio
async def test_get_candidate_resume_data_snapshot_priority(monkeypatch):
    user_a = AuthenticatedUser(uid="user_a_123", token="token_a")

    mock_doc = {
        "fields": {
            "title": {"stringValue": "My Resume"},
            "snapshot": {
                "mapValue": {
                    "fields": {
                        "profile": {
                            "mapValue": {
                                "fields": {
                                    "headline": {"stringValue": "Lead Architect"},
                                    "summary": {"stringValue": "Experienced Software Engineer"},
                                }
                            }
                        },
                        "skills": {
                            "arrayValue": {
                                "values": [
                                    {
                                        "mapValue": {
                                            "fields": {
                                                "name": {"stringValue": "FastAPI"},
                                                "category": {"stringValue": "Backend"},
                                                "proficiency": {"stringValue": "Expert"},
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                    }
                }
            },
        }
    }

    class MockResponse:
        status_code = 200
        def json(self):
            return mock_doc

    mock_client = AsyncMock()
    mock_client.get.return_value = MockResponse()
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: mock_client)

    evidence = await get_candidate_resume_data(user=user_a, resume_id="resume_999")
    assert evidence.headline == "Lead Architect"
    assert evidence.summary == "Experienced Software Engineer"
    assert len(evidence.skills) == 1
    assert evidence.skills[0].name == "FastAPI"


@pytest.mark.asyncio
async def test_get_candidate_resume_data_not_found_raises_404(monkeypatch):
    user_b = AuthenticatedUser(uid="user_b_456", token="token_b")

    class Mock404Response:
        status_code = 404
        def json(self):
            return {"error": "Document not found"}

    mock_client = AsyncMock()
    mock_client.get.return_value = Mock404Response()
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await get_candidate_resume_data(user=user_b, resume_id="nonexistent_or_other_user_res")
    assert exc_info.value.status_code == 404
    assert "not found or is inaccessible" in exc_info.value.detail


@pytest.mark.asyncio
async def test_load_master_profile_concurrent_execution(monkeypatch):
    user = AuthenticatedUser(uid="user_c_789", token="token_c")

    profile_json = {
        "fields": {
            "headline": {"stringValue": "Cloud Architect"},
            "summary": {"stringValue": "Scalable systems builder"},
        }
    }
    experience_json = {
        "documents": [
            {
                "fields": {
                    "role": {"stringValue": "DevOps Lead"},
                    "company": {"stringValue": "Fintech Inc"},
                    "bullets": {
                        "arrayValue": {
                            "values": [{"stringValue": "Managed multi-region Kubernetes clusters."}]
                        }
                    },
                }
            }
        ]
    }
    empty_subcollection = {"documents": []}

    async def mock_get(url, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "profile/main" in url:
            mock_resp.json.return_value = profile_json
        elif "experience" in url:
            mock_resp.json.return_value = experience_json
        else:
            mock_resp.json.return_value = empty_subcollection
        return mock_resp

    mock_client = AsyncMock()
    mock_client.get.side_effect = mock_get
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: mock_client)

    evidence = await load_master_profile(user)

    assert evidence.headline == "Cloud Architect"
    assert evidence.summary == "Scalable systems builder"
    assert len(evidence.experience) == 1
    assert evidence.experience[0].role == "DevOps Lead"
    assert evidence.experience[0].bullets == ["Managed multi-region Kubernetes clusters."]
    # Confirm 7 requests were dispatched (profile + 6 subcollections: experience, projects, skills, education, certifications, achievements)
    assert mock_client.get.call_count == 7
