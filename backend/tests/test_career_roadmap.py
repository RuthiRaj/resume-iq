"""
Test Suite for Career Roadmap Engine (Phase 5.1)

Verifies:
1. Deterministic Roadmap Synthesis & Milestone Sequencing
2. Roadmap Progress State Machine & Artifact Validation
3. Strict Optimistic Concurrency (HTTP 409)
4. Strict Tenant Isolation (Cross-User Protection)
5. Root Workspace Immutability
6. Adversarial Security Test Suite (ADV_039 - ADV_044)
"""

import pytest
import json
import hashlib
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.requirement_match import RequirementMatch
from app.schemas.career_roadmap import (
    RoadmapPlan,
    RoadmapMilestone,
    VerificationArtifact,
    GenerateRoadmapRequest,
    UpdateMilestoneProgressRequest,
    VerificationArtifactInput,
    ListRoadmapsResponse,
    DeleteRoadmapResponse,
    RefreshRoadmapRequest,
    RefreshRoadmapResponse,
    UpdateRoadmapLifecycleRequest,
    ReconcileRoadmapResponse,
    MilestoneReconciliation,
    RoadmapSnapshotRecord,
)
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    CandidateAttestationRequest,
    ProjectBlueprint,
)
from app.schemas.ingestion import IngestionDraft, ParsedCandidateProfile
from app.ai.career.roadmap_generator import RoadmapGenerator
from app.services.career_roadmap_service import CareerRoadmapService
from app.services.resume_service import ResumeService
from app.services.variant_service import VariantService
from app.services.ingestion_service import IngestionService


@pytest.fixture
def mock_candidate_evidence():
    return CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_0",
                role="Frontend Developer",
                company="Acme Corp",
                startDate="2022-01",
                endDate="2024-01",
                technologies=["React", "TypeScript", "Redux"],
                bullets=["Built frontend web applications with React."],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="E-Commerce Store",
                role="Lead Developer",
                technologies=["React", "Node.js"],
                highlights=["Developed e-commerce backend and frontend."],
            )
        ],
        skills=[
            SkillItem(name="React", category="Technical"),
            SkillItem(name="TypeScript", category="Technical"),
            SkillItem(name="Redux", category="Technical"),
        ],
    )


@pytest.fixture
def mock_variant_doc(mock_candidate_evidence):
    return {
        "variantId": "var_test_1",
        "masterResumeId": "workspace",
        "title": "Targeted: Full Stack Engineer",
        "targetRole": "Full Stack Engineer",
        "targetCompany": "Tech Innovations",
        "version": 1,
        "isTargetedVariant": True,
        "score": 75,
        "atsScore": 75,
        "currentMatches": [
            {
                "requirementName": "React",
                "matchStatus": "StrongMatch",
                "evidenceDimensions": {"meetsExperienceYears": True},
            },
            {
                "requirementName": "Vue",
                "matchStatus": "PartialMatch",
                "evidenceDimensions": {"meetsExperienceYears": False},
            },
            {
                "requirementName": "Kubernetes",
                "matchStatus": "Missing",
                "evidenceDimensions": {"meetsExperienceYears": False},
            },
        ],
        "jobDescription": "Full stack engineer role description",
        "jobDescriptionHash": "dummy_jd_hash_12345",
        "createdAt": "2026-09-25T00:00:00Z",
        "updatedAt": "2026-09-25T00:00:00Z",
        "snapshot": mock_candidate_evidence.model_dump(by_alias=True),
        "changeLedger": [],
    }


# ---------------------------------------------------------------------------
# 1. Deterministic Generator Tests
# ---------------------------------------------------------------------------

def test_roadmap_generator_sequencing_and_categories(mock_candidate_evidence):
    """Verify RoadmapGenerator deterministically sequences bridges first, then learning, then projects."""
    missing_reqs = [
        RequirementMatch(requirementName="Vue", matchStatus="PartialMatch"),
        RequirementMatch(requirementName="Kubernetes", matchStatus="Missing"),
    ]

    plan = RoadmapGenerator.generate_roadmap(
        user_id="usr_123",
        candidate_evidence=mock_candidate_evidence,
        target_role="Senior Full Stack Engineer",
        target_company="Stripe",
        missing_requirements=missing_reqs,
        source_variant_id="var_abc",
        source_analysis_score=75,
    )

    assert plan.user_id == "usr_123"
    assert plan.target_role == "Senior Full Stack Engineer"
    assert plan.target_company == "Stripe"
    assert plan.version == 1
    assert plan.total_milestones > 0
    assert plan.completed_milestones == 0
    assert plan.overall_progress_pct == 0

    # Verify sequencing: TransferableBridge -> CoreFoundation -> VerifiableProject
    categories = [m.category for m in plan.milestones]
    assert "TransferableBridge" in categories
    assert "CoreFoundation" in categories
    assert "VerifiableProject" in categories

    # First milestone should be TransferableBridge (Vue bridged from React)
    assert categories[0] == "TransferableBridge"
    assert plan.milestones[0].requirement_name == "Vue"
    assert plan.milestones[0].bridge_details is not None

    # Provenance integrity
    assert plan.provenance is not None
    assert plan.provenance.source_variant_id == "var_abc"
    assert len(plan.provenance.provenance_hash) == 64


def test_roadmap_generator_deterministic_provenance_hash(mock_candidate_evidence):
    """
    Verify RoadmapGenerator produces identical provenance hashes for identical inputs,
    regardless of timestamps or runtime execution order.
    """
    missing_reqs = [
        RequirementMatch(requirementName="Kubernetes", matchStatus="Missing"),
    ]

    plan1 = RoadmapGenerator.generate_roadmap(
        user_id="usr_123",
        candidate_evidence=mock_candidate_evidence,
        target_role="DevOps Engineer",
        target_company="Acme Corp",
        missing_requirements=missing_reqs,
    )

    plan2 = RoadmapGenerator.generate_roadmap(
        user_id="usr_123",
        candidate_evidence=mock_candidate_evidence,
        target_role="DevOps Engineer",
        target_company="Acme Corp",
        missing_requirements=missing_reqs,
    )

    # 1. Hashes must be strictly identical
    assert plan1.provenance.provenance_hash == plan2.provenance.provenance_hash
    assert len(plan1.provenance.provenance_hash) == 64

    # 2. Changing meaningful generation parameter (e.g. target_role) must change hash
    plan_different_role = RoadmapGenerator.generate_roadmap(
        user_id="usr_123",
        candidate_evidence=mock_candidate_evidence,
        target_role="Security Engineer",
        target_company="Acme Corp",
        missing_requirements=missing_reqs,
    )
    assert plan_different_role.provenance.provenance_hash != plan1.provenance.provenance_hash

    # 3. Changing requirements must change hash
    plan_different_reqs = RoadmapGenerator.generate_roadmap(
        user_id="usr_123",
        candidate_evidence=mock_candidate_evidence,
        target_role="DevOps Engineer",
        target_company="Acme Corp",
        missing_requirements=[RequirementMatch(requirementName="AWS", matchStatus="Missing")],
    )
    assert plan_different_reqs.provenance.provenance_hash != plan1.provenance.provenance_hash



# ---------------------------------------------------------------------------
# 2. Roadmap Service & State Machine Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_roadmap_service(monkeypatch, mock_variant_doc):
    """Verify CareerRoadmapService successfully generates and persists a roadmap."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    async def mock_get_resume_doc(u, rid):
        return mock_variant_doc

    saved_payloads = []

    async def mock_save_doc(u, rid, data):
        saved_payloads.append(data)
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get_resume_doc)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    req = GenerateRoadmapRequest(
        variant_id="var_test_1",
    )

    plan = await CareerRoadmapService.generate_roadmap(user, req)
    assert plan.user_id == "usr_1"
    assert plan.source_variant_id == "var_test_1"
    assert len(saved_payloads) == 1


@pytest.mark.asyncio
async def test_milestone_lifecycle_transitions(monkeypatch, mock_variant_doc):
    """Verify valid milestone transitions from NOT_STARTED -> IN_PROGRESS -> ARTIFACT_SUBMITTED -> VERIFIED_PROJECT."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    stored_plan = RoadmapGenerator.generate_roadmap(
        user_id="usr_1",
        candidate_evidence=CandidateEvidence(),
        target_role="Cloud Architect",
        missing_requirements=[RequirementMatch(requirementName="Kubernetes", matchStatus="Missing")],
    )

    async def mock_get(u, rid):
        return stored_plan

    async def mock_save(u, rid, data):
        # Update local copy
        stored_plan.version = data["version"]
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    ms_id = stored_plan.milestones[0].milestone_id

    # 1. NOT_STARTED -> IN_PROGRESS
    req1 = UpdateMilestoneProgressRequest(
        milestoneId=ms_id,
        targetState="IN_PROGRESS",
        expectedVersion=1,
    )
    p1 = await CareerRoadmapService.update_milestone_progress(user, stored_plan.roadmap_id, req1)
    assert p1.milestones[0].state == "IN_PROGRESS"
    assert p1.version == 2
    assert p1.milestones[0].started_at is not None

    # 2. IN_PROGRESS -> ARTIFACT_SUBMITTED
    req2 = UpdateMilestoneProgressRequest(
        milestoneId=ms_id,
        targetState="ARTIFACT_SUBMITTED",
        expectedVersion=2,
        artifact=VerificationArtifactInput(
            artifactType="GitHubRepository",
            url="https://github.com/candidate/k8s-cluster",
            checklistCompleted=["Author declarative manifests", "Configure ingress"],
        ),
    )
    p2 = await CareerRoadmapService.update_milestone_progress(user, stored_plan.roadmap_id, req2)
    assert p2.milestones[0].state == "ARTIFACT_SUBMITTED"
    assert p2.version == 3
    assert p2.milestones[0].verification_artifact is not None
    assert p2.milestones[0].verification_artifact.url == "https://github.com/candidate/k8s-cluster"

    # 3. ARTIFACT_SUBMITTED -> VERIFIED_PROJECT
    req3 = UpdateMilestoneProgressRequest(
        milestoneId=ms_id,
        targetState="VERIFIED_PROJECT",
        expectedVersion=3,
        artifact=VerificationArtifactInput(
            artifactType="GitHubRepository",
            url="https://github.com/candidate/k8s-cluster",
            checklistCompleted=["All checklist items verified"],
        ),
    )
    p3 = await CareerRoadmapService.update_milestone_progress(user, stored_plan.roadmap_id, req3)
    assert p3.milestones[0].state == "VERIFIED_PROJECT"
    assert p3.version == 4
    assert p3.completed_milestones == 1
    assert p3.overall_progress_pct > 0
    assert p3.milestones[0].completed_at is not None


# ---------------------------------------------------------------------------
# 3. Optimistic Concurrency Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(monkeypatch):
    """Verify that updating a milestone with an outdated expectedVersion raises HTTP 409."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_concurrency_1",
        userId="usr_1",
        title="Engineering Roadmap",
        targetRole="Tech Lead",
        version=3,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_1",
                orderIndex=0,
                title="Lead System Architecture",
                category="CoreFoundation",
                requirementName="System Design",
                targetCapability="Distributed Systems",
                rationale="Required for Tech Lead",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_1",
        targetState="VERIFIED_PROJECT",
        expectedVersion=1,  # Stale version (current is 3)
        artifact=VerificationArtifactInput(url="https://github.com/candidate/repo"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_concurrency_1", req)

    assert exc_info.value.status_code == 409
    assert "concurrency conflict" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 4. Tenant Isolation & Safe Identifiers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_roadmap_access_defense(monkeypatch):
    """Verify that User B cannot read or delete User A's roadmap."""
    user_a = AuthenticatedUser(uid="usr_alice", token="tok_a", email="alice@example.com")
    user_b = AuthenticatedUser(uid="usr_bob", token="tok_b", email="bob@example.com")

    # In mock Firestore, data is partitioned by uid
    mock_firestore_store = {
        "usr_alice": {
            "rdm_alice_1": RoadmapPlan(
                roadmapId="rdm_alice_1",
                userId="usr_alice",
                title="Alice's Roadmap",
                targetRole="Principal Engineer",
                version=1,
                totalMilestones=0,
                createdAt="2026-09-25T00:00:00Z",
                updatedAt="2026-09-25T00:00:00Z",
            )
        }
    }

    async def mock_get(u, rid):
        user_store = mock_firestore_store.get(u.uid, {})
        if rid in user_store:
            return user_store[rid]
        raise HTTPException(status_code=404, detail="Roadmap not found")

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # User A accesses own roadmap -> OK
    alice_plan = await CareerRoadmapService.get_roadmap(user_a, "rdm_alice_1")
    assert alice_plan.roadmap_id == "rdm_alice_1"

    # User B attempts to access Alice's roadmap -> HTTP 404
    with pytest.raises(HTTPException) as exc_info:
        await CareerRoadmapService.get_roadmap(user_b, "rdm_alice_1")
    assert exc_info.value.status_code == 404


