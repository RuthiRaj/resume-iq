import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from pydantic import ValidationError
from app.schemas.variant import (
    CreateTargetedVariantRequest,
    ApplyVariantChangeRequest,
    RevertChangeRequest,
)
from app.schemas.candidate import CandidateEvidence, ExperienceItem, ProjectItem, SkillItem
from app.schemas.requirement_match import RequirementMatch
from app.services.variant_service import VariantService
from app.services.resume_service import ResumeService
from app.core.auth import AuthenticatedUser
from app.ai.remediation_engine import generate_source_evidence_id
from fastapi import HTTPException


@pytest.fixture
def mock_master_resume():
    return {
        "title": "Master Backend Resume",
        "targetRole": "Software Engineer",
        "targetCompany": "General",
        "score": 60,
        "atsScore": 60,
        "scoreBreakdown": {
            "relevance": 60,
            "keywords": 60,
            "metrics": 60,
            "formatting": 60,
        },
        "analysisResults": {
            "requirementMatches": [
                {
                    "requirementName": "Python",
                    "category": "Language",
                    "importance": "MustHave",
                    "matchStatus": "StrongMatch",
                    "resumeEvidence": "Engineered Python web services.",
                    "jobSourceEvidence": "3+ years Python",
                    "confidence": "High",
                },
                {
                    "requirementName": "Kubernetes",
                    "category": "DevOps",
                    "importance": "MustHave",
                    "matchStatus": "Missing",
                    "resumeEvidence": "",
                    "jobSourceEvidence": "Experience with Kubernetes cluster management",
                    "confidence": "High",
                },
            ]
        },
        "snapshot": {
            "profile": {"headline": "Backend Engineer"},
            "summary": "Experienced Python developer.",
            "experience": [
                {
                    "role": "Backend Engineer",
                    "company": "Tech Corp",
                    "startDate": "2022",
                    "endDate": "Present",
                    "bullets": ["Engineered Python web services.", "Maintained PostgreSQL schemas."],
                    "technologies": ["Python", "PostgreSQL"],
                }
            ],
            "projects": [],
            "skills": [{"name": "Python", "category": "Technical", "proficiency": "Expert"}],
            "education": [],
            "certifications": [],
        },
    }


