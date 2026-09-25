"""
Career Roadmap Service (Phase 5.1 — Milestone 5)

Orchestrates:
1. Deterministic Career Roadmap Generation with DAG Dependencies & Evidence Hashing
2. Roadmap Persistence & Retrieval under users/{uid}/roadmaps/{roadmapId}
3. Dependency-Aware Milestone Progression & Prerequisite Validation
4. Aggregate Recalculation (Progress, Time, Next Recommended Milestone)
5. Multi-Roadmap Lifecycle Management (ACTIVE, COMPLETED, ARCHIVED)
6. Live Master Workspace Evidence Reconciliation & Promoted Project Linkage
7. Deterministic Roadmap Refresh / Re-Analysis with Historical Snapshot Preservation
8. Strict Optimistic Concurrency & Multi-Roadmap Tenant Isolation
9. Zero Root Evidence Contamination (Roadmap is derived planning intelligence only)
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from fastapi import HTTPException, status
from app.core.logging import get_logger

logger = get_logger("app.services.career_roadmap")

from app.core.auth import AuthenticatedUser
from app.schemas.career_roadmap import (
    RoadmapPlan,
    RoadmapMilestone,
    VerificationArtifact,
    GenerateRoadmapRequest,
    UpdateMilestoneProgressRequest,
    ListRoadmapsResponse,
    DeleteRoadmapResponse,
    MilestoneState,
    RoadmapLifecycle,
    ReconciliationStatus,
    MilestoneReconciliation,
    RoadmapSnapshotRecord,
    ReconcileRoadmapResponse,
    RefreshRoadmapRequest,
    RefreshRoadmapResponse,
    UpdateRoadmapLifecycleRequest,
)
from app.schemas.requirement_match import RequirementMatch
from app.schemas.candidate import CandidateEvidence, ProjectItem, SkillItem
from app.schemas.profile import ProfileDTO
from app.schemas.ingestion import IngestionDraft, ParsedCandidateProfile
from app.services.resume_service import (
    load_master_profile,
    get_http_client,
    _get_firestore_base_url,
    _decode_firestore_doc,
    _encode_firestore_fields,
    _validate_safe_id,
)
from app.services.variant_service import VariantService
from app.services.career_intelligence_service import CareerIntelligenceService
from app.services.ingestion_service import IngestionService
from app.ai.skills import normalize_skill_name
from app.ai.career.roadmap_generator import RoadmapGenerator


# Allowed State Transition Map
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "NOT_STARTED": {"IN_PROGRESS", "ATTESTED"},
    "IN_PROGRESS": {"ARTIFACT_SUBMITTED", "VERIFIED_PROJECT", "ATTESTED"},
    "ARTIFACT_SUBMITTED": {"VERIFIED_PROJECT", "IN_PROGRESS"},
    "VERIFIED_PROJECT": set(),  # Terminal state
    "ATTESTED": set(),          # Terminal state
}


class CareerRoadmapService:
    """
    Service layer for Career Roadmap Engine.
    Guarantees strict tenant isolation, DAG dependency gating, evidence non-contamination,
    live workspace reconciliation, and optimistic concurrency.
    """

    @classmethod
    async def generate_roadmap(
        cls,
        user: AuthenticatedUser,
        req: GenerateRoadmapRequest,
    ) -> RoadmapPlan:
        """
        Synthesizes a new career roadmap deterministically and stores it under users/{uid}/roadmaps.
        """
        candidate_evidence: CandidateEvidence
        target_role: str
        target_company: str = req.target_company or ""
        missing_reqs: List[RequirementMatch] = []
        source_variant_id: Optional[str] = req.variant_id
        source_analysis_score: Optional[int] = None

        if req.variant_id:
            variant = await VariantService.get_targeted_variant(user, req.variant_id)
            candidate_evidence = variant.snapshot
            target_role = req.target_role or variant.target_role
            target_company = req.target_company or variant.target_company or ""
            source_analysis_score = variant.current_score or variant.baseline_score
            matches = variant.current_matches or variant.baseline_matches or []
            missing_reqs = [m for m in matches if m.match_status in ("Missing", "PartialMatch")]
        else:
            if not req.target_role or not req.target_role.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Target role is required when generating a roadmap without a variantId.",
                )
            target_role = req.target_role.strip()
            candidate_evidence = await load_master_profile(user)

        roadmap = RoadmapGenerator.generate_roadmap(
            user_id=user.uid,
            candidate_evidence=candidate_evidence,
            target_role=target_role,
            target_company=target_company,
            missing_requirements=missing_reqs,
            source_variant_id=source_variant_id,
            source_analysis_score=source_analysis_score,
        )

        # Persist to Firestore: users/{uid}/roadmaps/{roadmapId}
        doc_payload = roadmap.model_dump(by_alias=True)
        saved = await cls._save_roadmap_doc(user, roadmap.roadmap_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist career roadmap to database.",
            )

        return roadmap

    @classmethod
    async def get_roadmap(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
    ) -> RoadmapPlan:
        """Loads and strongly types a career roadmap owned by the authenticated candidate."""
        _validate_safe_id(roadmap_id, "roadmap_id")
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/roadmaps/{roadmap_id}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        try:
            res = await client.get(doc_url, headers=headers)
            if res.status_code == 200:
                doc_data = _decode_firestore_doc(res.json())
                return RoadmapPlan.model_validate(doc_data)
            elif res.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Career roadmap '{roadmap_id}' not found.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error accessing roadmap store (HTTP {res.status_code}).",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve career roadmap: {str(e)}",
            )

    @classmethod
    async def list_roadmaps(
        cls,
        user: AuthenticatedUser,
        target_role: Optional[str] = None,
        active_only: Optional[bool] = None,
        lifecycle: Optional[str] = None,
    ) -> ListRoadmapsResponse:
        """Lists all career roadmaps belonging to the authenticated candidate with optional filters."""
        subcol_url = f"{_get_firestore_base_url()}/users/{user.uid}/roadmaps"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        roadmaps: List[RoadmapPlan] = []
        try:
            res = await client.get(subcol_url, headers=headers)
            if res.status_code == 200:
                docs = res.json().get("documents", [])
                for d in docs:
                    decoded = _decode_firestore_doc(d)
                    try:
                        plan = RoadmapPlan.model_validate(decoded)
                        if target_role and target_role.strip().lower() not in plan.target_role.lower():
                            continue
                        if active_only and (plan.overall_progress_pct >= 100 or plan.lifecycle != "ACTIVE"):
                            continue
                        if lifecycle and plan.lifecycle != lifecycle:
                            continue
                        roadmaps.append(plan)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(
                f"Failed to list roadmaps: {str(e)}",
                extra={"event": "firestore_read_error", "error_type": type(e).__name__, "component": "career_roadmap_service"},
            )

        return ListRoadmapsResponse(
            roadmaps=roadmaps,
            total=len(roadmaps),
        )

    @classmethod
    async def update_milestone_progress(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
        req: UpdateMilestoneProgressRequest,
    ) -> RoadmapPlan:
        """
        Updates milestone progression state, validates state transitions and DAG prerequisite completion,
        attaches verification artifacts or attestation records, and updates aggregates with optimistic concurrency.
        """
        roadmap = await cls.get_roadmap(user, roadmap_id)

        # Lifecycle Guard: Cannot mutate milestones in ARCHIVED or COMPLETED roadmaps
        if roadmap.lifecycle == "ARCHIVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify milestone progression in an ARCHIVED roadmap.",
            )
        if roadmap.lifecycle == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify milestone progression in a COMPLETED roadmap.",
            )

        # 1. Optimistic Concurrency Check
        if roadmap.version != req.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrency conflict: roadmap is at version {roadmap.version}, but expected version was {req.expected_version}.",
            )

        # 2. Locate Target Milestone
        target_ms: Optional[RoadmapMilestone] = None
        ms_map: Dict[str, RoadmapMilestone] = {}
        for ms in roadmap.milestones:
            ms_map[ms.milestone_id] = ms
            if ms.milestone_id == req.milestone_id:
                target_ms = ms

        if not target_ms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Milestone '{req.milestone_id}' not found in roadmap '{roadmap_id}'.",
            )

        current_state = target_ms.state
        target_state = req.target_state

        # 3. State Transition Validation
        if target_state != current_state:
            allowed = VALID_TRANSITIONS.get(current_state, set())
            if target_state not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid milestone state transition from '{current_state}' to '{target_state}'.",
                )

        # 4. Dependency DAG Progression Gating
        if target_state in ("IN_PROGRESS", "ARTIFACT_SUBMITTED", "VERIFIED_PROJECT"):
            for prereq_id in target_ms.prerequisite_milestone_ids:
                prereq_ms = ms_map.get(prereq_id)
                if not prereq_ms:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Milestone '{target_ms.title}' references non-existent prerequisite milestone '{prereq_id}'.",
                    )
                if prereq_ms.state not in ("VERIFIED_PROJECT", "ATTESTED"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot transition milestone '{target_ms.title}' to '{target_state}': prerequisite milestone '{prereq_ms.title}' ({prereq_ms.milestone_id}) is not completed (current state: {prereq_ms.state}).",
                    )

        now_iso = datetime.now(timezone.utc).isoformat()

        # 5. Handle State-Specific Progression & Security Validation
        if target_state == "IN_PROGRESS":
            if not target_ms.started_at:
                target_ms.started_at = now_iso

        elif target_state == "ARTIFACT_SUBMITTED":
            if not req.artifact:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Submitting an artifact requires artifact details (url or completed checklist).",
                )
            if not req.artifact.url and not req.artifact.checklist_completed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification artifact must have a valid URL or at least one completed checklist item.",
                )

            art_id = f"art_{uuid.uuid4().hex[:10]}"
            prov_str = f"{user.uid}:{roadmap_id}:{target_ms.milestone_id}:{req.artifact.url or ''}:{now_iso}"
            prov_hash = hashlib.sha256(prov_str.encode("utf-8")).hexdigest()

            target_ms.verification_artifact = VerificationArtifact(
                artifactId=art_id,
                artifactType=req.artifact.artifact_type,
                url=req.artifact.url,
                repositoryBranch=req.artifact.repository_branch,
                checklistCompleted=req.artifact.checklist_completed,
                submittedAt=now_iso,
                provenanceHash=prov_hash,
            )

        elif target_state == "VERIFIED_PROJECT":
            if not req.artifact and not target_ms.verification_artifact:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot verify project milestone without submitting a valid verification artifact.",
                )

            if req.artifact:
                if not req.artifact.url and not req.artifact.checklist_completed:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Verification artifact cannot be empty.",
                    )
                art_id = f"art_{uuid.uuid4().hex[:10]}"
                prov_str = f"{user.uid}:{roadmap_id}:{target_ms.milestone_id}:{req.artifact.url or ''}:{now_iso}"
                prov_hash = hashlib.sha256(prov_str.encode("utf-8")).hexdigest()

                target_ms.verification_artifact = VerificationArtifact(
                    artifactId=art_id,
                    artifactType=req.artifact.artifact_type,
                    url=req.artifact.url,
                    repositoryBranch=req.artifact.repository_branch,
                    checklistCompleted=req.artifact.checklist_completed,
                    submittedAt=now_iso,
                    provenanceHash=prov_hash,
                )

            target_ms.completed_at = now_iso

        elif target_state == "ATTESTED":
            if target_ms.category != "TransferableBridge":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Milestones of category '{target_ms.category}' cannot be ATTESTED. Use VERIFIED_PROJECT instead.",
                )

            if not req.attestation:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Direct transition to ATTESTED without invoking authoritative Phase 5.0 CandidateAttestationRequest is not permitted.",
                )

            attest_res = await CareerIntelligenceService.process_attestation(user, req.attestation)

            art_id = attest_res.attestation_id
            prov_str = f"{user.uid}:{roadmap_id}:{target_ms.milestone_id}:{art_id}:{now_iso}"
            prov_hash = hashlib.sha256(prov_str.encode("utf-8")).hexdigest()

            target_ms.verification_artifact = VerificationArtifact(
                artifactId=art_id,
                artifactType="AttestationRecord",
                url=None,
                repositoryBranch=None,
                checklistCompleted=[f"Attested via Phase 5.0: {req.attestation.attested_actions[:60]}..."],
                submittedAt=now_iso,
                provenanceHash=prov_hash,
            )
            target_ms.completed_at = now_iso

        # Apply State
        target_ms.state = target_state

        # 6. Recompute Aggregates & Bump Version
        completed_count = sum(
            1 for m in roadmap.milestones if m.state in ("VERIFIED_PROJECT", "ATTESTED")
        )
        total_count = len(roadmap.milestones)
        roadmap.completed_milestones = completed_count
        roadmap.overall_progress_pct = int((completed_count / total_count) * 100) if total_count > 0 else 0
        roadmap.next_recommended_milestone_id = RoadmapGenerator.calculate_next_recommended_milestone_id(roadmap.milestones)

        # Lifecycle completion check: if all milestones are completed, auto-mark COMPLETED
        if completed_count == total_count and total_count > 0:
            roadmap.lifecycle = "COMPLETED"

        roadmap.version += 1
        roadmap.updated_at = now_iso

        # 7. Persist Updated Roadmap
        doc_payload = roadmap.model_dump(by_alias=True)
        saved = await cls._save_roadmap_doc(user, roadmap_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist updated roadmap state to database.",
            )

        return roadmap

    @classmethod
    async def reconcile_roadmap(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
    ) -> ReconcileRoadmapResponse:
        """
        Deterministically reconciles an existing roadmap against current Master Workspace evidence:
        - Loads Master Workspace items (projects, skills, experience, certifications).
        - Computes current canonical evidence hash to detect staleness.
        - Checks each milestone's requirement against live Workspace evidence without mutating Workspace.
        - Identifies promoted projects and links them to the milestone.
        - Re-evaluates lifecycle completion.
        """
        _validate_safe_id(roadmap_id, "roadmap_id")
        roadmap = await cls.get_roadmap(user, roadmap_id)
        master_evidence = await load_master_profile(user)

        now_iso = datetime.now(timezone.utc).isoformat()
        current_hash = RoadmapGenerator.compute_workspace_evidence_hash(master_evidence)
        is_stale = bool(roadmap.workspace_evidence_hash and roadmap.workspace_evidence_hash != current_hash)

        # Index Master Workspace Items
        workspace_skills = {
            normalize_skill_name(s.name).lower(): s
            for s in (master_evidence.skills or [])
            if s.name and s.name.strip()
        }

        workspace_projects_by_doc_id: Dict[str, ProjectItem] = {}
        for p in (master_evidence.projects or []):
            if p.source_document_id:
                workspace_projects_by_doc_id[p.source_document_id] = p

        grounded_count = 0
        unverified_count = 0
        not_grounded_count = 0

        for m in roadmap.milestones:
            req_norm = normalize_skill_name(m.requirement_name).lower()
            expected_doc_id = f"ingest_prom_{roadmap_id}_{m.milestone_id}"

            # 1. Check for Promoted Project Linkage (Authoritative Ingestion Source ID Only)
            matched_proj = workspace_projects_by_doc_id.get(expected_doc_id)

            if matched_proj:
                m.promoted_project_id = matched_proj.id or f"proj_{m.milestone_id[:12]}"
                if matched_proj.id and matched_proj.id not in m.workspace_evidence_ids:
                    m.workspace_evidence_ids.append(matched_proj.id)
                m.reconciliation = MilestoneReconciliation(
                    status="GROUNDED_BY_PROMOTED_PROJECT",
                    matchedEvidenceId=matched_proj.id or m.promoted_project_id,
                    matchedEvidenceTitle=matched_proj.title,
                    matchedEvidenceSection="Project",
                    reconciliationNotes="Grounded by verified and confirmed Roadmap Project in Master Workspace.",
                    promotedProjectId=m.promoted_project_id,
                    reconciledAt=now_iso,
                )
                grounded_count += 1
                continue

            # 2. Check for Master Workspace Skill / Experience / Certification
            if req_norm in workspace_skills:
                sk = workspace_skills[req_norm]
                sk_id = sk.id or sk.name
                if sk_id not in m.workspace_evidence_ids:
                    m.workspace_evidence_ids.append(sk_id)
                m.reconciliation = MilestoneReconciliation(
                    status="GROUNDED_BY_WORKSPACE",
                    matchedEvidenceId=sk_id,
                    matchedEvidenceTitle=sk.name,
                    matchedEvidenceSection="Skill",
                    reconciliationNotes=f"Grounded by verified skill '{sk.name}' in Master Workspace.",
                    promotedProjectId=m.promoted_project_id,
                    reconciledAt=now_iso,
                )
                grounded_count += 1
                continue

            # Check if any workspace project has this skill in tech_stack
            found_proj = next(
                (p for p in (master_evidence.projects or []) if any(normalize_skill_name(t).lower() == req_norm for t in (p.tech_stack or []))),
                None,
            )
            if found_proj:
                pid = found_proj.id or found_proj.title
                if pid not in m.workspace_evidence_ids:
                    m.workspace_evidence_ids.append(pid)
                m.reconciliation = MilestoneReconciliation(
                    status="GROUNDED_BY_WORKSPACE",
                    matchedEvidenceId=pid,
                    matchedEvidenceTitle=found_proj.title,
                    matchedEvidenceSection="Project",
                    reconciliationNotes=f"Grounded by Master Workspace project '{found_proj.title}'.",
                    promotedProjectId=m.promoted_project_id,
                    reconciledAt=now_iso,
                )
                grounded_count += 1
                continue

            # Check if any workspace experience explicitly demonstrates this technology
            found_exp = next(
                (e for e in (master_evidence.experience or []) if any(normalize_skill_name(t).lower() == req_norm for t in (e.technologies or []))),
                None,
            )
            if found_exp:
                eid = found_exp.id or found_exp.company
                if eid not in m.workspace_evidence_ids:
                    m.workspace_evidence_ids.append(eid)
                m.reconciliation = MilestoneReconciliation(
                    status="GROUNDED_BY_WORKSPACE",
                    matchedEvidenceId=eid,
                    matchedEvidenceTitle=f"{found_exp.role} @ {found_exp.company}",
                    matchedEvidenceSection="Experience",
                    reconciliationNotes=f"Grounded by Master Workspace experience at {found_exp.company}.",
                    promotedProjectId=m.promoted_project_id,
                    reconciledAt=now_iso,
                )
                grounded_count += 1
                continue

            # Check if any workspace certification matches
            found_cert = next(
                (c for c in (master_evidence.certifications or []) if normalize_skill_name(getattr(c, "title", None) or getattr(c, "name", "")).lower() == req_norm),
                None,
            )
            if found_cert:
                cid = found_cert.id or getattr(found_cert, "title", None) or getattr(found_cert, "name", "Certification")
                if cid not in m.workspace_evidence_ids:
                    m.workspace_evidence_ids.append(cid)
                m.reconciliation = MilestoneReconciliation(
                    status="GROUNDED_BY_WORKSPACE",
                    matchedEvidenceId=cid,
                    matchedEvidenceTitle=getattr(found_cert, "title", None) or getattr(found_cert, "name", "Certification"),
                    matchedEvidenceSection="Certification",
                    reconciliationNotes=f"Grounded by Master Workspace certification '{getattr(found_cert, 'title', None) or getattr(found_cert, 'name', 'Certification')}'.",
                    promotedProjectId=m.promoted_project_id,
                    reconciledAt=now_iso,
                )
                grounded_count += 1
                continue

            # 3. Check for Attested / TransferableBridge
            if m.category == "TransferableBridge":
                if m.state == "ATTESTED":
                    m.reconciliation = MilestoneReconciliation(
                        status="GROUNDED_BY_WORKSPACE",
                        matchedEvidenceId=m.source_bridge_id,
                        matchedEvidenceTitle=m.title,
                        matchedEvidenceSection="Attestation",
                        reconciliationNotes="Grounded by candidate transferable skill attestation.",
                        promotedProjectId=None,
                        reconciledAt=now_iso,
                    )
                    grounded_count += 1
                else:
                    m.reconciliation = MilestoneReconciliation(
                        status="RELATED_UNVERIFIED",
                        matchedEvidenceId=m.source_bridge_id,
                        matchedEvidenceTitle=m.title,
                        matchedEvidenceSection="TransferableBridge",
                        reconciliationNotes="Transferable skill identified; candidate attestation required.",
                        promotedProjectId=None,
                        reconciledAt=now_iso,
                    )
                    unverified_count += 1
                continue

            # 4. Not Grounded
            m.reconciliation = MilestoneReconciliation(
                status="NOT_GROUNDED",
                matchedEvidenceId=None,
                matchedEvidenceTitle=None,
                matchedEvidenceSection=None,
                reconciliationNotes="Requirement is not yet grounded in Master Workspace evidence.",
                promotedProjectId=m.promoted_project_id,
                reconciledAt=now_iso,
            )
            not_grounded_count += 1

        # Check Lifecycle Completion based on MustHave requirements
        must_have_ms = [m for m in roadmap.milestones if getattr(m, "importance", "MustHave") == "MustHave"]
        if not must_have_ms:
            must_have_ms = roadmap.milestones

        must_have_satisfied = sum(
            1 for m in must_have_ms
            if m.state in ("VERIFIED_PROJECT", "ATTESTED")
            or (m.reconciliation and m.reconciliation.status in ("GROUNDED_BY_PROMOTED_PROJECT", "GROUNDED_BY_WORKSPACE"))
        )
        if must_have_satisfied == len(must_have_ms) and len(must_have_ms) > 0 and roadmap.lifecycle == "ACTIVE":
            roadmap.lifecycle = "COMPLETED"

        roadmap.reconciled_at = now_iso
        roadmap.is_stale = is_stale
        roadmap.updated_at = now_iso

        # Persist updated reconciliation metadata to roadmap document
        doc_payload = roadmap.model_dump(by_alias=True)
        await cls._save_roadmap_doc(user, roadmap_id, doc_payload)

        return ReconcileRoadmapResponse(
            roadmapId=roadmap_id,
            reconciledAt=now_iso,
            isStale=is_stale,
            groundedCount=grounded_count,
            unverifiedCount=unverified_count,
            notGroundedCount=not_grounded_count,
            lifecycle=roadmap.lifecycle,
            updatedPlan=roadmap,
        )

    @classmethod
    async def refresh_roadmap(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
        req: RefreshRoadmapRequest,
    ) -> RefreshRoadmapResponse:
        """
        Deterministically refreshes an active career roadmap against updated Master Workspace evidence:
        1. Verifies roadmap ownership and active lifecycle state (ARCHIVED roadmaps cannot be refreshed).
        2. Protects against stale concurrency via expected_version.
        3. Preserves all completed/verified milestones and their historical artifacts/timestamps.
        4. Saves an immutable historical snapshot record before refresh.
        5. Re-reconciles remaining milestones against current Master Workspace evidence.
        6. Updates workspace_evidence_hash and clears stale flag.
        """
        _validate_safe_id(roadmap_id, "roadmap_id")
        roadmap = await cls.get_roadmap(user, roadmap_id)

        if roadmap.lifecycle == "ARCHIVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot refresh an ARCHIVED career roadmap.",
            )

        if roadmap.version != req.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrency conflict: roadmap is at version {roadmap.version}, but expected version was {req.expected_version}.",
            )

        master_evidence = await load_master_profile(user)
        now_iso = datetime.now(timezone.utc).isoformat()
        current_hash = RoadmapGenerator.compute_workspace_evidence_hash(master_evidence)

        # 1. Capture Immutable Snapshot of Pre-Refresh State
        snapshot_record = RoadmapSnapshotRecord(
            snapshotId=f"snp_{uuid.uuid4().hex[:10]}",
            version=roadmap.version,
            workspaceEvidenceHash=roadmap.workspace_evidence_hash or current_hash,
            targetRole=roadmap.target_role,
            targetCompany=roadmap.target_company or "",
            milestoneCount=len(roadmap.milestones),
            completedMilestones=roadmap.completed_milestones,
            overallProgressPct=roadmap.overall_progress_pct,
            createdAt=now_iso,
            lifecycle=roadmap.lifecycle,
        )
        updated_history = list(roadmap.history_snapshots)
        updated_history.append(snapshot_record)
        # Bounded retention: Keep at most 10 most recent historical snapshots to avoid Firestore 1MB document limit
        if len(updated_history) > 10:
            updated_history = updated_history[-10:]

        # 2. Count Preserved Historical Milestones
        completed_preserved = sum(
            1 for m in roadmap.milestones if m.state in ("VERIFIED_PROJECT", "ATTESTED")
        )

        # 3. Perform Live Reconciliation against Master Workspace
        reconcile_res = await cls.reconcile_roadmap(user, roadmap_id)
        roadmap = reconcile_res.updated_plan
        roadmap.history_snapshots = updated_history

        remaining_reconciled = len(roadmap.milestones) - completed_preserved
        prev_v = roadmap.version

        # 4. Bump Version & Update Snapshot Metadata
        roadmap.workspace_evidence_hash = current_hash
        roadmap.is_stale = False
        roadmap.version = prev_v + 1
        roadmap.updated_at = now_iso

        # 5. Persist Refreshed Plan
        doc_payload = roadmap.model_dump(by_alias=True)
        saved = await cls._save_roadmap_doc(user, roadmap_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist refreshed roadmap to database.",
            )

        return RefreshRoadmapResponse(
            roadmapId=roadmap_id,
            refreshedAt=now_iso,
            previousVersion=prev_v,
            newVersion=roadmap.version,
            isStale=False,
            completedMilestonesPreserved=completed_preserved,
            remainingMilestonesReconciled=remaining_reconciled,
            lifecycle=roadmap.lifecycle,
            updatedPlan=roadmap,
        )

    @classmethod
    async def update_lifecycle(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
        req: UpdateRoadmapLifecycleRequest,
    ) -> RoadmapPlan:
        """
        Transitions a roadmap's lifecycle state (ACTIVE, COMPLETED, ARCHIVED) with optimistic concurrency.
        """
        _validate_safe_id(roadmap_id, "roadmap_id")
        roadmap = await cls.get_roadmap(user, roadmap_id)

        if roadmap.version != req.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrency conflict: roadmap is at version {roadmap.version}, but expected version was {req.expected_version}.",
            )

        # Lifecycle Invariant: ARCHIVED is terminal and read-only
        if roadmap.lifecycle == "ARCHIVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change lifecycle of an ARCHIVED career roadmap. Archived roadmaps are permanently read-only.",
            )

        # Security Rule (ADV_068): Completed roadmaps cannot be arbitrarily reopened if completion criteria are met
        if roadmap.lifecycle == "COMPLETED" and req.lifecycle == "ACTIVE":
            must_have_ms = [m for m in roadmap.milestones if getattr(m, "importance", "MustHave") == "MustHave"]
            if not must_have_ms:
                must_have_ms = roadmap.milestones
            all_must_have_done = all(
                m.state in ("VERIFIED_PROJECT", "ATTESTED")
                or (m.reconciliation and m.reconciliation.status in ("GROUNDED_BY_PROMOTED_PROJECT", "GROUNDED_BY_WORKSPACE"))
                for m in must_have_ms
            )
            if all_must_have_done:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reopen a fully COMPLETED roadmap. All required milestones are verified.",
                )

        # Security Rule (ADV_070): Cannot set COMPLETED if MustHave milestones remain incomplete
        if req.lifecycle == "COMPLETED":
            must_have_ms = [m for m in roadmap.milestones if getattr(m, "importance", "MustHave") == "MustHave"]
            if not must_have_ms:
                must_have_ms = roadmap.milestones
            incomplete = [
                m for m in must_have_ms
                if m.state not in ("VERIFIED_PROJECT", "ATTESTED")
                and (not m.reconciliation or m.reconciliation.status not in ("GROUNDED_BY_PROMOTED_PROJECT", "GROUNDED_BY_WORKSPACE"))
            ]
            if incomplete:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot mark roadmap as COMPLETED: {len(incomplete)} required milestones remain incomplete.",
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        roadmap.lifecycle = req.lifecycle
        roadmap.version += 1
        roadmap.updated_at = now_iso

        doc_payload = roadmap.model_dump(by_alias=True)
        saved = await cls._save_roadmap_doc(user, roadmap_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist roadmap lifecycle transition to database.",
            )

        return roadmap

    @classmethod
    async def delete_roadmap(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
    ) -> DeleteRoadmapResponse:
        """Deletes a career roadmap owned by the authenticated candidate."""
        _validate_safe_id(roadmap_id, "roadmap_id")
        # Ensure roadmap exists and belongs to candidate
        await cls.get_roadmap(user, roadmap_id)

        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/roadmaps/{roadmap_id}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        try:
            res = await client.delete(doc_url, headers=headers)
            if res.status_code in (200, 204):
                return DeleteRoadmapResponse(
                    success=True,
                    roadmap_id=roadmap_id,
                    message=f"Career roadmap '{roadmap_id}' successfully deleted.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete career roadmap from database.",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting career roadmap: {str(e)}",
            )

    @classmethod
    async def create_promotion_draft(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
        milestone_id: str,
    ) -> IngestionDraft:
        """
        Synthesizes a reviewable IngestionDraft from a completed roadmap milestone:
        1. Loads the roadmap strictly scoped under the authenticated user.
        2. Validates milestone existence and eligibility (must be VERIFIED_PROJECT with valid artifact).
        3. Rejects TransferableBridge / ATTESTED (which belong to Phase 5.0 attestation flow).
        4. Deterministically constructs an IngestionDraft with ProjectItem and SkillItems.
        5. Persists draft under users/{uid}/ingestions/{ingestion_id} with idempotency.
        6. Updates milestone with promoted_project_id linkage.
        7. Leaves root workspace evidence collections 100% UNTOUCHED (until candidate confirms via ingestion flow).
        """
        _validate_safe_id(roadmap_id, "roadmap_id")
        _validate_safe_id(milestone_id, "milestone_id")

        roadmap = await cls.get_roadmap(user, roadmap_id)

        target_ms: Optional[RoadmapMilestone] = None
        for ms in roadmap.milestones:
            if ms.milestone_id == milestone_id:
                target_ms = ms
                break

        if not target_ms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Milestone '{milestone_id}' not found in roadmap '{roadmap_id}'.",
            )

        # Eligibility Validation
        if target_ms.state != "VERIFIED_PROJECT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Milestone '{target_ms.title}' has state '{target_ms.state}'. Only milestones in 'VERIFIED_PROJECT' state are eligible for evidence promotion.",
            )

        if target_ms.category == "TransferableBridge":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TransferableBridge milestones cannot be promoted as project evidence. Use the candidate attestation flow instead.",
            )

        if not target_ms.verification_artifact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot promote milestone without a valid verification artifact.",
            )

        art = target_ms.verification_artifact
        if not art.artifact_id or not art.provenance_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification artifact is missing required identification or provenance hash.",
            )

        ingestion_id = f"ingest_prom_{roadmap_id}_{milestone_id}"
        promoted_proj_id = f"proj_{milestone_id[:12]}"

        # Establish and persist promoted_project_id linkage in RoadmapMilestone
        target_ms.promoted_project_id = promoted_proj_id
        if promoted_proj_id not in target_ms.workspace_evidence_ids:
            target_ms.workspace_evidence_ids.append(promoted_proj_id)

        # Idempotency Check
        try:
            existing_draft = await IngestionService.get_ingestion_draft(user, ingestion_id)
            if existing_draft.status == "Completed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Milestone project has already been promoted and confirmed into workspace evidence.",
                )
            # Update linkage on roadmap
            await cls._save_roadmap_doc(user, roadmap_id, roadmap.model_dump(by_alias=True))
            return existing_draft
        except HTTPException as he:
            if he.status_code == 400:
                raise
            # 404 means draft does not exist yet -> proceed to create

        now_iso = datetime.now(timezone.utc).isoformat()

        # Deterministic Field Mapping from ProjectBlueprint and VerificationArtifact
        if target_ms.project_blueprint:
            title = target_ms.project_blueprint.project_title or target_ms.title
            description = target_ms.project_blueprint.problem_statement or target_ms.rationale
            highlights = list(target_ms.project_blueprint.architecture_components) + list(art.checklist_completed)
            tech_stack = list(target_ms.project_blueprint.demonstrated_skills)
            if target_ms.requirement_name and target_ms.requirement_name not in tech_stack:
                tech_stack.append(target_ms.requirement_name)
        else:
            title = target_ms.title
            description = f"Project demonstrating {target_ms.target_capability}: {target_ms.rationale}"
            highlights = list(art.checklist_completed)
            tech_stack = [target_ms.requirement_name] if target_ms.requirement_name else []

        doc_name = f"Roadmap: {roadmap.title} ({target_ms.title})"

        proj_item = ProjectItem(
            id=promoted_proj_id,
            title=title,
            role="Lead Developer",
            description=description,
            highlights=highlights,
            techStack=tech_stack,
            sourceDocumentId=ingestion_id,
            sourceDocumentName=doc_name,
            verificationStatus="verified",
            confidence=1.0,
        )

        skill_items = [
            SkillItem(
                id=f"skill_prom_{uuid.uuid5(uuid.NAMESPACE_DNS, f'{ingestion_id}:{skill}').hex[:8]}",
                name=skill,
                category="Technical",
                proficiency="Intermediate",
                sourceDocumentId=ingestion_id,
                sourceDocumentName=doc_name,
                verificationStatus="verified",
                confidence=1.0,
            )
            for skill in tech_stack
        ]

        parsed_data = ParsedCandidateProfile(
            profile=ProfileDTO(),
            evidence=CandidateEvidence(
                projects=[proj_item],
                skills=skill_items,
            ),
        )

        raw_snippet = f"Milestone: {target_ms.title}\nArtifact ID: {art.artifact_id}\nArtifact Type: {art.artifact_type}\nProvenance Hash: {art.provenance_hash}"

        draft = IngestionDraft(
            ingestion_id=ingestion_id,
            document_name=doc_name,
            document_type="RoadmapProject",
            file_size_bytes=len(description.encode("utf-8")),
            status="Parsed",
            raw_text_snippet=raw_snippet,
            raw_text_char_count=len(raw_snippet),
            parsed_data=parsed_data,
            error_message=None,
            file_url=art.url,
            created_at=now_iso,
            updated_at=now_iso,
            completed_at=None,
        )

        # Persist draft in Firestore under users/{uid}/ingestions/{ingestion_id}
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/ingestions/{ingestion_id}"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        client = get_http_client()

        payload_dict = draft.model_dump(by_alias=True)
        fields_body = {"fields": _encode_firestore_fields(payload_dict)}

        res = await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)
        if res.status_code not in (200, 201):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist promotion draft in Firestore (status {res.status_code}).",
            )

        # Update roadmap document with linkage
        await cls._save_roadmap_doc(user, roadmap_id, roadmap.model_dump(by_alias=True))

        return draft

    @classmethod
    async def _save_roadmap_doc(
        cls,
        user: AuthenticatedUser,
        roadmap_id: str,
        doc_data: Dict[str, Any],
    ) -> bool:
        """Helper to save roadmap document to Firestore REST endpoint."""
        _validate_safe_id(roadmap_id, "roadmap_id")
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/roadmaps/{roadmap_id}"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        fields_body = {"fields": _encode_firestore_fields(doc_data)}
        client = get_http_client()
        try:
            res = await client.patch(doc_url, headers=headers, json=fields_body)
            return res.status_code in (200, 201)
        except Exception as e:
            logger.error(
                f"Error saving roadmap doc: {str(e)}",
                extra={"event": "firestore_write_error", "error_type": type(e).__name__, "component": "career_roadmap_service"},
            )
            return False