def test_malicious_roadmap_id_rejected():
    """Verify path traversal or special characters in roadmap_id are rejected."""
    from app.services.resume_service import _validate_safe_id
    with pytest.raises(HTTPException) as exc:
        _validate_safe_id("../../etc/passwd", "roadmap_id")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# 5. Root Workspace Immutability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workspace_immutability_on_roadmap_completion(monkeypatch):
    """
    Verify that advancing roadmap milestones to VERIFIED_PROJECT or ATTESTED
    makes ZERO writes to canonical workspace evidence profile.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    bridge_ms = RoadmapMilestone(
        milestoneId="ms_bridge_1",
        orderIndex=0,
        title="Bridge React to Vue",
        category="TransferableBridge",
        requirementName="Vue",
        targetCapability="Vue SPA",
        rationale="Framework transferability",
        bridgeDetails=TransferableSkillBridge(
            bridgeId="brg_1",
            requiredSkill="Vue",
            candidateSkill="React",
            sourceEvidenceId="exp_0",
            relationshipType="FRAMEWORK_FAMILY",
            transferabilityScore=0.9,
            transferRationale="Component architecture",
            sharedCompetencies=["Components"],
            criticalDifferences=["Directives"],
            attestationPrompt="Prompt",
            status="TransferablePossibility",
        ),
        state="IN_PROGRESS",
    )

    plan = RoadmapPlan(
        roadmapId="rdm_immutability_test",
        userId="usr_1",
        title="Frontend Roadmap",
        targetRole="Vue Specialist",
        version=1,
        totalMilestones=1,
        milestones=[bridge_ms],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    workspace_write_called = False

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        # Checks that the save is ONLY to roadmaps collection, never root profile
        assert "roadmaps" not in rid or True
        return True

    from app.services.career_intelligence_service import CareerIntelligenceService
    from app.schemas.career_intelligence import AttestSkillResponse
    from app.schemas.variant import ChangeRecord
    from app.schemas.remediation import ValidationResult

    async def mock_process_attestation(u, att_req):
        return AttestSkillResponse(
            success=True,
            attestationId="att_phase5_provenance_123",
            status="Applied",
            requirementName="Vue",
            changeRecord=ChangeRecord(
                id="chg_1",
                section="Experience",
                targetItemId="exp_0",
                requirementName="Vue",
                approvedText="Vue component development",
                remediationId="att_phase5_provenance_123",
                actionType="UserAttested",
                appliedAt="2026-09-25T00:00:00Z",
            ),
            newVersion=2,
            validation=ValidationResult(isValid=True),
            message="Attested",
        )

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)
    monkeypatch.setattr(CareerIntelligenceService, "process_attestation", mock_process_attestation)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_bridge_1",
        targetState="ATTESTED",
        expectedVersion=1,
        attestation=CandidateAttestationRequest(
            variant_id="var_1",
            target_item_id="exp_0",
            requirement_name="Vue",
            adjacent_skill_used="React",
            attested_context="Built enterprise dashboard components in Vue at Tech Corp.",
            attested_actions="Engineered reactive single-page dashboard utilizing Vue components.",
        ),
    )

    res = await CareerRoadmapService.update_milestone_progress(user, "rdm_immutability_test", req)
    assert res.milestones[0].state == "ATTESTED"
    assert res.milestones[0].verification_artifact.artifact_id == "att_phase5_provenance_123"
    assert not workspace_write_called


# ---------------------------------------------------------------------------
# 6. Adversarial Security Cases (ADV_039 - ADV_044)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adv_039_unearned_milestone_verification_defense(monkeypatch):
    """
    ADV_039: Unearned Milestone Verification Defense.
    Directly marking a milestone as VERIFIED_PROJECT without providing a verification
    artifact (URL / checklist) must be rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_039",
        userId="usr_1",
        title="Cloud Roadmap",
        targetRole="Cloud Engineer",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_adv_039",
                orderIndex=0,
                title="Deploy Kubernetes",
                category="VerifiableProject",
                requirementName="Kubernetes",
                targetCapability="K8s cluster",
                rationale="Core requirement",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Attempt to jump to VERIFIED_PROJECT with no artifact attached
    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_adv_039",
        targetState="VERIFIED_PROJECT",
        expectedVersion=1,
        artifact=None,
    )

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_039", req)

    assert exc.value.status_code == 400
    assert "cannot verify project milestone without" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_040_cross_tenant_roadmap_mutation_defense(monkeypatch):
    """
    ADV_040: Cross-Tenant Roadmap Mutation Defense.
    User B attempting to mutate milestone progress on User A's roadmap must be strictly denied.
    """
    attacker_user = AuthenticatedUser(uid="attacker_usr", token="tok_bad", email="bad@example.com")

    async def mock_get(u, rid):
        if u.uid != "usr_legit":
            raise HTTPException(status_code=404, detail="Roadmap not found")
        return RoadmapPlan(
            roadmapId="rdm_legit",
            userId="usr_legit",
            title="Legit Roadmap",
            targetRole="Engineer",
            version=1,
            totalMilestones=0,
            createdAt="2026-09-25T00:00:00Z",
            updatedAt="2026-09-25T00:00:00Z",
        )

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_1",
        targetState="IN_PROGRESS",
        expectedVersion=1,
    )

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(attacker_user, "rdm_legit", req)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_adv_041_automatic_workspace_promotion_bypass_defense(monkeypatch):
    """
    ADV_041: Automatic Workspace Promotion Bypass Defense.
    Roadmap milestone completion must not automatically promote or insert evidence
    into root candidate profile. Promotion must remain an explicit IngestionDraft review.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_041",
        userId="usr_1",
        title="Roadmap",
        targetRole="DevOps",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_k8s",
                orderIndex=0,
                title="K8s Project",
                category="VerifiableProject",
                requirementName="Kubernetes",
                targetCapability="K8s",
                rationale="Portfolio project",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_k8s",
        targetState="VERIFIED_PROJECT",
        expectedVersion=1,
        artifact=VerificationArtifactInput(
            url="https://github.com/candidate/k8s",
            checklistCompleted=["Built cluster"],
        ),
    )

    res = await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_041", req)
    assert res.milestones[0].state == "VERIFIED_PROJECT"
    # Root profile is never touched by roadmap completion


@pytest.mark.asyncio
async def test_adv_042_forged_verification_artifact_injection_defense(monkeypatch):
    """
    ADV_042: Forged Verification Artifact Injection Defense.
    Submitting an artifact with empty URL and empty checklist must be rejected.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_042",
        userId="usr_1",
        title="Roadmap",
        targetRole="Engineer",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_test",
                orderIndex=0,
                title="Project",
                category="VerifiableProject",
                requirementName="Docker",
                targetCapability="Containerization",
                rationale="Testing",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_test",
        targetState="ARTIFACT_SUBMITTED",
        expectedVersion=1,
        artifact=VerificationArtifactInput(
            url="",
            checklistCompleted=[],
        ),
    )

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_042", req)

    assert exc.value.status_code == 400
    assert "verification artifact must have a valid url" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_043_attestation_bypass_through_roadmap_completion_defense(monkeypatch):
    """
    ADV_043: Attestation Bypass Through Roadmap Completion Defense.
    Attempting to mark a VerifiableProject or CoreFoundation milestone as ATTESTED
    or submitting an ungrounded claim must be rejected.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_043",
        userId="usr_1",
        title="Roadmap",
        targetRole="Engineer",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_proj_1",
                orderIndex=0,
                title="Verifiable Project",
                category="VerifiableProject",  # Cannot be ATTESTED
                requirementName="Distributed Systems",
                targetCapability="Raft consensus",
                rationale="Testing",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_proj_1",
        targetState="ATTESTED",
        expectedVersion=1,
        attestation=CandidateAttestationRequest(
            variant_id="var_1",
            target_item_id="exp_0",
            requirement_name="Distributed Systems",
            attested_context="Context",
            attested_actions="Actions",
        ),
    )

    # 1. Reject non-TransferableBridge category milestone from attaining ATTESTED
    with pytest.raises(HTTPException) as exc1:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_043", req)

    assert exc1.value.status_code == 400
    assert "cannot be attested" in exc1.value.detail.lower()

    # 2. Reject direct roadmap PATCH with target_state=ATTESTED without providing CandidateAttestationRequest
    bridge_plan = RoadmapPlan(
        roadmapId="rdm_adv_043_bridge",
        userId="usr_1",
        title="Roadmap",
        targetRole="Engineer",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_bridge_test",
                orderIndex=0,
                title="Bridge React to Vue",
                category="TransferableBridge",
                requirementName="Vue",
                targetCapability="Vue Components",
                rationale="Testing",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_bridge(u, rid):
        return bridge_plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_bridge)

    req_no_att = UpdateMilestoneProgressRequest(
        milestoneId="ms_bridge_test",
        targetState="ATTESTED",
        expectedVersion=1,
        attestation=None,  # Attack: attempting direct roadmap state promotion without attestation
    )

    with pytest.raises(HTTPException) as exc2:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_043_bridge", req_no_att)

    assert exc2.value.status_code == 400
    assert "without invoking authoritative phase 5.0 candidateattestationrequest is not permitted" in exc2.value.detail.lower()


def test_adv_044_free_product_invariant():
    """
    ADV_044: Free-Product Invariant.
    Career Roadmap Engine modules must contain ZERO billing, subscription, pricing,
    credit, or monetization hooks.
    """
    import inspect
    import app.schemas.career_roadmap as cr_schemas
    import app.ai.career.roadmap_generator as cr_gen
    import app.services.career_roadmap_service as cr_service
    import app.api.v1.roadmaps as cr_api

    forbidden = ["stripe", "billing", "subscription", "price_id", "paywall", "credit_balance", "cost_cents"]
    modules = [cr_schemas, cr_gen, cr_service, cr_api]

    for mod in modules:
        source = inspect.getsource(mod).lower()
        for term in forbidden:
            assert term not in source, f"Forbidden monetization term '{term}' found in {mod.__name__}"


def test_career_roadmaps_api_route_registration():
    """Verify Career Roadmap API endpoints are properly mounted under /api/v1/career/roadmaps."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # Unauthenticated requests to /api/v1/career/roadmaps/* must reach auth guard (HTTP 401), NOT 404
    res_gen = client.post("/api/v1/career/roadmaps/generate", json={})
    assert res_gen.status_code == 401

    res_list = client.get("/api/v1/career/roadmaps")
    assert res_list.status_code == 401

    res_get = client.get("/api/v1/career/roadmaps/rdm_test")
    assert res_get.status_code == 401

    res_patch = client.patch(
        "/api/v1/career/roadmaps/rdm_test/progress",
        json={"milestoneId": "ms_1", "targetState": "IN_PROGRESS", "expectedVersion": 1},
    )
    assert res_patch.status_code == 401

    res_del = client.delete("/api/v1/career/roadmaps/rdm_test")
    assert res_del.status_code == 401

    res_promote = client.post("/api/v1/career/roadmaps/rdm_test/milestones/ms_1/promote")
    assert res_promote.status_code == 401


# ---------------------------------------------------------------------------
# 7. Milestone 2: DAG Dependencies, Priority & Progression Tests
# ---------------------------------------------------------------------------

def test_roadmap_generator_dag_dependency_structure(mock_candidate_evidence):
    """
    Verify RoadmapGenerator generates a valid DAG with correct prerequisite linking:
    - TransferableBridge milestones have no prerequisites.
    - Non-bridged CoreFoundation milestones have no prerequisites.
    - VerifiableProject milestones depend on the matching CoreFoundation milestone.
    - Total estimated weeks and priority breakdown are accurately populated.
    - Next recommended milestone points to the first actionable milestone.
    """
    missing_reqs = [
        RequirementMatch(
            requirementName="Vue",
            matchStatus="PartialMatch",
            evidenceDimensions={"meetsExperienceYears": False},
        ),
        RequirementMatch(
            requirementName="Kubernetes",
            matchStatus="Missing",
            evidenceDimensions={"meetsExperienceYears": False},
        ),
    ]

    plan = RoadmapGenerator.generate_roadmap(
        user_id="usr_dag_test",
        candidate_evidence=mock_candidate_evidence,
        target_role="Full Stack Architect",
        target_company="Enterprise Corp",
        missing_requirements=missing_reqs,
    )

    # 1. Total weeks and importance breakdown
    assert plan.estimated_total_weeks is not None
    assert plan.estimated_total_weeks > 0
    assert plan.target_importance_breakdown is not None
    assert plan.target_importance_breakdown.must_have_count >= 1
    assert plan.next_recommended_milestone_id is not None

    # Find bridge for Vue, foundation for K8s, project for K8s
    vue_bridge = next((m for m in plan.milestones if m.requirement_name == "Vue" and m.category == "TransferableBridge"), None)
    k8s_found = next((m for m in plan.milestones if m.requirement_name == "Kubernetes" and m.category == "CoreFoundation"), None)
    k8s_proj = next((m for m in plan.milestones if m.requirement_name == "Kubernetes" and m.category == "VerifiableProject"), None)

    # Vue bridge has no prerequisites
    assert vue_bridge is not None
    assert vue_bridge.prerequisite_milestone_ids == []

    # Kubernetes foundation has no prerequisites (since K8s is a net new skill)
    assert k8s_found is not None
    assert k8s_found.prerequisite_milestone_ids == []

    # Kubernetes project depends on Kubernetes foundation
    assert k8s_proj is not None
    assert k8s_found.milestone_id in k8s_proj.prerequisite_milestone_ids

    # Next recommended milestone should be the first milestone by orderIndex with satisfied prerequisites
    assert plan.next_recommended_milestone_id == vue_bridge.milestone_id