@pytest.mark.asyncio
async def test_create_targeted_variant_forks_snapshot_and_isolates_master(monkeypatch, mock_master_resume):
    saved_docs = {}

    async def mock_get(user, resume_id):
        if resume_id == "master_123":
            return mock_master_resume
        return saved_docs.get(resume_id)

    async def mock_save(user, resume_id, data):
        saved_docs[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")
    req = CreateTargetedVariantRequest(
        master_resume_id="master_123",
        target_role="Senior Full Stack Engineer",
        target_company="Stripe",
        job_description="We need 3+ years Python, Kubernetes, and PostgreSQL.",
    )

    variant = await VariantService.create_targeted_variant(user, req)

    assert variant.variant_id.startswith("var_")
    assert variant.master_resume_id == "master_123"
    assert variant.version == 1
    assert variant.baseline_score == 60
    assert variant.current_score == 60
    assert variant.score_delta == 0
    assert len(variant.snapshot.experience[0].bullets) == 2
    assert len(variant.change_ledger) == 0
    # Master resume title and object untouched
    assert mock_master_resume["title"] == "Master Backend Resume"


@pytest.mark.asyncio
async def test_create_targeted_variant_prevents_variant_of_variant_nesting(monkeypatch, mock_master_resume):
    # If source is already a targeted variant pointing to root master_123
    mock_targeted_doc = {
        **mock_master_resume,
        "isTargetedVariant": True,
        "masterResumeId": "master_123",
    }

    saved_docs = {}
    async def mock_get(user, resume_id):
        return mock_targeted_doc

    async def mock_save(user, resume_id, data):
        saved_docs[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    req = CreateTargetedVariantRequest(
        master_resume_id="var_intermediate_456",
        target_role="Lead Architect",
        job_description="Architect role description.",
    )

    variant = await VariantService.create_targeted_variant(user, req)
    # Proves root master ID was preserved instead of nesting
    assert variant.master_resume_id == "master_123"


@pytest.mark.asyncio
async def test_apply_change_increments_version_and_records_ledger(monkeypatch, mock_master_resume):
    doc_store = {}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    # 1. Fork variant
    doc_store["master_123"] = mock_master_resume
    create_req = CreateTargetedVariantRequest(
        master_resume_id="master_123",
        target_role="Senior Engineer",
        job_description="Python JD",
    )
    variant = await VariantService.create_targeted_variant(user, create_req)
    var_id = variant.variant_id
    assert variant.version == 1

    # 2. Apply change
    apply_req = ApplyVariantChangeRequest(
        requirement_name="PostgreSQL",
        section="Experience",
        target_item_id="exp_0",
        target_bullet_index=1,
        approved_bullet="Architected and indexed high-throughput PostgreSQL schemas cutting latency by 40%.",
    )

    updated_var, record = await VariantService.apply_change_to_variant(user, var_id, apply_req)

    assert updated_var.version == 2
    assert len(updated_var.change_ledger) == 1
    assert record.id.startswith("chg_")
    assert record.original_text == "Maintained PostgreSQL schemas."
    assert record.approved_text == "Architected and indexed high-throughput PostgreSQL schemas cutting latency by 40%."
    assert record.version_introduced == 2
    assert updated_var.snapshot.experience[0].bullets[1] == "Architected and indexed high-throughput PostgreSQL schemas cutting latency by 40%."


@pytest.mark.asyncio
async def test_revert_change_restores_original_text_and_increments_version(monkeypatch, mock_master_resume):
    doc_store = {}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    doc_store["master_123"] = mock_master_resume

    # 1. Create (v1)
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Senior Engineer",
            job_description="JD",
        ),
    )
    var_id = variant.variant_id

    # 2. Apply change (v2)
    _, change = await VariantService.apply_change_to_variant(
        user,
        var_id,
        ApplyVariantChangeRequest(
            requirement_name="Python",
            section="Experience",
            target_item_id="exp_0",
            target_bullet_index=0,
            approved_bullet="Engineered mission-critical Python APIs.",
        ),
    )

    # 3. Revert change (v3)
    revert_res = await VariantService.revert_change_on_variant(user, var_id, change.id)

    assert revert_res.success is True
    assert revert_res.new_version == 3

    reloaded = await VariantService.get_targeted_variant(user, var_id)
    assert reloaded.version == 3
    # Bullet text restored to original
    assert reloaded.snapshot.experience[0].bullets[0] == "Engineered Python web services."
    # Change ledger has both original change and revert record
    assert len(reloaded.change_ledger) == 2
    assert reloaded.change_ledger[0].status == "Reverted"
    assert reloaded.change_ledger[1].action_type == "RevertChange"


@pytest.mark.asyncio
async def test_fit_comparison_computes_exact_requirement_progressions(monkeypatch, mock_master_resume):
    doc_store = {}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    doc_store["master_123"] = mock_master_resume

    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Senior Engineer",
            job_description="JD",
        ),
    )
    var_id = variant.variant_id

    # Simulate updated analysis on variant
    doc_store[var_id]["currentScore"] = 75
    doc_store[var_id]["currentBreakdown"] = {"relevance": 75, "keywords": 75, "metrics": 75, "formatting": 75}
    doc_store[var_id]["currentMatches"] = [
        {
            "requirementName": "Python",
            "category": "Language",
            "importance": "MustHave",
            "matchStatus": "StrongMatch",
            "confidence": "High",
        },
        {
            "requirementName": "Kubernetes",
            "category": "DevOps",
            "importance": "MustHave",
            "matchStatus": "StrongMatch",
            "resumeEvidence": "Deployed EKS cluster.",
            "confidence": "High",
        },
    ]

    fit = await VariantService.get_fit_comparison(user, var_id)

    assert fit.baseline_score == 60
    assert fit.current_score == 75
    assert fit.score_delta == 15
    assert fit.total_gaps_resolved == 1  # Kubernetes went from Missing -> StrongMatch
    assert fit.total_gaps_remaining == 0


@pytest.mark.asyncio
async def test_export_targeted_variant_is_read_only(monkeypatch, mock_master_resume):
    doc_store = {}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    doc_store["master_123"] = mock_master_resume

    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Senior Engineer",
            target_company="Stripe",
            job_description="JD",
        ),
    )
    var_id = variant.variant_id

    export_res = await VariantService.export_targeted_variant_snapshot(user, var_id, fmt="markdown")

    assert "Senior Engineer" in export_res.content
    assert "Engineered Python web services." in export_res.content
    assert export_res.version == 1

    # Confirm zero mutations on variant
    reloaded = await VariantService.get_targeted_variant(user, var_id)
    assert reloaded.version == 1
    assert len(reloaded.change_ledger) == 0


