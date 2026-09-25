"""
Deterministic Roadmap Generator for Career Intelligence (Phase 5.1 — Milestone 2)

Synthesizes structured, capability-grounded career roadmaps from candidate evidence,
transferable skill bridges, and gap remediation blueprints.
Operates completely deterministically with 0 LLM calls and 0 network requests.

Milestone 2 additions:
- Explicit DAG milestone dependency linking
- O(V+E) topological DAG cycle validation
- Time and priority aggregation (MustHave vs Preferred)
- Next recommended actionable milestone computation
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict

from app.schemas.candidate import CandidateEvidence
from app.schemas.requirement_match import RequirementMatch
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    GapRemediationStrategy,
)
from app.schemas.career_roadmap import (
    RoadmapPlan,
    RoadmapMilestone,
    RoadmapProvenance,
    RoadmapSnapshotRecord,
    TargetImportanceBreakdown,
    MilestoneCategory,
)
from app.ai.skills import normalize_skill_name
from app.ai.career.bridge_engine import BridgeEngine
from app.ai.career.remediation_blueprints import GapRemediationEngine


class RoadmapGenerator:
    """
    Deterministic Career Roadmap Generator.
    Generates actionable, step-by-step milestone DAGs to bridge verified candidate skills
    to target job requirements.
    """

    @classmethod
    def compute_workspace_evidence_hash(cls, candidate_evidence: CandidateEvidence) -> str:
        """
        Computes a deterministic canonical SHA-256 hash of the candidate's Master Workspace evidence.
        Canonicalizes experiences, projects, skills, certifications, and education.
        Never hashes timestamps or random IDs.
        """
        canonical_items = {
            "experiences": sorted([
                {
                    "company": (exp.company or "").strip().lower(),
                    "role": (exp.role or "").strip().lower(),
                    "bullets": sorted([b.strip() for b in (exp.bullets or []) if b and b.strip()]),
                    "technologies": sorted([t.strip().lower() for t in (exp.technologies or []) if t and t.strip()]),
                }
                for exp in (candidate_evidence.experience or [])
            ], key=lambda x: (x["company"], x["role"])),
            "projects": sorted([
                {
                    "title": (proj.title or "").strip().lower(),
                    "description": (proj.description or "").strip().lower(),
                    "highlights": sorted([h.strip() for h in (proj.highlights or []) if h and h.strip()]),
                    "tech_stack": sorted([t.strip().lower() for t in (proj.tech_stack or []) if t and t.strip()]),
                }
                for proj in (candidate_evidence.projects or [])
            ], key=lambda x: x["title"]),
            "skills": sorted(list(set([
                normalize_skill_name(s.name).lower()
                for s in (candidate_evidence.skills or [])
                if s.name and s.name.strip()
            ]))),
            "certifications": sorted([
                {
                    "title": (getattr(cert, "title", None) or getattr(cert, "name", None) or "").strip().lower(),
                    "issuer": (cert.issuer or "").strip().lower(),
                }
                for cert in (candidate_evidence.certifications or [])
                if (getattr(cert, "title", None) or getattr(cert, "name", None) or "").strip()
            ], key=lambda x: x["title"]),
            "education": sorted([
                {
                    "institution": (edu.institution or "").strip().lower(),
                    "degree": (edu.degree or "").strip().lower(),
                }
                for edu in (candidate_evidence.education or [])
                if edu.institution and edu.degree
            ], key=lambda x: (x["institution"], x["degree"])),
        }
        serialized = json.dumps(canonical_items, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def validate_milestone_dag(cls, milestones: List[RoadmapMilestone]) -> None:
        """
        Validates that the milestone dependency graph is topologically sound:
        - No duplicate milestone IDs
        - All prerequisite_milestone_ids exist in the roadmap
        - No self-dependencies
        - No duplicate prerequisite IDs
        - Strictly acyclic (DAG check via 3-color DFS)
        """
        seen_ids: Set[str] = set()
        for m in milestones:
            if m.milestone_id in seen_ids:
                raise ValueError(f"Duplicate milestone ID '{m.milestone_id}' detected in roadmap.")
            seen_ids.add(m.milestone_id)

        ms_ids = set(seen_ids)
        adj: Dict[str, List[str]] = {m.milestone_id: [] for m in milestones}

        for m in milestones:
            # Check duplicate prerequisite IDs
            if len(m.prerequisite_milestone_ids) != len(set(m.prerequisite_milestone_ids)):
                raise ValueError(f"Milestone '{m.milestone_id}' contains duplicate prerequisite IDs.")

            # Check self dependency and membership
            for prereq_id in m.prerequisite_milestone_ids:
                if prereq_id == m.milestone_id:
                    raise ValueError(f"Milestone '{m.milestone_id}' cannot depend on itself.")
                if prereq_id not in ms_ids:
                    raise ValueError(f"Milestone '{m.milestone_id}' references non-existent prerequisite '{prereq_id}'.")
                adj[prereq_id].append(m.milestone_id)

        # Cycle check (0 = unvisited, 1 = visiting, 2 = visited)
        state: Dict[str, int] = {m_id: 0 for m_id in ms_ids}

        def dfs(node: str) -> None:
            state[node] = 1  # visiting
            for neighbor in adj.get(node, []):
                if state[neighbor] == 1:
                    raise ValueError(f"Circular dependency detected involving milestone '{neighbor}'.")
                if state[neighbor] == 0:
                    dfs(neighbor)
            state[node] = 2  # visited

        for m_id in ms_ids:
            if state[m_id] == 0:
                dfs(m_id)

    @classmethod
    def calculate_next_recommended_milestone_id(cls, milestones: List[RoadmapMilestone]) -> Optional[str]:
        """
        Determines the next unblocked actionable milestone:
        - Milestone is not completed (state not in ('VERIFIED_PROJECT', 'ATTESTED'))
        - All prerequisite milestones are completed (state in ('VERIFIED_PROJECT', 'ATTESTED'))
        - Returns the earliest unblocked milestone by order_index
        """
        ms_map = {m.milestone_id: m for m in milestones}
        completed_states = {"VERIFIED_PROJECT", "ATTESTED"}

        for m in sorted(milestones, key=lambda x: x.order_index):
            if m.state in completed_states:
                continue
            # Check if all prerequisites are satisfied
            prereqs_satisfied = True
            for prereq_id in m.prerequisite_milestone_ids:
                prereq = ms_map.get(prereq_id)
                if not prereq or prereq.state not in completed_states:
                    prereqs_satisfied = False
                    break
            if prereqs_satisfied:
                return m.milestone_id

        return None

    @classmethod
    def generate_roadmap(
        cls,
        user_id: str,
        candidate_evidence: CandidateEvidence,
        target_role: str,
        target_company: Optional[str] = "",
        missing_requirements: Optional[List[RequirementMatch]] = None,
        transferable_bridges: Optional[List[TransferableSkillBridge]] = None,
        remediation_strategies: Optional[List[GapRemediationStrategy]] = None,
        source_variant_id: Optional[str] = None,
        source_analysis_score: Optional[int] = None,
    ) -> RoadmapPlan:
        """
        Synthesizes a structured, DAG-grounded RoadmapPlan.
        Milestone sequencing:
        1. Transferable Bridges (immediate leverage of existing verified foundation)
        2. Core Foundations (learning paths for missing hard skills)
        3. Verifiable Projects (hands-on portfolio blueprints for hard gaps)
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        roadmap_id = f"rdm_{uuid.uuid4().hex[:12]}"

        # 1. Index requirement importance
        importance_map: Dict[str, str] = {}
        for req in (missing_requirements or []):
            norm = normalize_skill_name(req.requirement_name).lower()
            importance_map[norm] = req.importance or "MustHave"

        # 2. Discover bridges and remediations if not provided
        if transferable_bridges is None or remediation_strategies is None:
            missing = missing_requirements or []
            if transferable_bridges is None:
                transferable_bridges = BridgeEngine.find_transferable_bridges(
                    missing_requirements=missing,
                    candidate_evidence=candidate_evidence,
                )
            if remediation_strategies is None:
                bridged_names = {
                    normalize_skill_name(b.required_skill).lower()
                    for b in transferable_bridges
                }
                remediation_strategies = [
                    GapRemediationEngine.generate_remediation_strategy(m)
                    for m in missing
                    if normalize_skill_name(m.requirement_name).lower() not in bridged_names
                ]

        milestones: List[RoadmapMilestone] = []
        seen_milestone_keys: Set[str] = set()
        milestone_index: Dict[str, str] = {}  # key: f"{norm_req}_{category}" -> milestone_id
        order_idx = 0

        # Category 1: Transferable Bridges (Highest leverage / immediate impact)
        for bridge in transferable_bridges:
            req_norm = normalize_skill_name(bridge.required_skill).lower()
            key = f"bridge_{req_norm}"
            if key in seen_milestone_keys:
                continue
            seen_milestone_keys.add(key)

            ms_id = f"ms_{uuid.uuid4().hex[:8]}"
            imp_val = importance_map.get(req_norm, "MustHave")
            valid_imp = imp_val if imp_val in ("MustHave", "Preferred", "Unspecified") else "MustHave"

            ms = RoadmapMilestone(
                milestoneId=ms_id,
                orderIndex=order_idx,
                title=f"Bridge {bridge.candidate_skill} to {bridge.required_skill}",
                category="TransferableBridge",
                requirementName=bridge.required_skill,
                importance=valid_imp,  # type: ignore
                targetCapability=f"Demonstrate {bridge.required_skill} proficiency building on verified {bridge.candidate_skill} experience",
                prerequisiteEvidenceIds=[bridge.source_evidence_id] if bridge.source_evidence_id else [],
                prerequisiteMilestoneIds=[],  # Bridges build directly on candidate evidence
                sourceBridgeId=bridge.bridge_id,
                rationale=bridge.transfer_rationale,
                estimatedWeeks=1,
                bridgeDetails=bridge,
                state="NOT_STARTED",
            )
            milestones.append(ms)
            milestone_index[f"{req_norm}_TransferableBridge"] = ms_id
            order_idx += 1

        # Category 2 & 3: Hard Gap Remediations
        for strat in remediation_strategies:
            req_norm = normalize_skill_name(strat.requirement_name).lower()
            imp_val = importance_map.get(req_norm, "MustHave")
            valid_imp = imp_val if imp_val in ("MustHave", "Preferred", "Unspecified") else "MustHave"

            # 2a. Core Foundation (Learning Path)
            learn_ms_id: Optional[str] = None
            if strat.learning_paths:
                lp = strat.learning_paths[0]
                lp_key = f"learn_{req_norm}"
                if lp_key not in seen_milestone_keys:
                    seen_milestone_keys.add(lp_key)
                    learn_ms_id = f"ms_{uuid.uuid4().hex[:8]}"

                    # If a bridge exists for this skill, depend on it; otherwise no prerequisite
                    prereqs = []
                    if f"{req_norm}_TransferableBridge" in milestone_index:
                        prereqs.append(milestone_index[f"{req_norm}_TransferableBridge"])

                    ms_learn = RoadmapMilestone(
                        milestoneId=learn_ms_id,
                        orderIndex=order_idx,
                        title=f"Learn Core Fundamentals: {strat.requirement_name}",
                        category="CoreFoundation",
                        requirementName=strat.requirement_name,
                        importance=valid_imp,  # type: ignore
                        targetCapability=lp.title,
                        prerequisiteEvidenceIds=[],
                        prerequisiteMilestoneIds=prereqs,
                        rationale=strat.remediation_guidance,
                        estimatedWeeks=lp.estimated_weeks or 2,
                        learningPath=lp,
                        state="NOT_STARTED",
                    )
                    milestones.append(ms_learn)
                    milestone_index[f"{req_norm}_CoreFoundation"] = learn_ms_id
                    order_idx += 1

            # 2b. Verifiable Project Blueprint
            if strat.project_blueprints:
                pb = strat.project_blueprints[0]
                pb_key = f"proj_{req_norm}"
                if pb_key not in seen_milestone_keys:
                    seen_milestone_keys.add(pb_key)
                    proj_ms_id = f"ms_{uuid.uuid4().hex[:8]}"

                    # Project depends on CoreFoundation learning if present, or Bridge if present
                    proj_prereqs = []
                    if f"{req_norm}_CoreFoundation" in milestone_index:
                        proj_prereqs.append(milestone_index[f"{req_norm}_CoreFoundation"])
                    elif f"{req_norm}_TransferableBridge" in milestone_index:
                        proj_prereqs.append(milestone_index[f"{req_norm}_TransferableBridge"])

                    ms_proj = RoadmapMilestone(
                        milestoneId=proj_ms_id,
                        orderIndex=order_idx,
                        title=f"Build Verifiable Project: {pb.project_title}",
                        category="VerifiableProject",
                        requirementName=strat.requirement_name,
                        importance=valid_imp,  # type: ignore
                        targetCapability=pb.project_title,
                        prerequisiteEvidenceIds=[],
                        prerequisiteMilestoneIds=proj_prereqs,
                        rationale=f"Construct verifiable portfolio proof for '{strat.requirement_name}': {pb.problem_statement}",
                        estimatedWeeks=2,
                        projectBlueprint=pb,
                        state="NOT_STARTED",
                    )
                    milestones.append(ms_proj)
                    milestone_index[f"{req_norm}_VerifiableProject"] = proj_ms_id
                    order_idx += 1

        # 3. Validate DAG Integrity (fails closed if cycle or invalid reference detected)
        cls.validate_milestone_dag(milestones)

        # 4. Compute Aggregate Metrics
        total_weeks = sum(m.estimated_weeks for m in milestones)
        must_have_count = sum(1 for m in milestones if m.importance == "MustHave")
        preferred_count = sum(1 for m in milestones if m.importance == "Preferred")
        importance_breakdown = TargetImportanceBreakdown(
            mustHaveCount=must_have_count,
            preferredCount=preferred_count,
        )

        next_rec_id = cls.calculate_next_recommended_milestone_id(milestones)

        # 5. Calculate Deterministic Provenance Hash from canonical generation inputs
        # Must NOT depend on timestamps, random UUIDs, or runtime metadata
        canonical_input = {
            "generator_version": "5.1.0",
            "user_id": user_id,
            "target_role": target_role.strip().lower(),
            "target_company": (target_company or "").strip().lower(),
            "source_variant_id": source_variant_id or "",
            "source_analysis_score": source_analysis_score,
            "milestone_blueprints": [
                {
                    "category": m.category,
                    "requirement_name": m.requirement_name.strip().lower(),
                    "importance": m.importance,
                    "target_capability": m.target_capability.strip(),
                    "prerequisite_evidence_ids": sorted(m.prerequisite_evidence_ids),
                    "prerequisite_milestone_indices": [
                        next(i for i, other in enumerate(milestones) if other.milestone_id == pid)
                        for pid in m.prerequisite_milestone_ids
                    ],
                    "source_bridge_id": m.source_bridge_id or "",
                    "estimated_weeks": m.estimated_weeks,
                }
                for m in milestones
            ],
        }
        canonical_serialized = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"))
        prov_hash = hashlib.sha256(canonical_serialized.encode("utf-8")).hexdigest()

        provenance = RoadmapProvenance(
            sourceVariantId=source_variant_id,
            sourceAnalysisScore=source_analysis_score,
            generatedAt=now_iso,
            generatorVersion="5.1.0",
            provenanceHash=prov_hash,
        )

        title = f"Career Roadmap: {target_role}" + (f" @ {target_company}" if target_company else "")
        evidence_hash = cls.compute_workspace_evidence_hash(candidate_evidence)

        initial_snapshot = RoadmapSnapshotRecord(
            snapshotId=f"snp_{uuid.uuid4().hex[:10]}",
            version=1,
            workspaceEvidenceHash=evidence_hash,
            targetRole=target_role,
            targetCompany=target_company or "",
            milestoneCount=len(milestones),
            completedMilestones=0,
            overallProgressPct=0,
            createdAt=now_iso,
            lifecycle="ACTIVE",
        )

        return RoadmapPlan(
            roadmapId=roadmap_id,
            userId=user_id,
            title=title,
            targetRole=target_role,
            targetCompany=target_company or "",
            targetLevel="",
            sourceVariantId=source_variant_id,
            version=1,
            lifecycle="ACTIVE",
            workspaceEvidenceHash=evidence_hash,
            isStale=False,
            reconciledAt=now_iso,
            totalMilestones=len(milestones),
            completedMilestones=0,
            overallProgressPct=0,
            estimatedTotalWeeks=total_weeks,
            targetImportanceBreakdown=importance_breakdown,
            nextRecommendedMilestoneId=next_rec_id,
            milestones=milestones,
            historySnapshots=[initial_snapshot],
            provenance=provenance,
            createdAt=now_iso,
            updatedAt=now_iso,
        )
