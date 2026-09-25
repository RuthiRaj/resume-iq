"""
Pydantic v2 Schemas for Career Roadmap Engine (Phase 5.1 — Milestone 5)

Defines strongly-typed contracts for:
- Progressive capability roadmap plans (RoadmapPlan)
- Grounded milestones with explicit DAG dependency IDs (RoadmapMilestone)
- Deterministic progress state machine (MilestoneState)
- Auditable verification artifacts (VerificationArtifact)
- Multi-roadmap lifecycle (RoadmapLifecycle: ACTIVE, COMPLETED, ARCHIVED)
- Live Workspace Evidence Reconciliation (MilestoneReconciliation, ReconciliationStatus)
- Historical roadmap snapshots & evidence hashing (RoadmapSnapshotRecord)
- Reconcile and Refresh API contracts
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    ActionableLearningPath,
    ProjectBlueprint,
    CandidateAttestationRequest,
)

MilestoneCategory = Literal[
    "TransferableBridge",
    "CoreFoundation",
    "VerifiableProject",
    "DomainCertification",
]

MilestoneState = Literal[
    "NOT_STARTED",
    "IN_PROGRESS",
    "ARTIFACT_SUBMITTED",
    "VERIFIED_PROJECT",
    "ATTESTED",
]

ArtifactType = Literal[
    "GitHubRepository",
    "DeploymentUrl",
    "TechnicalWriteup",
    "AttestationRecord",
]

RoadmapLifecycle = Literal[
    "ACTIVE",
    "COMPLETED",
    "ARCHIVED",
]

ReconciliationStatus = Literal[
    "NOT_GROUNDED",
    "GROUNDED_BY_WORKSPACE",
    "GROUNDED_BY_PROMOTED_PROJECT",
    "RELATED_UNVERIFIED",
]


class TargetImportanceBreakdown(BaseModel):
    """Aggregate counts of target requirements classified by importance."""
    must_have_count: int = Field(default=0, ge=0, alias="mustHaveCount")
    preferred_count: int = Field(default=0, ge=0, alias="preferredCount")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class VerificationArtifact(BaseModel):
    """Auditable proof of project completion or attestation for a roadmap milestone."""
    artifact_id: str = Field(..., alias="artifactId", description="Unique artifact ID (art_...)")
    artifact_type: ArtifactType = Field(..., alias="artifactType")
    url: Optional[str] = Field(default=None, description="Repository or live URL")
    repository_branch: Optional[str] = Field(default=None, alias="repositoryBranch")
    checklist_completed: List[str] = Field(default_factory=list, alias="checklistCompleted")
    submitted_at: str = Field(..., alias="submittedAt")
    provenance_hash: str = Field(..., alias="provenanceHash", description="SHA-256 integrity hash")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class VerificationArtifactInput(BaseModel):
    """Payload provided by the user when submitting a verification artifact."""
    artifact_type: ArtifactType = Field(default="GitHubRepository", alias="artifactType")
    url: Optional[str] = Field(default=None, max_length=500)
    repository_branch: Optional[str] = Field(default=None, alias="repositoryBranch", max_length=100)
    checklist_completed: List[str] = Field(default_factory=list, alias="checklistCompleted")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class MilestoneReconciliation(BaseModel):
    """Authoritative result of reconciling a roadmap milestone with current Master Workspace evidence."""
    status: ReconciliationStatus
    matched_evidence_id: Optional[str] = Field(default=None, alias="matchedEvidenceId")
    matched_evidence_title: Optional[str] = Field(default=None, alias="matchedEvidenceTitle")
    matched_evidence_section: Optional[str] = Field(default=None, alias="matchedEvidenceSection")
    reconciliation_notes: str = Field(default="", alias="reconciliationNotes")
    promoted_project_id: Optional[str] = Field(default=None, alias="promotedProjectId")
    reconciled_at: str = Field(..., alias="reconciledAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapMilestone(BaseModel):
    """
    A single grounded milestone within a career capability roadmap.
    Traceable to prerequisite evidence, target requirements, DAG prerequisite milestones,
    promoted workspace projects, and live workspace evidence.
    """
    milestone_id: str = Field(..., alias="milestoneId", description="Unique milestone ID (ms_...)")
    order_index: int = Field(..., ge=0, alias="orderIndex")
    title: str
    category: MilestoneCategory
    requirement_name: str = Field(..., alias="requirementName")
    importance: Literal["MustHave", "Preferred", "Unspecified"] = Field(default="MustHave")
    target_capability: str = Field(..., alias="targetCapability")
    prerequisite_evidence_ids: List[str] = Field(default_factory=list, alias="prerequisiteEvidenceIds")
    prerequisite_milestone_ids: List[str] = Field(default_factory=list, alias="prerequisiteMilestoneIds")
    source_bridge_id: Optional[str] = Field(default=None, alias="sourceBridgeId")
    rationale: str
    estimated_weeks: int = Field(default=2, ge=1, le=52, alias="estimatedWeeks")
    learning_path: Optional[ActionableLearningPath] = Field(default=None, alias="learningPath")
    project_blueprint: Optional[ProjectBlueprint] = Field(default=None, alias="projectBlueprint")
    bridge_details: Optional[TransferableSkillBridge] = Field(default=None, alias="bridgeDetails")
    state: MilestoneState = Field(default="NOT_STARTED")
    verification_artifact: Optional[VerificationArtifact] = Field(default=None, alias="verificationArtifact")
    promoted_project_id: Optional[str] = Field(default=None, alias="promotedProjectId")
    workspace_evidence_ids: List[str] = Field(default_factory=list, alias="workspaceEvidenceIds")
    reconciliation: Optional[MilestoneReconciliation] = None
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapProvenance(BaseModel):
    """Cryptographic and contextual provenance tracking why and when the roadmap was generated."""
    source_variant_id: Optional[str] = Field(default=None, alias="sourceVariantId")
    source_analysis_score: Optional[int] = Field(default=None, alias="sourceAnalysisScore")
    generated_at: str = Field(..., alias="generatedAt")
    generator_version: str = Field(default="5.1.0", alias="generatorVersion")
    provenance_hash: str = Field(..., alias="provenanceHash")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapSnapshotRecord(BaseModel):
    """Immutable historical snapshot record captured during generation or refresh."""
    snapshot_id: str = Field(..., alias="snapshotId")
    version: int
    workspace_evidence_hash: str = Field(..., alias="workspaceEvidenceHash")
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    milestone_count: int = Field(..., alias="milestoneCount")
    completed_milestones: int = Field(..., alias="completedMilestones")
    overall_progress_pct: int = Field(..., alias="overallProgressPct")
    created_at: str = Field(..., alias="createdAt")
    lifecycle: RoadmapLifecycle = "ACTIVE"

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapPlan(BaseModel):
    """
    Persistent Career Roadmap Aggregate Document.
    Stored under users/{uid}/roadmaps/{roadmapId}.
    """
    roadmap_id: str = Field(..., alias="roadmapId")
    user_id: str = Field(..., alias="userId")
    title: str
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    target_level: Optional[str] = Field(default="", alias="targetLevel")
    source_variant_id: Optional[str] = Field(default=None, alias="sourceVariantId")
    version: int = Field(default=1, ge=1)
    lifecycle: RoadmapLifecycle = Field(default="ACTIVE")
    workspace_evidence_hash: Optional[str] = Field(default=None, alias="workspaceEvidenceHash")
    is_stale: bool = Field(default=False, alias="isStale")
    reconciled_at: Optional[str] = Field(default=None, alias="reconciledAt")
    total_milestones: int = Field(default=0, alias="totalMilestones")
    completed_milestones: int = Field(default=0, alias="completedMilestones")
    overall_progress_pct: int = Field(default=0, ge=0, le=100, alias="overallProgressPct")
    estimated_total_weeks: int = Field(default=0, ge=0, alias="estimatedTotalWeeks")
    target_importance_breakdown: TargetImportanceBreakdown = Field(
        default_factory=TargetImportanceBreakdown, alias="targetImportanceBreakdown"
    )
    next_recommended_milestone_id: Optional[str] = Field(default=None, alias="nextRecommendedMilestoneId")
    milestones: List[RoadmapMilestone] = Field(default_factory=list)
    history_snapshots: List[RoadmapSnapshotRecord] = Field(default_factory=list, alias="historySnapshots")
    provenance: Optional[RoadmapProvenance] = None
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class GenerateRoadmapRequest(BaseModel):
    """Request contract for deterministically synthesizing a career roadmap."""
    variant_id: Optional[str] = Field(default=None, alias="variantId", max_length=100)
    target_role: Optional[str] = Field(default=None, alias="targetRole", max_length=200)
    target_company: Optional[str] = Field(default="", alias="targetCompany", max_length=200)
    job_description: Optional[str] = Field(default="", alias="jobDescription", max_length=10000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class UpdateMilestoneProgressRequest(BaseModel):
    """Request contract to update milestone state, attach proof artifacts, or submit attestation."""
    milestone_id: str = Field(..., alias="milestoneId")
    target_state: MilestoneState = Field(..., alias="targetState")
    expected_version: int = Field(..., ge=1, alias="expectedVersion")
    artifact: Optional[VerificationArtifactInput] = None
    attestation: Optional[CandidateAttestationRequest] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ReconcileRoadmapResponse(BaseModel):
    """Response contract after deterministically reconciling roadmap milestones against Master Workspace."""
    roadmap_id: str = Field(..., alias="roadmapId")
    reconciled_at: str = Field(..., alias="reconciledAt")
    is_stale: bool = Field(..., alias="isStale")
    grounded_count: int = Field(default=0, alias="groundedCount")
    unverified_count: int = Field(default=0, alias="unverifiedCount")
    not_grounded_count: int = Field(default=0, alias="notGroundedCount")
    lifecycle: RoadmapLifecycle
    updated_plan: RoadmapPlan = Field(..., alias="updatedPlan")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RefreshRoadmapRequest(BaseModel):
    """Request contract for refreshing an active career roadmap against updated Master Workspace evidence."""
    expected_version: int = Field(..., ge=1, alias="expectedVersion")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RefreshRoadmapResponse(BaseModel):
    """Response contract after re-evaluating remaining gaps and updating roadmap snapshots."""
    roadmap_id: str = Field(..., alias="roadmapId")
    refreshed_at: str = Field(..., alias="refreshedAt")
    previous_version: int = Field(..., alias="previousVersion")
    new_version: int = Field(..., alias="newVersion")
    is_stale: bool = Field(..., alias="isStale")
    completed_milestones_preserved: int = Field(..., alias="completedMilestonesPreserved")
    remaining_milestones_reconciled: int = Field(..., alias="remainingMilestonesReconciled")
    lifecycle: RoadmapLifecycle
    updated_plan: RoadmapPlan = Field(..., alias="updatedPlan")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class UpdateRoadmapLifecycleRequest(BaseModel):
    """Request contract for transitioning roadmap lifecycle (e.g. ARCHIVED / ACTIVE)."""
    lifecycle: RoadmapLifecycle
    expected_version: int = Field(..., ge=1, alias="expectedVersion")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ListRoadmapsResponse(BaseModel):
    """Response contract listing all active roadmaps for the authenticated candidate."""
    roadmaps: List[RoadmapPlan] = Field(default_factory=list)
    total: int = 0

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class DeleteRoadmapResponse(BaseModel):
    """Response contract after deleting a roadmap plan."""
    success: bool = True
    roadmap_id: str = Field(..., alias="roadmapId")
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
