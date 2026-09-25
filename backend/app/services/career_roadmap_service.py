"""
Career Roadmap Service (Phase 5.1)

Orchestrates:
1. Deterministic Career Roadmap Generation
2. Roadmap Persistence & Retrieval under users/{uid}/roadmaps/{roadmapId}
3. Milestone Progress Lifecycle & Verification Artifact Validation
4. Strict Optimistic Concurrency & Tenant Isolation
5. Zero Root Evidence Contamination (Roadmap is derived intelligence only)
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set
from fastapi import HTTPException, status

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
)
from app.schemas.requirement_match import RequirementMatch
from app.schemas.candidate import CandidateEvidence
from app.services.resume_service import (
    ResumeService,
    get_http_client,
    _get_firestore_base_url,
    _decode_firestore_doc,
    _encode_firestore_fields,
    _validate_safe_id,
)
from app.services.variant_service import VariantService
from app.services.career_intelligence_service import CareerIntelligenceService
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
    Guarantees strict tenant isolation, evidence non-contamination, and optimistic concurrency.
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
            candidate_evidence = await ResumeService.load_master_profile(user)

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
    ) -> ListRoadmapsResponse:
        """Lists all career roadmaps belonging to the authenticated candidate."""
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
                        roadmaps.append(RoadmapPlan.model_validate(decoded))
                    except Exception:
                        pass
        except Exception as e:
            print(f"Warning: Failed to list roadmaps for user {user.uid}: {e}")

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
        Updates milestone progression state, validates state transitions, attaches verification
        artifacts or attestation records, and updates aggregates with optimistic concurrency.
        """
        roadmap = await cls.get_roadmap(user, roadmap_id)

        # 1. Optimistic Concurrency Check
        if roadmap.version != req.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrency conflict: roadmap is at version {roadmap.version}, but expected version was {req.expected_version}.",
            )

        # 2. Locate Target Milestone
        target_ms: Optional[RoadmapMilestone] = None
        for ms in roadmap.milestones:
            if ms.milestone_id == req.milestone_id:
                target_ms = ms
                break

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

        now_iso = datetime.now(timezone.utc).isoformat()

        # 4. Handle State-Specific Progression & Security Validation
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
            # Security Rule (ADV_039 / ADV_042): Must have valid proof artifact
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
            # Security Rule (ADV_043): Only TransferableBridge milestones can be ATTESTED
            if target_ms.category != "TransferableBridge":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Milestones of category '{target_ms.category}' cannot be ATTESTED. Use VERIFIED_PROJECT instead.",
                )

            # Security Rule: Roadmap state MUST NOT substitute for authoritative CandidateAttestationRequest
            if not req.attestation:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Direct transition to ATTESTED without invoking authoritative Phase 5.0 CandidateAttestationRequest is not permitted.",
                )

            # Invoke authoritative Phase 5.0 attestation pipeline (gates claims via ClaimValidator,
            # updates variant change ledger with UserAttested record, enforces tenant isolation)
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

        # 5. Recompute Aggregates & Bump Version
        completed_count = sum(
            1 for m in roadmap.milestones if m.state in ("VERIFIED_PROJECT", "ATTESTED")
        )
        total_count = len(roadmap.milestones)
        roadmap.completed_milestones = completed_count
        roadmap.overall_progress_pct = int((completed_count / total_count) * 100) if total_count > 0 else 0
        roadmap.version += 1
        roadmap.updated_at = now_iso

        # 6. Persist Updated Roadmap
        doc_payload = roadmap.model_dump(by_alias=True)
        saved = await cls._save_roadmap_doc(user, roadmap_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist updated roadmap state to database.",
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
        doc_url = f"{_get_firestore_base_url()}/users/{user.uid}/roadmaps/{roadmap_id}"
        headers = {"Authorization": f"Bearer {user.token}"}
        client = get_http_client()

        try:
            res = await client.delete(doc_url, headers=headers)
            if res.status_code in (200, 204):
                return DeleteRoadmapResponse(
                    success=True,
                    roadmapId=roadmap_id,
                    message="Career roadmap successfully deleted.",
                )
            elif res.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Career roadmap '{roadmap_id}' not found.",
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
            print(f"Error saving roadmap doc: {e}")
            return False