@pytest.mark.asyncio
async def test_multi_experience_resolution_isolation(monkeypatch, mock_master_resume):
    """
    Verifies that mutations targeted at exp_1 resolve to the second job entry,
    modifying only that job and strictly preserving exp_0.
    """
    multi_exp_resume = json.loads(json.dumps(mock_master_resume))
    multi_exp_resume["snapshot"]["experience"] = [
        {
            "role": "Staff Backend Engineer",
            "company": "Alpha Corp",
            "bullets": ["Alpha bullet 1.", "Alpha bullet 2."],
        },
        {
            "role": "Junior Developer",
            "company": "Beta LLC",
            "bullets": ["Beta bullet 1.", "Beta bullet 2."],
        },
    ]

    doc_store = {"master_multi": multi_exp_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_multi",
            target_role="Full Stack",
            job_description="Need React and Node.",
        ),
    )
    var_id = variant.variant_id

    # 1. Apply change targeted specifically to exp_1, bullet 1
    apply_req = ApplyVariantChangeRequest(
        requirement_name="Node.js",
        section="Experience",
        target_item_id="exp_1",
        target_bullet_index=1,
        approved_bullet="Architected high-throughput Node.js microservices.",
    )
    updated_var, change_rec = await VariantService.apply_change_to_variant(user, var_id, apply_req)

    # Verify exp_0 is completely untouched
    assert updated_var.snapshot.experience[0].bullets == ["Alpha bullet 1.", "Alpha bullet 2."]
    # Verify exp_1 bullet 1 was updated
    assert updated_var.snapshot.experience[1].bullets[1] == "Architected high-throughput Node.js microservices."
    assert change_rec.target_item_id == "exp_1"
    assert change_rec.original_text == "Beta bullet 2."

    # 2. Revert the change on exp_1
    revert_res = await VariantService.revert_change_on_variant(user, var_id, change_rec.id)
    assert revert_res.success is True

    reloaded = await VariantService.get_targeted_variant(user, var_id)
    # Verify exp_0 is still completely untouched
    assert reloaded.snapshot.experience[0].bullets == ["Alpha bullet 1.", "Alpha bullet 2."]
    # Verify exp_1 bullet 1 is restored to its original text
    assert reloaded.snapshot.experience[1].bullets[1] == "Beta bullet 2."


@pytest.mark.asyncio
async def test_multi_project_resolution_isolation(monkeypatch, mock_master_resume):
    """
    Verifies that mutations targeted at proj_1 resolve to the second project entry,
    modifying only that project and preserving proj_0.
    """
    multi_proj_resume = json.loads(json.dumps(mock_master_resume))
    multi_proj_resume["snapshot"]["projects"] = [
        {"title": "Project Alpha", "highlights": ["Alpha hl 1."]},
        {"title": "Project Beta", "highlights": ["Beta hl 1.", "Beta hl 2."]},
    ]

    doc_store = {"master_proj": multi_proj_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_proj",
            target_role="Full Stack",
            job_description="Need React.",
        ),
    )
    var_id = variant.variant_id

    # Apply change to proj_1
    apply_req = ApplyVariantChangeRequest(
        requirement_name="React",
        section="Project",
        target_item_id="proj_1",
        target_bullet_index=0,
        approved_bullet="Built scalable React dashboard.",
    )
    updated_var, change_rec = await VariantService.apply_change_to_variant(user, var_id, apply_req)

    # Verify proj_0 is untouched
    assert updated_var.snapshot.projects[0].highlights == ["Alpha hl 1."]
    # Verify proj_1 was updated
    assert updated_var.snapshot.projects[1].highlights[0] == "Built scalable React dashboard."
    assert change_rec.target_item_id == "proj_1"

    # Revert change on proj_1
    await VariantService.revert_change_on_variant(user, var_id, change_rec.id)
    reloaded = await VariantService.get_targeted_variant(user, var_id)
    assert reloaded.snapshot.projects[0].highlights == ["Alpha hl 1."]
    assert reloaded.snapshot.projects[1].highlights[0] == "Beta hl 1."


def test_negative_bullet_index_rejected_by_schema():
    """Confirms negative bullet indices are rejected by schema validation."""
    with pytest.raises(ValidationError):
        ApplyVariantChangeRequest(
            requirement_name="Python",
            section="Experience",
            target_item_id="exp_0",
            target_bullet_index=-1,
            approved_bullet="Should fail validation",
        )


