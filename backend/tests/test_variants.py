import pytest
import json
from unittest.mock import MagicMock, AsyncMock
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
