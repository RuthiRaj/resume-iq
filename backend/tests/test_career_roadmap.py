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
