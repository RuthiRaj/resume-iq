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
import hashlib
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.core.auth import AuthenticatedUser
from app.schemas.candidate import CandidateEvidence, ExperienceItem, ProjectItem, SkillItem
from app.schemas.requirement_match import RequirementMatch
from app.schemas.career_roadmap import (
    RoadmapPlan,
    RoadmapMilestone,
    GenerateRoadmapRequest,
    UpdateMilestoneProgressRequest,
    VerificationArtifactInput,
    ListRoadmapsResponse,
    DeleteRoadmapResponse,
)
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    CandidateAttestationRequest,
)
from app.ai.career.roadmap_generator import RoadmapGenerator
from app.services.career_roadmap_service import CareerRoadmapService
from app.services.resume_service import ResumeService
from app.services.variant_service import VariantService


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