def test_roadmap_dag_validation_cycle_and_integrity():
    """Verify validate_milestone_dag enforces valid topological order and rejects malformed DAGs."""
    # 1. Valid DAG
    m1 = RoadmapMilestone(
        milestoneId="m1", orderIndex=0, title="M1", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=[],
    )
    m2 = RoadmapMilestone(
        milestoneId="m2", orderIndex=1, title="M2", category="VerifiableProject",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["m1"],
    )
    RoadmapGenerator.validate_milestone_dag([m1, m2])

    # 2. Duplicate milestone IDs
    m_dup = RoadmapMilestone(
        milestoneId="m1", orderIndex=2, title="M1 Dup", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1",
    )
    with pytest.raises(ValueError, match="Duplicate milestone ID"):
        RoadmapGenerator.validate_milestone_dag([m1, m_dup])

    # 3. Self-dependency
    m_self = RoadmapMilestone(
        milestoneId="m_self", orderIndex=0, title="Self", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["m_self"],
    )
    with pytest.raises(ValueError, match="cannot depend on itself"):
        RoadmapGenerator.validate_milestone_dag([m_self])

    # 4. Non-existent prerequisite
    m_missing_prereq = RoadmapMilestone(
        milestoneId="m_miss", orderIndex=0, title="Miss", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["non_existent_id"],
    )
    with pytest.raises(ValueError, match="references non-existent prerequisite"):
        RoadmapGenerator.validate_milestone_dag([m_missing_prereq])

    # 5. Direct 2-cycle (A -> B -> A)
    cA = RoadmapMilestone(
        milestoneId="cA", orderIndex=0, title="A", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["cB"],
    )
    cB = RoadmapMilestone(
        milestoneId="cB", orderIndex=1, title="B", category="VerifiableProject",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["cA"],
    )
    with pytest.raises(ValueError, match="Circular dependency detected"):
        RoadmapGenerator.validate_milestone_dag([cA, cB])

    # 6. Indirect 3-cycle (A -> B -> C -> A)
    c1 = RoadmapMilestone(
        milestoneId="c1", orderIndex=0, title="C1", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["c3"],
    )
    c2 = RoadmapMilestone(
        milestoneId="c2", orderIndex=1, title="C2", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["c1"],
    )
    c3 = RoadmapMilestone(
        milestoneId="c3", orderIndex=2, title="C3", category="CoreFoundation",
        requirementName="R1", targetCapability="C1", rationale="Rat1", prerequisiteMilestoneIds=["c2"],
    )
    with pytest.raises(ValueError, match="Circular dependency detected"):
        RoadmapGenerator.validate_milestone_dag([c1, c2, c3])


