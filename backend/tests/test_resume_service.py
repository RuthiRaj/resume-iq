import pytest
from fastapi import HTTPException
from app.core.auth import AuthenticatedUser
from app.services.resume_service import (
    _decode_firestore_value,
    _decode_firestore_doc,
    _encode_firestore_value,
    _encode_firestore_fields,
    get_candidate_resume_data,
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

    import requests
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: MockResponse())

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

    import requests
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: Mock404Response())

    with pytest.raises(HTTPException) as exc_info:
        await get_candidate_resume_data(user=user_b, resume_id="nonexistent_or_other_user_res")
    assert exc_info.value.status_code == 404
    assert "not found or is inaccessible" in exc_info.value.detail