@pytest.mark.asyncio
async def test_out_of_bounds_bullet_index_raises_http_400(monkeypatch, mock_master_resume):
    """Confirms out of bounds bullet indices raise HTTP 400 Bad Request."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="Job Description text.",
        ),
    )

    # Item has 2 bullets (indices 0, 1). Index 50 is out of bounds
    with pytest.raises(HTTPException) as exc_info:
        await VariantService.apply_change_to_variant(
            user,
            variant.variant_id,
            ApplyVariantChangeRequest(
                requirement_name="Python",
                section="Experience",
                target_item_id="exp_0",
                target_bullet_index=50,
                approved_bullet="Out of bounds bullet.",
            ),
        )
    assert exc_info.value.status_code == 400
    assert "out of bounds" in exc_info.value.detail


@pytest.mark.asyncio
async def test_out_of_bounds_target_item_id_raises_http_404(monkeypatch, mock_master_resume):
    """Confirms non-existent target items raise HTTP 404 Not Found."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="Job Description text.",
        ),
    )

    # Candidate has 1 experience item. exp_99 does not exist
    with pytest.raises(HTTPException) as exc_info:
        await VariantService.apply_change_to_variant(
            user,
            variant.variant_id,
            ApplyVariantChangeRequest(
                requirement_name="Python",
                section="Experience",
                target_item_id="exp_99",
                target_bullet_index=0,
                approved_bullet="Non-existent item bullet.",
            ),
        )
    assert exc_info.value.status_code == 404
    assert "out of bounds" in exc_info.value.detail


@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict_raises_http_409(monkeypatch, mock_master_resume):
    """Confirms version mismatch raises HTTP 409 Conflict."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="Job Description text.",
        ),
    )

    # Variant is at version 1; pass expected_version=5
    with pytest.raises(HTTPException) as exc_info:
        await VariantService.apply_change_to_variant(
            user,
            variant.variant_id,
            ApplyVariantChangeRequest(
                requirement_name="Python",
                section="Experience",
                target_item_id="exp_0",
                target_bullet_index=0,
                approved_bullet="Concurrent update.",
                expected_version=5,
            ),
        )
    assert exc_info.value.status_code == 409
    assert "Concurrency conflict" in exc_info.value.detail


@pytest.mark.asyncio
async def test_whitespace_normalized_job_description_hash(monkeypatch, mock_master_resume):
    """Confirms that varying line endings (CRLF vs LF) and line trailing whitespace produce identical hashes."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")

    # Unix format
    v_unix = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="Line 1\nLine 2\nLine 3",
        ),
    )

    # Windows format with trailing whitespace
    v_win = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="Line 1   \r\nLine 2  \r\nLine 3",
        ),
    )

    assert v_unix.job_description_hash == v_win.job_description_hash


@pytest.mark.asyncio
async def test_invalid_variant_id_format_rejected():
    """Confirms path traversal or invalid characters in variant_id raise HTTP 400."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    with pytest.raises(HTTPException) as exc_info:
        await VariantService.get_targeted_variant(user, "var_123/../../etc/passwd")
    assert exc_info.value.status_code == 400
    assert "Invalid variant_id" in exc_info.value.detail


@pytest.mark.asyncio
async def test_unsupported_export_format_rejected(monkeypatch, mock_master_resume):
    """Confirms unsupported export format raises HTTP 400."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="JD text",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await VariantService.export_targeted_variant_snapshot(user, variant.variant_id, fmt="yaml")
    assert exc_info.value.status_code == 400
    assert "Unsupported export format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_unsupported_variant_section_raises_http_400(monkeypatch, mock_master_resume):
    """Confirms modifying an unsupported section (e.g. Education) raises HTTP 400."""
    doc_store = {"master_123": mock_master_resume}

    async def mock_get(user, resume_id):
        return doc_store.get(resume_id)

    async def mock_save(user, resume_id, data):
        doc_store[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    user = AuthenticatedUser(uid="usr_1", token="tok_1")
    variant = await VariantService.create_targeted_variant(
        user,
        CreateTargetedVariantRequest(
            master_resume_id="master_123",
            target_role="Engineer",
            job_description="JD text",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await VariantService.apply_change_to_variant(
            user,
            variant.variant_id,
            ApplyVariantChangeRequest(
                requirement_name="B.S. Computer Science",
                section="Education",
                target_item_id="edu_0",
                target_bullet_index=0,
                approved_bullet="Should be rejected",
            ),
        )
    assert exc_info.value.status_code == 400
    assert "Unsupported variant section" in exc_info.value.detail