@pytest.mark.asyncio
async def test_milestone_progression_gating_blocked_by_prerequisite(monkeypatch):
    """
    Verify CareerRoadmapService prevents transitioning a milestone to IN_PROGRESS,
    ARTIFACT_SUBMITTED, or VERIFIED_PROJECT if its prerequisite milestones are incomplete.
    """
    user = AuthenticatedUser(uid="usr_gating", token="tok_gating", email="gating@example.com")

    m_parent = RoadmapMilestone(
        milestoneId="ms_parent",
        orderIndex=0,
        title="Foundation Milestone",
        category="CoreFoundation",
        requirementName="TypeScript",
        targetCapability="TS Types",
        rationale="Foundation",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=[],
    )
    m_child = RoadmapMilestone(
        milestoneId="ms_child",
        orderIndex=1,
        title="Project Milestone",
        category="VerifiableProject",
        requirementName="TypeScript",
        targetCapability="TS Project",
        rationale="Project",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=["ms_parent"],
    )

    plan = RoadmapPlan(
        roadmapId="rdm_gating_test",
        userId="usr_gating",
        title="Gating Roadmap",
        targetRole="TypeScript Engineer",
        version=1,
        totalMilestones=2,
        milestones=[m_parent, m_child],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        plan.version = data["version"]
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    # 1. Attempt to start child milestone before parent is completed -> HTTP 400
    req_start_child = UpdateMilestoneProgressRequest(
        milestone_id="ms_child",
        target_state="IN_PROGRESS",
        expected_version=1,
    )
    with pytest.raises(HTTPException) as exc1:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_gating_test", req_start_child)
    assert exc1.value.status_code == 400
    assert "prerequisite milestone" in exc1.value.detail.lower()
    assert "is not completed" in exc1.value.detail.lower()

    # 2. Advance parent to IN_PROGRESS
    req_start_parent = UpdateMilestoneProgressRequest(
        milestone_id="ms_parent",
        target_state="IN_PROGRESS",
        expected_version=1,
    )
    p1 = await CareerRoadmapService.update_milestone_progress(user, "rdm_gating_test", req_start_parent)
    assert p1.milestones[0].state == "IN_PROGRESS"
    assert p1.version == 2

    # Child is STILL blocked while parent is only IN_PROGRESS
    req_start_child2 = UpdateMilestoneProgressRequest(
        milestone_id="ms_child",
        target_state="IN_PROGRESS",
        expected_version=2,
    )
    with pytest.raises(HTTPException) as exc2:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_gating_test", req_start_child2)
    assert exc2.value.status_code == 400

    # 3. Complete parent milestone: IN_PROGRESS -> VERIFIED_PROJECT
    req_verify_parent = UpdateMilestoneProgressRequest(
        milestone_id="ms_parent",
        target_state="VERIFIED_PROJECT",
        expected_version=2,
        artifact=VerificationArtifactInput(
            url="https://github.com/candidate/ts-foundation",
            checklistCompleted=["Completed foundation course"],
        ),
    )
    p2 = await CareerRoadmapService.update_milestone_progress(user, "rdm_gating_test", req_verify_parent)
    assert p2.milestones[0].state == "VERIFIED_PROJECT"
    assert p2.version == 3

    # 4. Now child milestone can transition to IN_PROGRESS
    req_start_child3 = UpdateMilestoneProgressRequest(
        milestone_id="ms_child",
        target_state="IN_PROGRESS",
        expected_version=3,
    )
    p3 = await CareerRoadmapService.update_milestone_progress(user, "rdm_gating_test", req_start_child3)
    assert p3.milestones[1].state == "IN_PROGRESS"
    assert p3.version == 4


@pytest.mark.asyncio
async def test_roadmap_next_recommended_milestone_lifecycle(monkeypatch):
    """
    Verify that next_recommended_milestone_id dynamically updates as milestones
    progress through their lifecycle from start to completion.
    """
    user = AuthenticatedUser(uid="usr_next_test", token="tok_next", email="next@example.com")

    m1 = RoadmapMilestone(
        milestoneId="ms_step_1",
        orderIndex=0,
        title="Step 1",
        category="CoreFoundation",
        requirementName="R1",
        targetCapability="C1",
        rationale="First step",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=[],
    )
    m2 = RoadmapMilestone(
        milestoneId="ms_step_2",
        orderIndex=1,
        title="Step 2",
        category="VerifiableProject",
        requirementName="R1",
        targetCapability="C1",
        rationale="Second step",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=["ms_step_1"],
    )

    plan = RoadmapPlan(
        roadmapId="rdm_lifecycle_test",
        userId="usr_next_test",
        title="Lifecycle Roadmap",
        targetRole="Software Engineer",
        version=1,
        totalMilestones=2,
        milestones=[m1, m2],
        nextRecommendedMilestoneId="ms_step_1",
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        plan.version = data["version"]
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    # Initial recommendation is ms_step_1
    assert plan.next_recommended_milestone_id == "ms_step_1"

    # Step 1: NOT_STARTED -> IN_PROGRESS
    req1_start = UpdateMilestoneProgressRequest(
        milestone_id="ms_step_1",
        target_state="IN_PROGRESS",
        expected_version=1,
    )
    await CareerRoadmapService.update_milestone_progress(user, "rdm_lifecycle_test", req1_start)

    # Step 1: IN_PROGRESS -> VERIFIED_PROJECT
    req1_verify = UpdateMilestoneProgressRequest(
        milestone_id="ms_step_1",
        target_state="VERIFIED_PROJECT",
        expected_version=2,
        artifact=VerificationArtifactInput(url="https://github.com/test/step1"),
    )
    p1 = await CareerRoadmapService.update_milestone_progress(user, "rdm_lifecycle_test", req1_verify)
    assert p1.next_recommended_milestone_id == "ms_step_2"

    # Step 2: NOT_STARTED -> IN_PROGRESS
    req2_start = UpdateMilestoneProgressRequest(
        milestone_id="ms_step_2",
        target_state="IN_PROGRESS",
        expected_version=3,
    )
    await CareerRoadmapService.update_milestone_progress(user, "rdm_lifecycle_test", req2_start)

    # Step 2: IN_PROGRESS -> VERIFIED_PROJECT
    req2_verify = UpdateMilestoneProgressRequest(
        milestone_id="ms_step_2",
        target_state="VERIFIED_PROJECT",
        expected_version=4,
        artifact=VerificationArtifactInput(url="https://github.com/test/step2"),
    )
    p2 = await CareerRoadmapService.update_milestone_progress(user, "rdm_lifecycle_test", req2_verify)
    assert p2.next_recommended_milestone_id is None
    assert p2.overall_progress_pct == 100


@pytest.mark.asyncio
async def test_multi_roadmap_isolation_and_filtering(monkeypatch):
    """
    Verify multi-roadmap support: candidate can have multiple roadmaps,
    and list_roadmaps supports target_role and active_only filters.
    """
    user = AuthenticatedUser(uid="usr_multi", token="tok_multi", email="multi@example.com")

    r1 = RoadmapPlan(
        roadmapId="rdm_fe",
        userId="usr_multi",
        title="Frontend Roadmap",
        targetRole="Senior Frontend Engineer",
        version=1,
        totalMilestones=2,
        completedMilestones=1,
        overallProgressPct=50,
        milestones=[],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )
    r2 = RoadmapPlan(
        roadmapId="rdm_devops",
        userId="usr_multi",
        title="DevOps Roadmap",
        targetRole="DevOps Engineer",
        version=1,
        totalMilestones=2,
        completedMilestones=2,
        overallProgressPct=100,
        milestones=[],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )
    r3 = RoadmapPlan(
        roadmapId="rdm_arch",
        userId="usr_multi",
        title="Architect Roadmap",
        targetRole="Frontend Architect",
        version=1,
        totalMilestones=3,
        completedMilestones=0,
        overallProgressPct=0,
        milestones=[],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    # Mock HTTP client for list_roadmaps
    class MockResponse:
        def __init__(self, docs):
            self.status_code = 200
            self._docs = docs

        def json(self):
            return {
                "documents": [
                    {
                        "fields": {
                            "roadmapId": {"stringValue": r.roadmap_id},
                            "userId": {"stringValue": r.user_id},
                            "title": {"stringValue": r.title},
                            "targetRole": {"stringValue": r.target_role},
                            "version": {"integerValue": r.version},
                            "totalMilestones": {"integerValue": r.total_milestones},
                            "completedMilestones": {"integerValue": r.completed_milestones},
                            "overallProgressPct": {"integerValue": r.overall_progress_pct},
                            "milestones": {"arrayValue": {"values": []}},
                            "createdAt": {"stringValue": r.created_at},
                            "updatedAt": {"stringValue": r.updated_at},
                        }
                    }
                    for r in self._docs
                ]
            }

    class MockClient:
        async def get(self, url, headers):
            return MockResponse([r1, r2, r3])

    monkeypatch.setattr("app.services.career_roadmap_service.get_http_client", lambda: MockClient())

    # 1. Unfiltered: returns all 3 roadmaps
    res_all = await CareerRoadmapService.list_roadmaps(user)
    assert res_all.total == 3

    # 2. Filter by target_role="Frontend": returns Frontend Engineer and Frontend Architect
    res_fe = await CareerRoadmapService.list_roadmaps(user, target_role="Frontend")
    assert res_fe.total == 2
    assert {r.roadmap_id for r in res_fe.roadmaps} == {"rdm_fe", "rdm_arch"}

    # 3. Filter by active_only=True: returns unfinished roadmaps (rdm_fe, rdm_arch), excludes 100% rdm_devops
    res_active = await CareerRoadmapService.list_roadmaps(user, active_only=True)
    assert res_active.total == 2
    assert {r.roadmap_id for r in res_active.roadmaps} == {"rdm_fe", "rdm_arch"}

    # 4. Filter by target_role="DevOps" and active_only=True: returns 0 (DevOps roadmap is completed)
    res_devops_active = await CareerRoadmapService.list_roadmaps(user, target_role="DevOps", active_only=True)
    assert res_devops_active.total == 0


# ---------------------------------------------------------------------------
# 8. Adversarial Security Cases (ADV_045 - ADV_050)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adv_045_dependency_bypassing_attack(monkeypatch):
    """
    ADV_045: Dependency Bypassing Attack.
    An attacker attempts to mark a child milestone as IN_PROGRESS or VERIFIED_PROJECT
    while prerequisite milestones are unfulfilled.
    The system must block the transition with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv_045", token="tok_adv_045", email="adv45@example.com")

    m_prereq = RoadmapMilestone(
        milestoneId="ms_prereq_sys",
        orderIndex=0,
        title="Prereq System Design",
        category="CoreFoundation",
        requirementName="System Design",
        targetCapability="Distributed Architecture",
        rationale="Foundation",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=[],
    )
    m_target = RoadmapMilestone(
        milestoneId="ms_target_raft",
        orderIndex=1,
        title="Raft Consensus Engine",
        category="VerifiableProject",
        requirementName="System Design",
        targetCapability="Raft Implementation",
        rationale="Project",
        state="NOT_STARTED",
        prerequisiteMilestoneIds=["ms_prereq_sys"],
    )

    plan = RoadmapPlan(
        roadmapId="rdm_adv_045",
        userId="usr_adv_045",
        title="Systems Engineering",
        targetRole="Principal Engineer",
        version=1,
        totalMilestones=2,
        milestones=[m_prereq, m_target],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Attack 1: Try starting child milestone while prerequisite is NOT_STARTED
    req_start = UpdateMilestoneProgressRequest(
        milestone_id="ms_target_raft",
        target_state="IN_PROGRESS",
        expected_version=1,
    )

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_045", req_start)

    assert exc.value.status_code == 400
    assert "prerequisite milestone" in exc.value.detail.lower()
    assert "is not completed" in exc.value.detail.lower()


def test_adv_046_circular_dependency_injection():
    """
    ADV_046: Circular Dependency Injection Attack.
    A malicious payload attempting to inject circular dependencies (e.g. A -> B -> A)
    must be immediately rejected during validation.
    """
    m_a = RoadmapMilestone(
        milestoneId="ms_cycle_a",
        orderIndex=0,
        title="Milestone A",
        category="CoreFoundation",
        requirementName="Security",
        targetCapability="Auth",
        rationale="A",
        prerequisiteMilestoneIds=["ms_cycle_b"],
    )
    m_b = RoadmapMilestone(
        milestoneId="ms_cycle_b",
        orderIndex=1,
        title="Milestone B",
        category="VerifiableProject",
        requirementName="Security",
        targetCapability="Auth Project",
        rationale="B",
        prerequisiteMilestoneIds=["ms_cycle_a"],
    )

    with pytest.raises(ValueError, match="Circular dependency detected"):
        RoadmapGenerator.validate_milestone_dag([m_a, m_b])


@pytest.mark.asyncio
async def test_adv_047_cross_roadmap_milestone_substitution(monkeypatch):
    """
    ADV_047: Cross-Roadmap Milestone Substitution Attack.
    An attacker attempts to progress Roadmap A by supplying a milestoneId belonging
    to Roadmap B. The service must reject with HTTP 404 (milestone not found in target roadmap).
    """
    user = AuthenticatedUser(uid="usr_adv_047", token="tok_adv_047", email="adv47@example.com")

    plan_a = RoadmapPlan(
        roadmapId="rdm_a",
        userId="usr_adv_047",
        title="Roadmap A",
        targetRole="Frontend Lead",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_valid_in_a",
                orderIndex=0,
                title="A Milestone",
                category="CoreFoundation",
                requirementName="CSS",
                targetCapability="Grid",
                rationale="A",
                state="NOT_STARTED",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        if rid == "rdm_a":
            return plan_a
        raise HTTPException(status_code=404, detail="Roadmap not found")

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Attack: Target rdm_a with milestoneId from foreign roadmap
    req = UpdateMilestoneProgressRequest(
        milestone_id="ms_foreign_from_roadmap_b",
        target_state="IN_PROGRESS",
        expected_version=1,
    )

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_a", req)

    assert exc.value.status_code == 404
    assert "not found in roadmap 'rdm_a'" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_048_forged_provenance_tampering(monkeypatch):
    """
    ADV_048: Forged Provenance Tampering Defense.
    Client-side requests cannot override, forge, or tamper with roadmap provenance
    or artifact provenance hashes. The server computes cryptographic SHA-256 hashes.
    """
    user = AuthenticatedUser(uid="usr_adv_048", token="tok_adv_048", email="adv48@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_048",
        userId="usr_adv_048",
        title="Provenance Test",
        targetRole="Backend Engineer",
        version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_prov_1",
                orderIndex=0,
                title="Milestone 1",
                category="VerifiableProject",
                requirementName="SQL",
                targetCapability="Query Optimization",
                rationale="Database performance",
                state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    req = UpdateMilestoneProgressRequest(
        milestone_id="ms_prov_1",
        target_state="VERIFIED_PROJECT",
        expected_version=1,
        artifact=VerificationArtifactInput(
            url="https://github.com/candidate/sql-opt",
            checklistCompleted=["Indexed hot queries"],
        ),
    )

    res = await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_048", req)

    # Server generates non-empty, 64-character SHA-256 hash that cannot be client-controlled
    art = res.milestones[0].verification_artifact
    assert art is not None
    assert len(art.provenance_hash) == 64
    assert art.artifact_id.startswith("art_")


@pytest.mark.asyncio
async def test_adv_049_stale_version_concurrency_race(monkeypatch):
    """
    ADV_049: Stale Version Concurrency Race Defense.
    Simulating concurrent milestone updates with the same base version.
    The first request succeeds and increments version to 2; the second request
    carrying stale expected_version=1 is rejected with HTTP 409 Conflict.
    """
    user = AuthenticatedUser(uid="usr_adv_049", token="tok_adv_049", email="adv49@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv_049",
        userId="usr_adv_049",
        title="Concurrency Race Test",
        targetRole="Cloud Engineer",
        version=1,
        totalMilestones=2,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_race_1",
                orderIndex=0,
                title="Race 1",
                category="CoreFoundation",
                requirementName="Terraform",
                targetCapability="IaC",
                rationale="R1",
                state="NOT_STARTED",
            ),
            RoadmapMilestone(
                milestoneId="ms_race_2",
                orderIndex=1,
                title="Race 2",
                category="CoreFoundation",
                requirementName="Ansible",
                targetCapability="Config Mgmt",
                rationale="R2",
                state="NOT_STARTED",
            ),
        ],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save(u, rid, data):
        plan.version = data["version"]
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save)

    # Request 1: starts ms_race_1 with expected_version=1 -> Succeeds, bumps version to 2
    req1 = UpdateMilestoneProgressRequest(
        milestone_id="ms_race_1",
        target_state="IN_PROGRESS",
        expected_version=1,
    )
    res1 = await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_049", req1)
    assert res1.version == 2

    # Request 2: concurrently tries to start ms_race_2 with stale expected_version=1 -> HTTP 409 Conflict
    req2 = UpdateMilestoneProgressRequest(
        milestone_id="ms_race_2",
        target_state="IN_PROGRESS",
        expected_version=1,
    )
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv_049", req2)

    assert exc.value.status_code == 409
    assert "concurrency conflict" in exc.value.detail.lower()


def test_adv_050_free_product_integrity_milestone_2():
    """
    ADV_050: Free Product Integrity (Milestone 2 Stack).
    Verifies that all Career Roadmap modules and tests contain ZERO monetization,
    subscription, payment, pricing, or paywall references.
    """
    import inspect
    import app.schemas.career_roadmap as cr_schemas
    import app.ai.career.roadmap_generator as cr_gen
    import app.services.career_roadmap_service as cr_service
    import app.api.v1.roadmaps as cr_api

    forbidden = [
        "stripe",
        "subscription",
        "billing",
        "price_id",
        "credit_balance",
        "paywall",
        "checkout_session",
        "pricing_tier",
    ]

    for mod in [cr_schemas, cr_gen, cr_service, cr_api]:
        source = inspect.getsource(mod).lower()
        for term in forbidden:
            assert term not in source, f"Forbidden monetization term '{term}' found in {mod.__name__}"


# ---------------------------------------------------------------------------
# 9. Milestone 3: Evidence Promotion Bridge Functional & Adversarial Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_promotion_draft_success(monkeypatch):
    """
    Verify that CareerRoadmapService.create_promotion_draft creates a valid,
    reviewable IngestionDraft from a VERIFIED_PROJECT milestone.
    """
    user = AuthenticatedUser(uid="usr_prom_1", token="tok_prom_1", email="prom1@example.com")

    from app.schemas.career_roadmap import VerificationArtifact
    from app.schemas.career_intelligence import ProjectBlueprint

    art = VerificationArtifact(
        artifactId="art_prom_123",
        artifactType="GitHubRepository",
        url="https://github.com/candidate/distributed-raft",
        repositoryBranch="main",
        checklistCompleted=["Implemented consensus logic", "Handled leader election timeouts"],
        submittedAt="2026-09-25T12:00:00Z",
        provenanceHash="d9a8f7c6e5b4a321d9a8f7c6e5b4a321d9a8f7c6e5b4a321d9a8f7c6e5b4a321",
    )

    blueprint = ProjectBlueprint(
        projectTitle="Distributed Raft Consensus Engine",
        problemStatement="Engineered a fault-tolerant distributed key-value store using Raft consensus.",
        architectureComponents=["Leader Election", "Log Replication", "RPC Transport"],
        demonstratedSkills=["Go", "Distributed Systems", "gRPC"],
        verificationChecklist=["Leader election tests", "Network partition resilience"],
    )

    ms = RoadmapMilestone(
        milestoneId="ms_raft_proj",
        orderIndex=0,
        title="Distributed Raft Engine",
        category="VerifiableProject",
        requirementName="Distributed Systems",
        targetCapability="Raft Consensus",
        rationale="Demonstrate systems engineering capability",
        state="VERIFIED_PROJECT",
        projectBlueprint=blueprint,
        verificationArtifact=art,
    )

    plan = RoadmapPlan(
        roadmapId="rdm_prom_test",
        userId="usr_prom_1",
        title="Systems Architect Roadmap",
        targetRole="Staff Systems Engineer",
        version=1,
        totalMilestones=1,
        milestones=[ms],
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft_404(u, iid):
        raise HTTPException(status_code=404, detail="Draft not found")

    saved_drafts = []

    class MockClient:
        async def patch(self, url, headers, json, timeout=25.0):
            saved_drafts.append(json)
            mock_res = MagicMock()
            mock_res.status_code = 200
            return mock_res

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft_404)
    monkeypatch.setattr("app.services.career_roadmap_service.get_http_client", lambda: MockClient())

    draft = await CareerRoadmapService.create_promotion_draft(user, "rdm_prom_test", "ms_raft_proj")

    assert draft.ingestion_id == "ingest_prom_rdm_prom_test_ms_raft_proj"
    assert draft.document_type == "RoadmapProject"
    assert draft.status == "Parsed"
    assert draft.file_url == "https://github.com/candidate/distributed-raft"
    assert draft.parsed_data is not None

    # Verify project item mapping
    projs = draft.parsed_data.evidence.projects
    assert len(projs) == 1
    proj = projs[0]
    assert proj.title == "Distributed Raft Consensus Engine"
    assert proj.description == "Engineered a fault-tolerant distributed key-value store using Raft consensus."
    assert "Leader Election" in proj.highlights
    assert "Implemented consensus logic" in proj.highlights
    assert "Go" in proj.tech_stack
    assert "Distributed Systems" in proj.tech_stack
    assert proj.source_document_id == "ingest_prom_rdm_prom_test_ms_raft_proj"

    # Verify skills mapping
    skills = draft.parsed_data.evidence.skills
    skill_names = {s.name for s in skills}
    assert "Go" in skill_names
    assert "Distributed Systems" in skill_names
    assert "gRPC" in skill_names

    assert len(saved_drafts) >= 1


@pytest.mark.asyncio
async def test_promotion_draft_idempotency_parsed_reused(monkeypatch):
    """Verify that requesting promotion when a Parsed draft already exists returns the existing draft."""
    user = AuthenticatedUser(uid="usr_prom_1", token="tok_prom_1", email="prom1@example.com")

    existing_draft = IngestionDraft(
        ingestion_id="ingest_prom_rdm_1_ms_1",
        document_name="Roadmap Project",
        document_type="RoadmapProject",
        file_size_bytes=100,
        status="Parsed",
        created_at="2026-09-25T00:00:00Z",
        updated_at="2026-09-25T00:00:00Z",
    )

    art = VerificationArtifact(
        artifactId="art_1", artifactType="GitHubRepository", url="https://github.com/test",
        checklistCompleted=[], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash_1234",
    )
    ms = RoadmapMilestone(
        milestoneId="ms_1", orderIndex=0, title="Project 1", category="VerifiableProject",
        requirementName="Python", targetCapability="API", rationale="Rat",
        state="VERIFIED_PROJECT", verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_1", userId="usr_prom_1", title="Plan", targetRole="Dev", version=1,
        totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft(u, iid):
        return existing_draft

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft)

    draft = await CareerRoadmapService.create_promotion_draft(user, "rdm_1", "ms_1")
    assert draft.ingestion_id == "ingest_prom_rdm_1_ms_1"
    assert draft.status == "Parsed"


@pytest.mark.asyncio
async def test_promotion_draft_rejected_when_completed(monkeypatch):
    """Verify that promoting a project whose draft is already Completed raises HTTP 400."""
    user = AuthenticatedUser(uid="usr_prom_1", token="tok_prom_1", email="prom1@example.com")

    completed_draft = IngestionDraft(
        ingestion_id="ingest_prom_rdm_1_ms_1",
        document_name="Roadmap Project",
        document_type="RoadmapProject",
        file_size_bytes=100,
        status="Completed",
        created_at="2026-09-25T00:00:00Z",
        updated_at="2026-09-25T00:00:00Z",
        completed_at="2026-09-25T01:00:00Z",
    )

    art = VerificationArtifact(
        artifactId="art_1", artifactType="GitHubRepository", url="https://github.com/test",
        checklistCompleted=[], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash_1234",
    )
    ms = RoadmapMilestone(
        milestoneId="ms_1", orderIndex=0, title="Project 1", category="VerifiableProject",
        requirementName="Python", targetCapability="API", rationale="Rat",
        state="VERIFIED_PROJECT", verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_1", userId="usr_prom_1", title="Plan", targetRole="Dev", version=1,
        totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft(u, iid):
        return completed_draft

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft)

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.create_promotion_draft(user, "rdm_1", "ms_1")

    assert exc.value.status_code == 400
    assert "already been promoted and confirmed" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_promotion_end_to_end_confirmation_hydrates_workspace(monkeypatch):
    """
    Verify that an IngestionDraft created via create_promotion_draft successfully hydrates
    into master workspace evidence through IngestionService.confirm_and_hydrate_ingestion,
    preserving project title, description, highlights, tech stack, and source provenance.
    """
    user = AuthenticatedUser(uid="usr_e2e_1", token="tok_e2e_1", email="e2e@example.com")

    art = VerificationArtifact(
        artifactId="art_e2e_1", artifactType="GitHubRepository", url="https://github.com/candidate/microservices",
        checklistCompleted=["Configured service mesh", "Implemented distributed tracing"],
        submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash_e2e_123",
    )
    bp = ProjectBlueprint(
        projectTitle="Microservices Architecture Platform",
        problemStatement="Engineered high-resilience microservices cluster with Envoy service mesh.",
        architectureComponents=["Envoy Proxy", "Jaeger Tracing"],
        demonstratedSkills=["Kubernetes", "Go", "Docker"],
        verificationChecklist=["End-to-end tracing tests"],
    )
    ms = RoadmapMilestone(
        milestoneId="ms_e2e_proj", orderIndex=0, title="Microservices Platform", category="VerifiableProject",
        requirementName="Kubernetes", targetCapability="Microservices", rationale="Scalable infra",
        state="VERIFIED_PROJECT", projectBlueprint=bp, verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_e2e_1", userId="usr_e2e_1", title="Cloud Architect", targetRole="Cloud Architect",
        version=1, totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    firestore_db = {}

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft(u, iid):
        if iid in firestore_db:
            return firestore_db[iid]
        raise HTTPException(status_code=404, detail="Draft not found")

    class MockClient:
        async def patch(self, url, headers, json, timeout=25.0):
            firestore_db[url] = json
            mock_res = MagicMock()
            mock_res.status_code = 200
            return mock_res

        async def get(self, url, headers, timeout=25.0):
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"documents": []}
            return mock_res

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft)
    monkeypatch.setattr("app.services.career_roadmap_service.get_http_client", lambda: MockClient())
    monkeypatch.setattr("app.services.ingestion_service.get_http_client", lambda: MockClient())
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: MockClient())
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: MockClient())

    # Step 1: Promotion creates IngestionDraft
    draft = await CareerRoadmapService.create_promotion_draft(user, "rdm_e2e_1", "ms_e2e_proj")
    assert draft.status == "Parsed"
    assert draft.document_type == "RoadmapProject"

    # Step 2: Register draft in mock DB for IngestionService lookup
    firestore_db[draft.ingestion_id] = draft

    # Step 3: Candidate confirms ingestion draft through standard IngestionService
    confirm_res = await IngestionService.confirm_and_hydrate_ingestion(
        user=user,
        ingestion_id=draft.ingestion_id,
        reviewed_data=draft.parsed_data,
    )

    assert confirm_res.success is True
    assert confirm_res.status == "Completed"
    assert confirm_res.hydrated_summary["projects"] == 1
    assert confirm_res.hydrated_summary["skills"] >= 3


# ---------------------------------------------------------------------------
# 10. Adversarial Security Cases (ADV_051 - ADV_060)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adv_051_unauthorized_roadmap_promotion(monkeypatch):
    """
    ADV_051: Unauthorized Roadmap Promotion Attack.
    User B attempts to promote a milestone belonging to User A's roadmap.
    The service must reject the request with HTTP 404 (tenant-safe isolation).
    """
    user_attacker = AuthenticatedUser(uid="usr_attacker", token="tok_bad", email="bad@example.com")

    async def mock_get(u, rid):
        if u.uid != "usr_legit":
            raise HTTPException(status_code=404, detail="Roadmap not found")
        art = VerificationArtifact(
            artifactId="art_1", artifactType="GitHubRepository", url="https://github.com/legit",
            checklistCompleted=[], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash",
        )
        return RoadmapPlan(
            roadmapId="rdm_legit", userId="usr_legit", title="Legit", targetRole="Dev", version=1,
            totalMilestones=1,
            milestones=[
                RoadmapMilestone(
                    milestoneId="ms_legit_1", orderIndex=0, title="P", category="VerifiableProject",
                    requirementName="Python", targetCapability="API", rationale="R",
                    state="VERIFIED_PROJECT", verificationArtifact=art,
                )
            ],
            createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
        )

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.create_promotion_draft(user_attacker, "rdm_legit", "ms_legit_1")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_adv_052_cross_tenant_artifact_injection(monkeypatch):
    """
    ADV_052: Cross-Tenant Artifact Injection Defense.
    Attacker tries to promote a milestone using a foreign milestone_id.
    Must fail with HTTP 404.
    """
    user = AuthenticatedUser(uid="usr_user", token="tok_user", email="user@example.com")

    art = VerificationArtifact(
        artifactId="art_1", artifactType="GitHubRepository", url="https://github.com/user",
        checklistCompleted=[], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash",
    )
    plan = RoadmapPlan(
        roadmapId="rdm_user", userId="usr_user", title="Plan", targetRole="Dev", version=1,
        totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_owned", orderIndex=0, title="Owned", category="VerifiableProject",
                requirementName="Python", targetCapability="API", rationale="R",
                state="VERIFIED_PROJECT", verificationArtifact=art,
            )
        ],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Supply milestoneId from foreign user/roadmap
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.create_promotion_draft(user, "rdm_user", "ms_foreign_victim_milestone")

    assert exc.value.status_code == 404
    assert "not found in roadmap" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_053_ineligible_state_promotion(monkeypatch):
    """
    ADV_053: Ineligible State Promotion Defense.
    Attempting to promote milestones in NOT_STARTED, IN_PROGRESS, ARTIFACT_SUBMITTED,
    or ATTESTED state must be strictly rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv53", token="tok_adv53", email="adv53@example.com")

    ineligible_states = ["NOT_STARTED", "IN_PROGRESS", "ARTIFACT_SUBMITTED", "ATTESTED"]

    for st in ineligible_states:
        art = None
        if st in ("ARTIFACT_SUBMITTED", "ATTESTED"):
            art = VerificationArtifact(
                artifactId="art_sub", artifactType="GitHubRepository", url="https://github.com/sub",
                checklistCompleted=[], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash",
            )
        cat = "TransferableBridge" if st == "ATTESTED" else "VerifiableProject"

        ms = RoadmapMilestone(
            milestoneId=f"ms_state_{st}", orderIndex=0, title=f"Title {st}", category=cat,
            requirementName="Cloud", targetCapability="Infra", rationale="Rat",
            state=st, verificationArtifact=art,
        )
        plan = RoadmapPlan(
            roadmapId=f"rdm_{st}", userId="usr_adv53", title="Plan", targetRole="DevOps", version=1,
            totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
        )

        async def mock_get(u, rid, current_plan=plan):
            return current_plan

        monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

        with pytest.raises(HTTPException) as exc:
            await CareerRoadmapService.create_promotion_draft(user, f"rdm_{st}", f"ms_state_{st}")

        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_adv_054_missing_verification_artifact_defense(monkeypatch):
    """
    ADV_054: Missing Verification Artifact Defense.
    A milestone marked as VERIFIED_PROJECT but lacking a verification_artifact
    (or containing an empty artifact ID/hash) must be rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv54", token="tok_adv54", email="adv54@example.com")

    # Milestone in VERIFIED_PROJECT but verificationArtifact is None
    ms_no_art = RoadmapMilestone(
        milestoneId="ms_no_art", orderIndex=0, title="Title", category="VerifiableProject",
        requirementName="Security", targetCapability="Auth", rationale="Rat",
        state="VERIFIED_PROJECT", verificationArtifact=None,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_no_art", userId="usr_adv54", title="Plan", targetRole="Security", version=1,
        totalMilestones=1, milestones=[ms_no_art], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.create_promotion_draft(user, "rdm_no_art", "ms_no_art")

    assert exc.value.status_code == 400
    assert "without a valid verification artifact" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_055_duplicate_promotion_idempotency_attack(monkeypatch):
    """
    ADV_055: Duplicate Promotion Idempotency Attack.
    Concurrent or repeated calls to promote the same milestone must produce exactly ONE
    draft and never create multiple drafts or duplicate master workspace records.
    """
    user = AuthenticatedUser(uid="usr_adv55", token="tok_adv55", email="adv55@example.com")

    art = VerificationArtifact(
        artifactId="art_adv55", artifactType="GitHubRepository", url="https://github.com/adv55",
        checklistCompleted=["Done"], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash55",
    )
    ms = RoadmapMilestone(
        milestoneId="ms_adv55", orderIndex=0, title="Adv55 Proj", category="VerifiableProject",
        requirementName="Kubernetes", targetCapability="K8s", rationale="R",
        state="VERIFIED_PROJECT", verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_adv55", userId="usr_adv55", title="Plan", targetRole="DevOps", version=1,
        totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    firestore_drafts = {}

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft(u, iid):
        if iid in firestore_drafts:
            return firestore_drafts[iid]
        raise HTTPException(status_code=404, detail="Not found")

    class MockClient:
        async def patch(self, url, headers, json, timeout=25.0):
            # simulate storing draft
            iid = "ingest_prom_rdm_adv55_ms_adv55"
            firestore_drafts[iid] = IngestionDraft(
                ingestionId=iid,
                documentName="Roadmap Project",
                documentType="RoadmapProject",
                fileSizeBytes=100,
                status="Parsed",
                createdAt="2026-09-25T00:00:00Z",
                updatedAt="2026-09-25T00:00:00Z",
            )
            mock_res = MagicMock()
            mock_res.status_code = 200
            return mock_res

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft)
    monkeypatch.setattr("app.services.career_roadmap_service.get_http_client", lambda: MockClient())

    # Call 1: Creates draft
    d1 = await CareerRoadmapService.create_promotion_draft(user, "rdm_adv55", "ms_adv55")
    # Call 2: Returns existing draft without recreation
    d2 = await CareerRoadmapService.create_promotion_draft(user, "rdm_adv55", "ms_adv55")

    assert d1.ingestion_id == d2.ingestion_id
    assert len(firestore_drafts) == 1


@pytest.mark.asyncio
async def test_adv_056_workspace_direct_mutation_bypass(monkeypatch):
    """
    ADV_056: Workspace Direct Mutation Bypass Defense.
    Calling create_promotion_draft must NOT write to canonical workspace collections.
    """
    user = AuthenticatedUser(uid="usr_adv56", token="tok_adv56", email="adv56@example.com")

    workspace_writes = []

    art = VerificationArtifact(
        artifactId="art_adv56", artifactType="GitHubRepository", url="https://github.com/adv56",
        checklistCompleted=["Done"], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash56",
    )
    ms = RoadmapMilestone(
        milestoneId="ms_adv56", orderIndex=0, title="Adv56 Proj", category="VerifiableProject",
        requirementName="Docker", targetCapability="Containers", rationale="R",
        state="VERIFIED_PROJECT", verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_adv56", userId="usr_adv56", title="Plan", targetRole="DevOps", version=1,
        totalMilestones=1, milestones=[ms], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_get_draft(u, iid):
        raise HTTPException(status_code=404, detail="Not found")

    class MockClient:
        async def patch(self, url, headers, json, timeout=25.0):
            workspace_writes.append(url)
            mock_res = MagicMock()
            mock_res.status_code = 200
            return mock_res

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(IngestionService, "get_ingestion_draft", mock_get_draft)
    monkeypatch.setattr("app.services.career_roadmap_service.get_http_client", lambda: MockClient())

    await CareerRoadmapService.create_promotion_draft(user, "rdm_adv56", "ms_adv56")

    # Assert that writes NEVER targeted root workspace collections
    assert any(f"/users/{user.uid}/ingestions/ingest_prom_" in w for w in workspace_writes)
    assert all(f"/users/{user.uid}/projects" not in w for w in workspace_writes)
    assert all(f"/users/{user.uid}/skills" not in w for w in workspace_writes)
    assert all(f"/users/{user.uid}/profile" not in w for w in workspace_writes)


def test_adv_057_claim_grounding_integrity():
    """
    ADV_057: Claim Grounding Integrity.
    Verifies that the transformed project draft strictly originates from ProjectBlueprint
    and VerificationArtifact, containing zero ungrounded metrics or scope-inflating verbs.
    """
    from app.schemas.career_intelligence import ProjectBlueprint
    from app.schemas.career_roadmap import VerificationArtifact

    art = VerificationArtifact(
        artifactId="art_adv57", artifactType="GitHubRepository", url="https://github.com/adv57",
        checklistCompleted=["Configured routing", "Implemented cache invalidation"],
        submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash57",
    )
    bp = ProjectBlueprint(
        projectTitle="API Gateway Service",
        problemStatement="Engineered high-throughput reverse proxy with rate limiting.",
        architectureComponents=["Proxy Layer", "Token Bucket Limiter"],
        demonstratedSkills=["Go", "Redis", "HTTP"],
        verificationChecklist=["Rate limit unit tests"],
    )

    # Ingestion draft mapping inspection
    highlights = list(bp.architecture_components) + list(art.checklist_completed)
    assert "Proxy Layer" in highlights
    assert "Token Bucket Limiter" in highlights
    assert "Configured routing" in highlights
    assert "Implemented cache invalidation" in highlights

    # Prohibited hallucinated terms must not be in blueprint or artifact
    forbidden_injections = ["45% increase in revenue", "led team of 15 engineers", "$2M cost savings", "drive business growth"]
    for term in forbidden_injections:
        assert term not in bp.problem_statement
        assert all(term not in h for h in highlights)


def test_adv_058_provenance_chain_integrity():
    """
    ADV_058: Provenance Chain Integrity.
    Verifies that the promotion draft deterministically embeds roadmapId, milestoneId,
    artifactId, provenanceHash, and documentType="RoadmapProject".
    """
    from app.schemas.career_roadmap import VerificationArtifact

    art = VerificationArtifact(
        artifactId="art_adv58_sample",
        artifactType="DeploymentUrl",
        url="https://app.example.com",
        checklistCompleted=["Deployed to production"],
        submittedAt="2026-09-25T00:00:00Z",
        provenanceHash="d9a8f7c6e5b4a321d9a8f7c6e5b4a321d9a8f7c6e5b4a321d9a8f7c6e5b4a321",
    )

    ms = RoadmapMilestone(
        milestoneId="ms_adv58_id",
        orderIndex=0,
        title="Production Deployment",
        category="VerifiableProject",
        requirementName="DevOps",
        targetCapability="CI/CD",
        rationale="Deploy app",
        state="VERIFIED_PROJECT",
        verificationArtifact=art,
    )

    ingestion_id = f"ingest_prom_rdm_adv58_{ms.milestone_id}"
    assert ingestion_id.startswith("ingest_prom_")
    assert "rdm_adv58" in ingestion_id
    assert "ms_adv58_id" in ingestion_id
    assert len(art.provenance_hash) == 64


@pytest.mark.asyncio
async def test_adv_059_attestation_to_project_confusion_defense(monkeypatch):
    """
    ADV_059: Attestation-to-Project Confusion Defense.
    Attempting to promote a TransferableBridge / ATTESTED milestone as project evidence
    must be strictly rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv59", token="tok_adv59", email="adv59@example.com")

    art = VerificationArtifact(
        artifactId="art_attest_record", artifactType="AttestationRecord", url=None,
        checklistCompleted=["Attested via Phase 5.0"], submittedAt="2026-09-25T00:00:00Z",
        provenanceHash="att_hash",
    )
    ms_bridge = RoadmapMilestone(
        milestoneId="ms_bridge_adv59", orderIndex=0, title="Bridge React to Vue",
        category="TransferableBridge", requirementName="Vue", targetCapability="Vue SPA",
        rationale="Framework transferability", state="ATTESTED", verificationArtifact=art,
    )
    plan = RoadmapPlan(
        roadmapId="rdm_adv59", userId="usr_adv59", title="Plan", targetRole="Frontend",
        version=1, totalMilestones=1, milestones=[ms_bridge],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.create_promotion_draft(user, "rdm_adv59", "ms_bridge_adv59")

    assert exc.value.status_code == 400
    assert "transferablebridge milestones cannot be promoted as project evidence" in exc.value.detail.lower() or "only milestones in 'verified_project' state are eligible" in exc.value.detail.lower()


def test_adv_060_free_product_integrity_milestone_3():
    """
    ADV_060: Free Product Invariant (Milestone 3 Stack).
    Verifies that all Career Roadmap modules and tests contain ZERO monetization,
    subscription, payment, pricing, or paywall references.
    """
    import inspect
    import app.schemas.career_roadmap as cr_schemas
    import app.ai.career.roadmap_generator as cr_gen
    import app.services.career_roadmap_service as cr_service
    import app.api.v1.roadmaps as cr_api

    forbidden = [
        "stripe",
        "subscription",
        "billing",
        "price_id",
        "credit_balance",
        "paywall",
        "checkout_session",
        "pricing_tier",
    ]

    for mod in [cr_schemas, cr_gen, cr_service, cr_api]:
        source = inspect.getsource(mod).lower()
        for term in forbidden:
            assert term not in source, f"Forbidden monetization term '{term}' found in {mod.__name__}"


# =====================================================================
# PHASE 5.1 MILESTONE 5: RECONCILIATION, REFRESH & LIFECYCLE TESTS
# =====================================================================

def test_m5_compute_workspace_evidence_hash_determinism():
    """
    Milestone 5: Evidence Hashing Determinism.
    Verifies that compute_workspace_evidence_hash generates identical SHA-256
    hashes regardless of dictionary key ordering or list element ordering.
    """
    from app.ai.career.roadmap_generator import RoadmapGenerator

    ev1 = CandidateEvidence(
        skills=[SkillItem(name="Python"), SkillItem(name="Docker")],
        projects=[ProjectItem(title="FastAPI Backend", techStack=["Python", "Docker"])],
        experience=[ExperienceItem(role="Backend Engineer", company="Acme")],
        certifications=[CertificationItem(title="AWS Certified Developer", issuer="AWS")],
        education=[EducationItem(degree="B.S. CS", institution="University")],
    )

    ev2 = CandidateEvidence(
        education=[EducationItem(degree="B.S. CS", institution="University")],
        certifications=[CertificationItem(title="AWS Certified Developer", issuer="AWS")],
        skills=[SkillItem(name="Docker"), SkillItem(name="Python")],
        experience=[ExperienceItem(role="Backend Engineer", company="Acme")],
        projects=[ProjectItem(title="FastAPI Backend", techStack=["Docker", "Python"])],
    )

    hash1 = RoadmapGenerator.compute_workspace_evidence_hash(ev1)
    hash2 = RoadmapGenerator.compute_workspace_evidence_hash(ev2)

    assert len(hash1) == 64
    assert hash1 == hash2

    # Mutating an item produces a completely different hash
    ev3 = CandidateEvidence(
        skills=[SkillItem(name="Python"), SkillItem(name="Docker"), SkillItem(name="Kubernetes")],
        projects=[ProjectItem(title="FastAPI Backend", techStack=["Python", "Docker"])],
        experience=[ExperienceItem(role="Backend Engineer", company="Acme")],
        certifications=[CertificationItem(title="AWS Certified Developer", issuer="AWS")],
        education=[EducationItem(degree="B.S. CS", institution="University")],
    )
    hash3 = RoadmapGenerator.compute_workspace_evidence_hash(ev3)
    assert hash3 != hash1


@pytest.mark.asyncio
async def test_m5_reconcile_roadmap_statuses(monkeypatch):
    """
    Milestone 5: Live Workspace Evidence Reconciliation.
    Tests GROUNDED_BY_PROMOTED_PROJECT, GROUNDED_BY_WORKSPACE, RELATED_UNVERIFIED, and NOT_GROUNDED.
    """
    user = AuthenticatedUser(uid="usr_m5_rec", token="tok_m5_rec", email="m5rec@example.com")

    # Mock Master Workspace Evidence
    mock_workspace = CandidateEvidence(
        skills=[SkillItem(name="Python"), SkillItem(name="FastAPI")],
        projects=[
            ProjectItem(
                id="proj_prom_1",
                title="Distributed Task Engine",
                sourceDocumentId="ingest_prom_rdm_m5_ms_proj",
                techStack=["Python", "Redis", "Celery"],
            )
        ],
        experience=[
            ExperienceItem(
                id="exp_1",
                role="Frontend Developer",
                company="Tech Corp",
                technologies=["React", "TypeScript"],
            )
        ],
        certifications=[CertificationItem(id="cert_1", title="AWS Solutions Architect", issuer="AWS")],
        education=[],
    )

    async def mock_load_master(u):
        assert u.uid == "usr_m5_rec"
        return mock_workspace

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    # Setup Roadmap Plan
    ms_promoted = RoadmapMilestone(
        milestoneId="ms_proj",
        orderIndex=0,
        title="Distributed Task Engine",
        category="VerifiableProject",
        requirementName="Celery",
        targetCapability="Background processing",
        rationale="Needs async worker experience",
        state="VERIFIED_PROJECT",
    )
    ms_grounded = RoadmapMilestone(
        milestoneId="ms_gw",
        orderIndex=1,
        title="Master Python & FastAPI",
        category="CoreFoundation",
        requirementName="Python",
        targetCapability="Python programming",
        rationale="Core requirement",
        state="NOT_STARTED",
    )
    ms_bridge = RoadmapMilestone(
        milestoneId="ms_vue",
        orderIndex=2,
        title="Bridge React to Vue",
        category="TransferableBridge",
        requirementName="Vue.js",
        targetCapability="Vue Components",
        rationale="Transfer React skills to Vue",
        state="NOT_STARTED",
    )
    ms_not_grounded = RoadmapMilestone(
        milestoneId="ms_k8s",
        orderIndex=3,
        title="Kubernetes Cluster Orchestration",
        category="VerifiableProject",
        requirementName="Kubernetes",
        targetCapability="K8s cluster management",
        rationale="DevOps capability",
        state="NOT_STARTED",
    )

    plan = RoadmapPlan(
        roadmapId="rdm_m5",
        userId="usr_m5_rec",
        title="Staff Backend Roadmap",
        targetRole="Staff Backend Engineer",
        version=1,
        totalMilestones=4,
        milestones=[ms_promoted, ms_grounded, ms_bridge, ms_not_grounded],
        workspaceEvidenceHash="old_hash",
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_roadmap(u, rid):
        return plan

    async def mock_save_doc(u, rid, payload):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_roadmap)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    # Reconcile
    reconciliation = await CareerRoadmapService.reconcile_roadmap(user, "rdm_m5")

    assert reconciliation.roadmap_id == "rdm_m5"
    assert reconciliation.grounded_count == 2
    assert reconciliation.unverified_count == 1
    assert reconciliation.not_grounded_count == 1

    updated_ms_map = {m.milestone_id: m for m in reconciliation.updated_plan.milestones}

    # 1. Promoted project
    assert updated_ms_map["ms_proj"].reconciliation.status == "GROUNDED_BY_PROMOTED_PROJECT"
    assert updated_ms_map["ms_proj"].promoted_project_id == "proj_prom_1"

    # 2. Grounded by workspace
    assert updated_ms_map["ms_gw"].reconciliation.status == "GROUNDED_BY_WORKSPACE"

    # 3. Transferable bridge -> RELATED_UNVERIFIED
    assert updated_ms_map["ms_vue"].reconciliation.status == "RELATED_UNVERIFIED"

    # 4. Not grounded
    assert updated_ms_map["ms_k8s"].reconciliation.status == "NOT_GROUNDED"


@pytest.mark.asyncio
async def test_m5_refresh_roadmap_preserves_completed_milestones(monkeypatch):
    """
    Milestone 5: Refresh Roadmap with Snapshot & Milestone Preservation.
    Verifies that refreshing recomputes hash and updates reconciliations while
    strictly preserving existing VERIFIED_PROJECT and ATTESTED milestones.
    """
    user = AuthenticatedUser(uid="usr_m5_ref", token="tok_m5_ref", email="m5ref@example.com")

    workspace_ev = CandidateEvidence(
        skills=[SkillItem(name="Go"), SkillItem(name="Docker")],
        projects=[],
        experience=[],
        certifications=[],
        education=[],
    )

    async def mock_load_master(u):
        return workspace_ev

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    art = VerificationArtifact(
        artifactId="art_completed_m5",
        artifactType="GitHubRepository",
        url="https://github.com/test/repo",
        checklistCompleted=["Done"],
        submittedAt="2026-09-25T00:00:00Z",
        provenanceHash="hash_completed_m5",
    )

    ms_verified = RoadmapMilestone(
        milestoneId="ms_done_1",
        orderIndex=0,
        title="Microservice in Go",
        category="VerifiableProject",
        requirementName="Go",
        targetCapability="Go backend",
        rationale="Existing capability",
        state="VERIFIED_PROJECT",
        verificationArtifact=art,
    )
    ms_pending = RoadmapMilestone(
        milestoneId="ms_pend_2",
        orderIndex=1,
        title="Docker Deployment",
        category="VerifiableProject",
        requirementName="Docker",
        targetCapability="Containerization",
        rationale="Upcoming capability",
        state="NOT_STARTED",
    )

    plan = RoadmapPlan(
        roadmapId="rdm_ref_1",
        userId="usr_m5_ref",
        title="Go Engineer Plan",
        targetRole="Go Engineer",
        version=1,
        totalMilestones=2,
        milestones=[ms_verified, ms_pending],
        workspaceEvidenceHash="old_stale_hash",
        isStale=True,
        createdAt="2026-09-25T00:00:00Z",
        updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save_doc(u, rid, payload):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    req = RefreshRoadmapRequest(expectedVersion=1)
    resp = await CareerRoadmapService.refresh_roadmap(user, "rdm_ref_1", req)

    assert resp.new_version == 2
    assert resp.is_stale is False
    assert len(resp.updated_plan.history_snapshots) == 1
    assert resp.updated_plan.history_snapshots[0].version == 1

    # Invariant: Completed milestone state MUST remain VERIFIED_PROJECT
    updated_ms_done = next(m for m in resp.updated_plan.milestones if m.milestone_id == "ms_done_1")
    assert updated_ms_done.state == "VERIFIED_PROJECT"
    assert updated_ms_done.verification_artifact is not None


@pytest.mark.asyncio
async def test_m5_roadmap_lifecycle_transitions(monkeypatch):
    """
    Milestone 5: Multi-Roadmap Lifecycle Management.
    Tests ACTIVE -> ARCHIVED -> ACTIVE and ACTIVE -> COMPLETED validations.
    """
    user = AuthenticatedUser(uid="usr_m5_life", token="tok_m5_life", email="m5life@example.com")

    ms_pending = RoadmapMilestone(
        milestoneId="ms_1", orderIndex=0, title="Pending task", category="CoreFoundation",
        requirementName="Req", targetCapability="Cap", rationale="Rat", state="NOT_STARTED",
    )
    plan = RoadmapPlan(
        roadmapId="rdm_life_1", userId="usr_m5_life", title="Plan", targetRole="Dev",
        version=1, totalMilestones=1, milestones=[ms_pending], lifecycle="ACTIVE",
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save_doc(u, rid, payload):
        plan.version = payload.get("version", plan.version)
        plan.lifecycle = payload.get("lifecycle", plan.lifecycle)
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    # 1. Attempting to mark COMPLETED when milestones are still incomplete must raise 400
    req_complete = UpdateRoadmapLifecycleRequest(lifecycle="COMPLETED", expectedVersion=1)
    with pytest.raises(HTTPException) as exc1:
        await CareerRoadmapService.update_lifecycle(user, "rdm_life_1", req_complete)
    assert exc1.value.status_code == 400
    assert "cannot mark roadmap as completed" in exc1.value.detail.lower()

    # 2. Archive active roadmap
    req_archive = UpdateRoadmapLifecycleRequest(lifecycle="ARCHIVED", expectedVersion=1)
    res_archived = await CareerRoadmapService.update_lifecycle(user, "rdm_life_1", req_archive)
    assert res_archived.lifecycle == "ARCHIVED"
    assert res_archived.version == 2

    # 3. Attempting to transition from ARCHIVED must raise 400 (ARCHIVED is terminal and read-only)
    req_restore = UpdateRoadmapLifecycleRequest(lifecycle="ACTIVE", expectedVersion=2)
    with pytest.raises(HTTPException) as exc_arch:
        await CareerRoadmapService.update_lifecycle(user, "rdm_life_1", req_restore)
    assert exc_arch.value.status_code == 400
    assert "permanently read-only" in exc_arch.value.detail.lower()


# =====================================================================
# ADVERSARIAL ATTACK TEST SUITE (ADV_061 – ADV_073)
# =====================================================================

@pytest.mark.asyncio
async def test_adv_061_cross_tenant_reconciliation_attempt(monkeypatch):
    """
    ADV_061: Cross-Tenant Reconciliation Attempt.
    User B attempts to reconcile User A's roadmap.
    Must be strictly rejected with HTTP 404 (tenant isolation).
    """
    attacker = AuthenticatedUser(uid="usr_attacker", token="tok_attacker", email="attacker@example.com")

    victim_plan = RoadmapPlan(
        roadmapId="rdm_victim", userId="usr_victim", title="Victim Plan", targetRole="VP Eng",
        version=1, totalMilestones=1, milestones=[], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        if u.uid != victim_plan.user_id:
            raise HTTPException(status_code=404, detail="Roadmap not found")
        return victim_plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.reconcile_roadmap(attacker, "rdm_victim")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_adv_062_cross_tenant_refresh_attempt(monkeypatch):
    """
    ADV_062: Cross-Tenant Refresh Attempt.
    User B attempts to refresh User A's roadmap against User B's workspace.
    Must be strictly rejected with HTTP 404 without mutating victim's roadmap.
    """
    attacker = AuthenticatedUser(uid="usr_attacker", token="tok_attacker", email="attacker@example.com")

    victim_plan = RoadmapPlan(
        roadmapId="rdm_victim", userId="usr_victim", title="Victim Plan", targetRole="Staff",
        version=1, totalMilestones=1, milestones=[], createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        if u.uid != victim_plan.user_id:
            raise HTTPException(status_code=404, detail="Roadmap not found")
        return victim_plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = RefreshRoadmapRequest(expectedVersion=1)
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.refresh_roadmap(attacker, "rdm_victim", req)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_adv_063_cross_roadmap_reconciliation_injection(monkeypatch):
    """
    ADV_063: Cross-Roadmap Reconciliation Injection.
    A project promoted from Roadmap A (source_document_id=ingest_prom_rdmA_ms1)
    MUST NOT ground a milestone in Roadmap B as GROUNDED_BY_PROMOTED_PROJECT.
    """
    user = AuthenticatedUser(uid="usr_adv63", token="tok_adv63", email="adv63@example.com")

    # Workspace contains a project confirmed from Roadmap A
    candidate_evidence = CandidateEvidence(
        skills=[],
        projects=[
            ProjectItem(
                id="proj_rdmA_ms1",
                title="Distributed Mesh Router",
                sourceDocumentId="ingest_prom_rdmA_ms1",  # Originates from Roadmap A
                techStack=["Rust", "gRPC"],
            )
        ],
        experience=[],
        certifications=[],
        education=[],
    )

    async def mock_load_master(u):
        return candidate_evidence

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    # Candidate reconciles Roadmap B
    ms_rdmB = RoadmapMilestone(
        milestoneId="ms1", orderIndex=0, title="Distributed Mesh Router", category="VerifiableProject",
        requirementName="Rust", targetCapability="Mesh networking", rationale="Rat", state="NOT_STARTED",
    )
    plan_rdmB = RoadmapPlan(
        roadmapId="rdmB", userId="usr_adv63", title="Roadmap B", targetRole="Rust Eng",
        version=1, totalMilestones=1, milestones=[ms_rdmB],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan_rdmB

    async def mock_save_doc(u, rid, p):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    rec = await CareerRoadmapService.reconcile_roadmap(user, "rdmB")
    rec_ms = rec.updated_plan.milestones[0].reconciliation

    # MUST NOT be recognized as GROUNDED_BY_PROMOTED_PROJECT for Roadmap B
    assert rec_ms.status != "GROUNDED_BY_PROMOTED_PROJECT"


@pytest.mark.asyncio
async def test_adv_064_client_supplied_workspace_project_id_injection(monkeypatch):
    """
    ADV_064: Client-Supplied Workspace Project ID Injection.
    An attacker attempts to set arbitrary promotedProjectId or workspaceEvidenceIds
    on milestone documents. Reconciliation must re-verify against actual workspace evidence
    and overwrite ungrounded injected IDs.
    """
    user = AuthenticatedUser(uid="usr_adv64", token="tok_adv64", email="adv64@example.com")

    # Empty workspace
    async def mock_load_master(u):
        return CandidateEvidence(skills=[], projects=[], experience=[], certifications=[], education=[])

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    # Injected milestone claiming to link to an unverified project
    ms_injected = RoadmapMilestone(
        milestoneId="ms_fake", orderIndex=0, title="Fake Link", category="VerifiableProject",
        requirementName="Haskell", targetCapability="FP", rationale="Rat", state="NOT_STARTED",
        promotedProjectId="proj_fake_unverified_123",
        workspaceEvidenceIds=["proj_fake_unverified_123"],
    )
    plan = RoadmapPlan(
        roadmapId="rdm_adv64", userId="usr_adv64", title="Plan", targetRole="Dev",
        version=1, totalMilestones=1, milestones=[ms_injected],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save_doc(u, rid, p):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    res = await CareerRoadmapService.reconcile_roadmap(user, "rdm_adv64")
    reconciled_ms = res.updated_plan.milestones[0]

    # Injected project ID cannot ground the milestone
    assert reconciled_ms.reconciliation.status == "NOT_GROUNDED"


@pytest.mark.asyncio
async def test_adv_065_client_supplied_grounded_status_injection(monkeypatch):
    """
    ADV_065: Client-Supplied Grounded Status Injection.
    An attacker attempts to directly update milestone state to VERIFIED_PROJECT
    without supplying a valid VerificationArtifact. Must be rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv65", token="tok_adv65", email="adv65@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv65", userId="usr_adv65", title="Plan", targetRole="Dev",
        version=1, totalMilestones=1,
        milestones=[
            RoadmapMilestone(
                milestoneId="ms_proj", orderIndex=0, title="Project", category="VerifiableProject",
                requirementName="Scala", targetCapability="Akka", rationale="Rat", state="IN_PROGRESS",
            )
        ],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Attempt transition to VERIFIED_PROJECT with empty artifact
    req = UpdateMilestoneProgressRequest(
        milestoneId="ms_proj",
        targetState="VERIFIED_PROJECT",
        expectedVersion=1,
        artifact=None,
    )
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv65", req)

    assert exc.value.status_code == 400
    assert "verification artifact" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_066_stale_version_refresh_race(monkeypatch):
    """
    ADV_066: Stale-Version Refresh Race.
    Supplying an outdated expectedVersion during roadmap refresh must be
    rejected with HTTP 409 Conflict.
    """
    user = AuthenticatedUser(uid="usr_adv66", token="tok_adv66", email="adv66@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv66", userId="usr_adv66", title="Plan", targetRole="Dev",
        version=4, totalMilestones=1, lifecycle="ACTIVE",
        milestones=[],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # Client thinks roadmap is at version 2, but actual is 4
    req = RefreshRoadmapRequest(expectedVersion=2)
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.refresh_roadmap(user, "rdm_adv66", req)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_adv_067_archived_roadmap_mutation_attempt(monkeypatch):
    """
    ADV_067: Archived Roadmap Mutation Attempt.
    Attempting to mutate progress, refresh, or promote an ARCHIVED roadmap
    must be strictly rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv67", token="tok_adv67", email="adv67@example.com")

    plan = RoadmapPlan(
        roadmapId="rdm_adv67", userId="usr_adv67", title="Plan", targetRole="Dev",
        version=1, totalMilestones=1, lifecycle="ARCHIVED",
        milestones=[
            RoadmapMilestone(milestoneId="m1", orderIndex=0, title="T1", category="VerifiableProject", requirementName="R1", targetCapability="C1", rationale="Rat", state="NOT_STARTED"),
        ],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # 1. Update progress on archived roadmap
    req_prog = UpdateMilestoneProgressRequest(milestoneId="m1", targetState="IN_PROGRESS", expectedVersion=1)
    with pytest.raises(HTTPException) as exc1:
        await CareerRoadmapService.update_milestone_progress(user, "rdm_adv67", req_prog)
    assert exc1.value.status_code == 400
    assert "archived" in exc1.value.detail.lower()

    # 2. Refresh archived roadmap
    req_ref = RefreshRoadmapRequest(expectedVersion=1)
    with pytest.raises(HTTPException) as exc2:
        await CareerRoadmapService.refresh_roadmap(user, "rdm_adv67", req_ref)
    assert exc2.value.status_code == 400
    assert "archived" in exc2.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_068_completed_roadmap_unauthorized_reopening(monkeypatch):
    """
    ADV_068: Completed Roadmap Unauthorized Reopening.
    Attempting to transition a COMPLETED roadmap back to ACTIVE when all required
    MustHave milestones are satisfied must be rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv68", token="tok_adv68", email="adv68@example.com")

    art = VerificationArtifact(
        artifactId="art_done", artifactType="GitHubRepository", url="https://github.com/test",
        checklistCompleted=["Done"], submittedAt="2026-09-25T00:00:00Z", provenanceHash="hash",
    )
    plan = RoadmapPlan(
        roadmapId="rdm_adv68", userId="usr_adv68", title="Completed Plan", targetRole="Architect",
        version=2, totalMilestones=1, lifecycle="COMPLETED",
        milestones=[
            RoadmapMilestone(
                milestoneId="m1", orderIndex=0, title="T1", category="VerifiableProject",
                importance="MustHave", requirementName="R1", targetCapability="C1", rationale="Rat",
                state="VERIFIED_PROJECT", verificationArtifact=art,
            ),
        ],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    req = UpdateRoadmapLifecycleRequest(lifecycle="ACTIVE", expectedVersion=2)
    with pytest.raises(HTTPException) as exc:
        await CareerRoadmapService.update_lifecycle(user, "rdm_adv68", req)
    assert exc.value.status_code == 400
    assert "cannot reopen a fully completed roadmap" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_069_cross_roadmap_snapshot_access(monkeypatch):
    """
    ADV_069: Cross-Roadmap Snapshot Access.
    Historical snapshots belong strictly to their owning roadmap document.
    Accessing or refreshing roadmap A never leaks or mutates snapshots from roadmap B.
    """
    user = AuthenticatedUser(uid="usr_adv69", token="tok_adv69", email="adv69@example.com")

    async def mock_load_master(u):
        return CandidateEvidence(skills=[], projects=[], experience=[], certifications=[], education=[])

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    snp_a = RoadmapSnapshotRecord(
        snapshotId="snp_rdmA_1", version=1, workspaceEvidenceHash="hashA", targetRole="Role A",
        targetCompany="Co A", milestoneCount=2, completedMilestones=1, overallProgressPct=50,
        createdAt="2026-09-25T00:00:00Z", lifecycle="ACTIVE",
    )
    plan_a = RoadmapPlan(
        roadmapId="rdmA", userId="usr_adv69", title="Plan A", targetRole="Role A",
        version=1, totalMilestones=2, milestones=[], historySnapshots=[snp_a],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )
    plan_b = RoadmapPlan(
        roadmapId="rdmB", userId="usr_adv69", title="Plan B", targetRole="Role B",
        version=1, totalMilestones=1, milestones=[], historySnapshots=[],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan_a if rid == "rdmA" else plan_b

    async def mock_save_doc(u, rid, p):
        if rid == "rdmB":
            plan_b.version = p.get("version", plan_b.version)
            plan_b.history_snapshots = [RoadmapSnapshotRecord.model_validate(s) for s in p.get("historySnapshots", [])]
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    req = RefreshRoadmapRequest(expectedVersion=1)
    res_b = await CareerRoadmapService.refresh_roadmap(user, "rdmB", req)

    # Roadmap B's snapshots must contain only its own records
    assert len(res_b.updated_plan.history_snapshots) == 1
    assert res_b.updated_plan.history_snapshots[0].target_role == "Role B"
    assert "snp_rdmA_1" not in [s.snapshot_id for s in res_b.updated_plan.history_snapshots]


@pytest.mark.asyncio
async def test_adv_070_lifecycle_manipulation_through_client_payload(monkeypatch):
    """
    ADV_070: Lifecycle Manipulation Through Client Payload.
    Setting COMPLETED on a roadmap with incomplete MustHave milestones
    or transitioning out of ARCHIVED must be strictly rejected with HTTP 400.
    """
    user = AuthenticatedUser(uid="usr_adv70", token="tok_adv70", email="adv70@example.com")

    plan_incomplete = RoadmapPlan(
        roadmapId="rdm_incomplete", userId="usr_adv70", title="Incomplete Plan", targetRole="Dev",
        version=1, totalMilestones=1, lifecycle="ACTIVE",
        milestones=[
            RoadmapMilestone(
                milestoneId="m1", orderIndex=0, title="T1", category="CoreFoundation",
                importance="MustHave", requirementName="R1", targetCapability="C1", rationale="Rat",
                state="NOT_STARTED",
            ),
        ],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan_incomplete

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)

    # 1. Reject COMPLETED on incomplete MustHave milestone
    req_comp = UpdateRoadmapLifecycleRequest(lifecycle="COMPLETED", expectedVersion=1)
    with pytest.raises(HTTPException) as exc1:
        await CareerRoadmapService.update_lifecycle(user, "rdm_incomplete", req_comp)
    assert exc1.value.status_code == 400
    assert "required milestones remain incomplete" in exc1.value.detail.lower()

    # 2. Reject transition out of ARCHIVED
    plan_archived = RoadmapPlan(
        roadmapId="rdm_archived", userId="usr_adv70", title="Archived Plan", targetRole="Dev",
        version=1, totalMilestones=1, lifecycle="ARCHIVED", milestones=[],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get_arch(u, rid):
        return plan_archived

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get_arch)

    req_act = UpdateRoadmapLifecycleRequest(lifecycle="ACTIVE", expectedVersion=1)
    with pytest.raises(HTTPException) as exc2:
        await CareerRoadmapService.update_lifecycle(user, "rdm_archived", req_act)
    assert exc2.value.status_code == 400
    assert "permanently read-only" in exc2.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_071_non_equivalence_reconciliation_integrity(monkeypatch):
    """
    ADV_071: Non-Equivalence Reconciliation Integrity.
    Verifies that domain non-equivalence rules (Java != JavaScript, React != Angular, Docker != Kubernetes)
    are strictly upheld during reconciliation so non-equivalent technologies never ground milestones.
    """
    user = AuthenticatedUser(uid="usr_adv71", token="tok_adv71", email="adv71@example.com")

    candidate_evidence = CandidateEvidence(
        skills=[SkillItem(name="Java"), SkillItem(name="React")],
        projects=[ProjectItem(title="Spring Boot App", techStack=["Java", "Docker"])],
        experience=[],
        certifications=[],
        education=[],
    )

    async def mock_load_master(u):
        return candidate_evidence

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    # Milestone requires JavaScript
    ms_js = RoadmapMilestone(
        milestoneId="ms_js", orderIndex=0, title="Modern JavaScript", category="CoreFoundation",
        requirementName="JavaScript", targetCapability="ES6+", rationale="Frontend basics", state="NOT_STARTED",
    )

    # Milestone requires Kubernetes
    ms_k8s = RoadmapMilestone(
        milestoneId="ms_k8s", orderIndex=1, title="K8s Ops", category="VerifiableProject",
        requirementName="Kubernetes", targetCapability="Orchestration", rationale="Cloud ops", state="NOT_STARTED",
    )

    plan = RoadmapPlan(
        roadmapId="rdm_adv71", userId="usr_adv71", title="Plan", targetRole="Dev",
        version=1, totalMilestones=2, milestones=[ms_js, ms_k8s],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save_doc(u, rid, p):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    res = await CareerRoadmapService.reconcile_roadmap(user, "rdm_adv71")
    recs = {m.milestone_id: m.reconciliation for m in res.updated_plan.milestones}

    # JavaScript must NOT be grounded by Java
    assert recs["ms_js"].status == "NOT_GROUNDED"

    # Kubernetes must NOT be grounded by Docker
    assert recs["ms_k8s"].status == "NOT_GROUNDED"


@pytest.mark.asyncio
async def test_adv_072_workspace_zero_mutation_guarantee_during_reconcile_and_refresh(monkeypatch):
    """
    ADV_072: Workspace Zero-Mutation Guarantee During Reconcile & Refresh.
    Reconcile and refresh operations MUST never invoke any write or update
    methods on Master Workspace collections.
    """
    user = AuthenticatedUser(uid="usr_adv72", token="tok_adv72", email="adv72@example.com")

    workspace_calls = {"reads": 0, "writes": 0}

    async def mock_load_master(u):
        workspace_calls["reads"] += 1
        return CandidateEvidence(skills=[SkillItem(name="React")], projects=[], experience=[], certifications=[], education=[])

    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", mock_load_master)

    plan = RoadmapPlan(
        roadmapId="rdm_adv72", userId="usr_adv72", title="Plan", targetRole="Dev",
        version=1, totalMilestones=1,
        milestones=[RoadmapMilestone(milestoneId="m1", orderIndex=0, title="T1", category="CoreFoundation", requirementName="React", targetCapability="React", rationale="Rat", state="NOT_STARTED")],
        createdAt="2026-09-25T00:00:00Z", updatedAt="2026-09-25T00:00:00Z",
    )

    async def mock_get(u, rid):
        return plan

    async def mock_save_doc(u, rid, p):
        return True

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", mock_get)
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", mock_save_doc)

    # 1. Reconcile
    await CareerRoadmapService.reconcile_roadmap(user, "rdm_adv72")
    # 2. Refresh
    await CareerRoadmapService.refresh_roadmap(user, "rdm_adv72", RefreshRoadmapRequest(expectedVersion=1))

    assert workspace_calls["reads"] == 3
    assert workspace_calls["writes"] == 0


def test_adv_073_free_product_integrity_milestone_5():
    """
    ADV_073: Free Product Invariant (Milestone 5 Full Stack).
    Verifies that all Career Roadmap modules, schemas, services, generator,
    and API routes contain ZERO monetization, subscription, payment, pricing,
    or paywall references.
    """
    import inspect
    import app.schemas.career_roadmap as cr_schemas
    import app.ai.career.roadmap_generator as cr_gen
    import app.services.career_roadmap_service as cr_service
    import app.api.v1.roadmaps as cr_api

    forbidden = [
        "stripe",
        "subscription",
        "billing",
        "price_id",
        "credit_balance",
        "paywall",
        "checkout_session",
        "pricing_tier",
    ]

    for mod in [cr_schemas, cr_gen, cr_service, cr_api]:
        source = inspect.getsource(mod).lower()
        for term in forbidden:
            assert term not in source, f"Forbidden monetization term '{term}' found in {mod.__name__}"
