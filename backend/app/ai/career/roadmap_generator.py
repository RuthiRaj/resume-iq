"""
Deterministic Roadmap Generator for Career Intelligence (Phase 5.1)

Synthesizes structured, capability-grounded career roadmaps from candidate evidence,
transferable skill bridges, and gap remediation blueprints.
Operates completely deterministically with 0 LLM calls and 0 network requests.
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set

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
    MilestoneCategory,
)
from app.ai.skills import normalize_skill_name
from app.ai.career.bridge_engine import BridgeEngine
from app.ai.career.remediation_blueprints import GapRemediationEngine


class RoadmapGenerator:
    """
    Deterministic Career Roadmap Generator.
    Generates actionable, step-by-step milestones to bridge verified candidate skills
    to target job requirements.
    """

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
        Synthesizes a structured RoadmapPlan.
        Milestone sequencing:
        1. Transferable Bridges (immediate leverage of existing verified foundation)
        2. Core Foundations (learning paths for missing hard skills)
        3. Verifiable Projects (hands-on portfolio blueprints for hard gaps)
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        roadmap_id = f"rdm_{uuid.uuid4().hex[:12]}"

        # 1. Discover bridges and remediations if not provided
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
        order_idx = 0

        # Category 1: Transferable Bridges (Highest leverage / immediate impact)
        for bridge in transferable_bridges:
            key = f"bridge_{normalize_skill_name(bridge.required_skill).lower()}"
            if key in seen_milestone_keys:
                continue
            seen_milestone_keys.add(key)

            ms = RoadmapMilestone(
                milestoneId=f"ms_{uuid.uuid4().hex[:8]}",
                orderIndex=order_idx,
                title=f"Bridge {bridge.candidate_skill} to {bridge.required_skill}",
                category="TransferableBridge",
                requirementName=bridge.required_skill,
                targetCapability=f"Demonstrate {bridge.required_skill} proficiency building on verified {bridge.candidate_skill} experience",
                prerequisiteEvidenceIds=[bridge.source_evidence_id] if bridge.source_evidence_id else [],
                sourceBridgeId=bridge.bridge_id,
                rationale=bridge.transfer_rationale,
                estimatedWeeks=1,
                bridgeDetails=bridge,
                state="NOT_STARTED",
            )
            milestones.append(ms)
            order_idx += 1

        # Category 2 & 3: Hard Gap Remediations
        for strat in remediation_strategies:
            req_norm = normalize_skill_name(strat.requirement_name).lower()

            # 2a. Core Foundation (Learning Path)
            if strat.learning_paths:
                lp = strat.learning_paths[0]
                lp_key = f"learn_{req_norm}"
                if lp_key not in seen_milestone_keys:
                    seen_milestone_keys.add(lp_key)
                    ms_learn = RoadmapMilestone(
                        milestoneId=f"ms_{uuid.uuid4().hex[:8]}",
                        orderIndex=order_idx,
                        title=f"Learn Core Fundamentals: {strat.requirement_name}",
                        category="CoreFoundation",
                        requirementName=strat.requirement_name,
                        targetCapability=lp.title,
                        prerequisiteEvidenceIds=[],
                        rationale=strat.remediation_guidance,
                        estimatedWeeks=lp.estimated_weeks or 2,
                        learningPath=lp,
                        state="NOT_STARTED",
                    )
                    milestones.append(ms_learn)
                    order_idx += 1

            # 2b. Verifiable Project Blueprint
            if strat.project_blueprints:
                pb = strat.project_blueprints[0]
                pb_key = f"proj_{req_norm}"
                if pb_key not in seen_milestone_keys:
                    seen_milestone_keys.add(pb_key)
                    ms_proj = RoadmapMilestone(
                        milestoneId=f"ms_{uuid.uuid4().hex[:8]}",
                        orderIndex=order_idx,
                        title=f"Build Verifiable Project: {pb.project_title}",
                        category="VerifiableProject",
                        requirementName=strat.requirement_name,
                        targetCapability=pb.project_title,
                        prerequisiteEvidenceIds=[],
                        rationale=f"Construct verifiable portfolio proof for '{strat.requirement_name}': {pb.problem_statement}",
                        estimatedWeeks=2,
                        projectBlueprint=pb,
                        state="NOT_STARTED",
                    )
                    milestones.append(ms_proj)
                    order_idx += 1

        # Calculate Deterministic Provenance Hash from canonical generation inputs
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
                    "target_capability": m.target_capability.strip(),
                    "prerequisite_evidence_ids": sorted(m.prerequisite_evidence_ids),
                    "source_bridge_id": m.source_bridge_id or "",
                }
                for m in milestones
            ],
        }
        import json
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

        return RoadmapPlan(
            roadmapId=roadmap_id,
            userId=user_id,
            title=title,
            targetRole=target_role,
            targetCompany=target_company or "",
            targetLevel="",
            sourceVariantId=source_variant_id,
            version=1,
            totalMilestones=len(milestones),
            completedMilestones=0,
            overallProgressPct=0,
            milestones=milestones,
            provenance=provenance,
            createdAt=now_iso,
            updatedAt=now_iso,
        )
