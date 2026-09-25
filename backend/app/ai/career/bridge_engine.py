"""
Bridge Engine for Career Intelligence (Phase 5.0)

Discovers valid transferable skill bridges between missing job requirements
and verified candidate evidence without ever hallucinating unverified experience.
"""

import uuid
from typing import List, Dict, Set, Optional, Tuple
from app.schemas.candidate import CandidateEvidence
from app.schemas.evidence import EvidenceItem
from app.schemas.requirement_match import RequirementMatch, EvidenceSourceSection
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    SkillTransferabilityRule,
)
from app.ai.skills import normalize_skill_name
from app.ai.career.taxonomy import GLOBAL_TRANSFERABILITY_GRAPH, SkillTransferabilityGraph
from app.services.evidence_graph_service import CareerEvidenceGraph


class BridgeEngine:
    """
    Deterministic Bridge Detection Layer.
    Discovers transferable skill opportunities without mutating authoritative evidence.
    """

    @classmethod
    def find_transferable_bridges(
        cls,
        missing_requirements: List[RequirementMatch],
        candidate_evidence: CandidateEvidence,
        evidence_graph: Optional[CareerEvidenceGraph] = None,
        taxonomy_graph: Optional[SkillTransferabilityGraph] = None,
    ) -> List[TransferableSkillBridge]:
        """
        Scans missing or partial requirements against candidate's verified skills & experiences.
        For each gap where a verified adjacent skill exists in candidate evidence,
        constructs an explicit TransferableSkillBridge contract.
        """
        taxonomy = taxonomy_graph or GLOBAL_TRANSFERABILITY_GRAPH
        discovered_bridges: List[TransferableSkillBridge] = []
        seen_pairs: Set[Tuple[str, str]] = set()

        # 1. Build index of verified candidate skills mapped to evidence items
        verified_skills_map: Dict[str, List[Tuple[str, str, str]]] = {}
        # key: normalized_skill_name -> List of (evidence_id, title, section)

        # Index from candidate experience
        for i, exp in enumerate(candidate_evidence.experience):
            item_id = exp.id or f"exp_{i}"
            item_title = f"{exp.role} at {exp.company}" if exp.company else (exp.role or "Experience")
            for t in exp.technologies:
                norm_t = normalize_skill_name(t).lower()
                verified_skills_map.setdefault(norm_t, []).append((item_id, item_title, "Experience"))
            for b in exp.bullets:
                # Check for explicit skill mentions in verified bullets
                for rule_src in taxonomy._by_source.keys():
                    if rule_src in b.lower():
                        verified_skills_map.setdefault(rule_src, []).append((item_id, item_title, "Experience"))

        # Index from candidate projects
        for i, proj in enumerate(candidate_evidence.projects):
            item_id = proj.id or f"proj_{i}"
            proj_techs = getattr(proj, "tech_stack", None) or getattr(proj, "technologies", []) or []
            for t in proj_techs:
                norm_t = normalize_skill_name(t).lower()
                verified_skills_map.setdefault(norm_t, []).append((item_id, item_title, "Project"))

        # Index from candidate explicit skill tags
        for s in candidate_evidence.skills:
            norm_s = normalize_skill_name(s.name).lower()
            verified_skills_map.setdefault(norm_s, []).append((f"skill_{norm_s}", s.name, "SkillTag"))

        # 2. Match each missing requirement against potential bridges
        for req in missing_requirements:
            if req.match_status == "StrongMatch":
                continue  # Already satisfied by direct evidence

            req_norm = normalize_skill_name(req.requirement_name).lower()
            candidate_rules = taxonomy.find_bridges_for_target(req_norm)

            for rule in candidate_rules:
                src_norm = normalize_skill_name(rule.source_skill).lower()
                
                # Check if candidate possesses verified source evidence for this rule
                if src_norm in verified_skills_map:
                    evidence_locations = verified_skills_map[src_norm]
                    if not evidence_locations:
                        continue

                    # Select best primary evidence source (Experience preferred over Project/SkillTag)
                    best_ev = evidence_locations[0]
                    for ev in evidence_locations:
                        if ev[2] == "Experience":
                            best_ev = ev
                            break

                    pair_key = (src_norm, req_norm)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    prompt_text = (
                        rule.verification_questions[0]
                        if rule.verification_questions
                        else f"Have you applied {rule.target_skill} in production or side-projects utilizing your {rule.source_skill} background?"
                    )

                    sec_val = best_ev[2]
                    valid_section: EvidenceSourceSection = "Experience"
                    if sec_val in ("Experience", "Project", "SkillTag", "Education", "Certification", "Summary", "None"):
                        valid_section = sec_val  # type: ignore

                    bridge = TransferableSkillBridge(
                        bridgeId=f"brg_{uuid.uuid4().hex[:8]}",
                        requiredSkill=req.requirement_name,
                        candidateSkill=rule.source_skill,
                        sourceEvidenceId=best_ev[0],
                        sourceEvidenceTitle=best_ev[1],
                        sourceSection=valid_section,
                        relationshipType=rule.relationship_type,
                        transferabilityScore=rule.transferability_score,
                        transferRationale=rule.transfer_rationale,
                        sharedCompetencies=rule.shared_competencies,
                        criticalDifferences=rule.critical_differences,
                        attestationPrompt=prompt_text,
                        status="TransferablePossibility",
                    )
                    discovered_bridges.append(bridge)

        return discovered_bridges
