import re
from typing import List, Dict, Set, Optional, Any
from app.core.auth import AuthenticatedUser
from app.schemas.evidence import (
    EvidenceItem,
    EvidenceSourceType,
    EvidenceRelationship,
    EvidenceGraphQuery,
    EvidenceQueryResult,
)
from app.services.evidence_service import EvidenceService
from app.ai.skills import normalize_skill_name


class CareerEvidenceGraph:
    """
    In-memory deterministic relationship and query layer over a candidate's EvidenceItems.
    Answers semantic provenance queries:
      - Which projects demonstrate React?
      - Which experiences show backend engineering?
      - What evidence supports skill X?
      - Which items contain quantifiable metrics?
    """

    def __init__(self, user_id: str = "temp_user", items: Optional[List[EvidenceItem]] = None):
        self.user_id = user_id
        self._items_by_id: Dict[str, EvidenceItem] = {}
        self._skill_index: Dict[str, Set[str]] = {}
        self._tech_index: Dict[str, Set[str]] = {}
        self._role_index: Dict[str, Set[str]] = {}
        self._source_type_index: Dict[str, Set[str]] = {}
        self._relationships: List[EvidenceRelationship] = []

        self._build_index(items or [])

    def _build_index(self, items: List[EvidenceItem]) -> None:
        """Constructs multi-index lookups and directed relationships."""
        for item in items:
            # Enforce user boundary
            if item.user_id != self.user_id:
                continue

            self._items_by_id[item.evidence_id] = item

            # Index by source type
            self._source_type_index.setdefault(item.source_type, set()).add(item.evidence_id)

            # Index by role
            if item.role:
                clean_role = item.role.lower().strip()
                self._role_index.setdefault(clean_role, set()).add(item.evidence_id)
                self._relationships.append(
                    EvidenceRelationship(
                        sourceEvidenceId=item.evidence_id,
                        targetId=item.role,
                        targetType="Role",
                        relationshipType="held_role",
                    )
                )

            # Index by skills
            for s in item.skills:
                norm_s = normalize_skill_name(s).lower()
                self._skill_index.setdefault(norm_s, set()).add(item.evidence_id)
                self._relationships.append(
                    EvidenceRelationship(
                        sourceEvidenceId=item.evidence_id,
                        targetId=norm_s,
                        targetType="Skill",
                        relationshipType="demonstrates_skill",
                    )
                )

            # Index by technologies
            for t in item.technologies:
                norm_t = normalize_skill_name(t).lower()
                self._tech_index.setdefault(norm_t, set()).add(item.evidence_id)
                self._relationships.append(
                    EvidenceRelationship(
                        sourceEvidenceId=item.evidence_id,
                        targetId=norm_t,
                        targetType="Technology",
                        relationshipType="uses_technology",
                    )
                )

            # Index achievements / metrics
            for ach in item.achievements:
                self._relationships.append(
                    EvidenceRelationship(
                        sourceEvidenceId=item.evidence_id,
                        targetId=ach[:80],
                        targetType="Achievement",
                        relationshipType="produced_achievement",
                    )
                )

    def find_by_skill(self, skill_name: str) -> List[EvidenceItem]:
        """Finds all evidence items demonstrating a specific skill (case & alias normalized)."""
        if not skill_name:
            return []
        norm = normalize_skill_name(skill_name).lower()
        ev_ids = self._skill_index.get(norm, set())
        return [self._items_by_id[eid] for eid in sorted(ev_ids)]

    def find_by_technology(self, tech_name: str) -> List[EvidenceItem]:
        """Finds all evidence items using a specific technology or tool."""
        if not tech_name:
            return []
        norm = normalize_skill_name(tech_name).lower()
        ev_ids = self._tech_index.get(norm, set())
        return [self._items_by_id[eid] for eid in sorted(ev_ids)]

    def find_by_role(self, role_keyword: str) -> List[EvidenceItem]:
        """Finds all evidence items where the role matches or contains the keyword."""
        if not role_keyword:
            return []
        kw = role_keyword.lower().strip()
        matched_ids: Set[str] = set()
        for role_str, ids in self._role_index.items():
            if kw in role_str:
                matched_ids.update(ids)
        return [self._items_by_id[eid] for eid in sorted(matched_ids)]

    def find_by_source_type(self, source_type: EvidenceSourceType) -> List[EvidenceItem]:
        """Finds all evidence items from a specific workspace category."""
        ev_ids = self._source_type_index.get(source_type, set())
        return [self._items_by_id[eid] for eid in sorted(ev_ids)]

    def find_by_metric_presence(self) -> List[EvidenceItem]:
        """Returns all evidence items containing extracted quantifiable metrics."""
        return [item for item in self._items_by_id.values() if len(item.metrics) > 0]

    def get_skills_demonstrated(self) -> List[str]:
        """Returns a sorted list of all unique normalized skills demonstrated in the graph."""
        return sorted(list(self._skill_index.keys()))

    def get_technologies_demonstrated(self) -> List[str]:
        """Returns a sorted list of all unique normalized technologies demonstrated."""
        return sorted(list(self._tech_index.keys()))

    def get_provenance(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Returns the source provenance (source_type, source_item_id, title) for a given evidence ID."""
        item = self._items_by_id.get(evidence_id)
        if not item:
            return None
        return {
            "evidenceId": item.evidence_id,
            "sourceType": item.source_type,
            "sourceItemId": item.source_item_id,
            "title": item.title,
            "dates": item.dates,
            "verificationStatus": item.verification_status,
            "confidence": item.confidence,
        }

    def query(self, query: EvidenceGraphQuery) -> EvidenceQueryResult:
        """Executes a multi-criteria query across the candidate evidence graph."""
        candidates = set(self._items_by_id.keys())

        if query.source_type:
            type_ids = self._source_type_index.get(query.source_type, set())
            candidates &= type_ids

        if query.skill:
            norm_s = normalize_skill_name(query.skill).lower()
            skill_ids = self._skill_index.get(norm_s, set())
            # Also check substring in skill names
            partial_matches: Set[str] = set()
            for s_name, ids in self._skill_index.items():
                if norm_s in s_name or s_name in norm_s:
                    partial_matches.update(ids)
            candidates &= (skill_ids | partial_matches)

        if query.technology:
            norm_t = normalize_skill_name(query.technology).lower()
            tech_ids = self._tech_index.get(norm_t, set())
            partial_matches: Set[str] = set()
            for t_name, ids in self._tech_index.items():
                if norm_t in t_name or t_name in norm_t:
                    partial_matches.update(ids)
            candidates &= (tech_ids | partial_matches)

        if query.role:
            role_kw = query.role.lower().strip()
            role_ids: Set[str] = set()
            for r_name, ids in self._role_index.items():
                if role_kw in r_name:
                    role_ids.update(ids)
            candidates &= role_ids

        matched_items: List[EvidenceItem] = []
        skills_matched: Set[str] = set()
        techs_matched: Set[str] = set()

        for eid in sorted(candidates):
            item = self._items_by_id[eid]
            if query.has_metrics is True and not item.metrics:
                continue
            if query.has_metrics is False and item.metrics:
                continue
            if query.min_confidence is not None and item.confidence < query.min_confidence:
                continue

            matched_items.append(item)
            skills_matched.update(item.skills)
            techs_matched.update(item.technologies)

        return EvidenceQueryResult(
            items=matched_items,
            totalCount=len(matched_items),
            skillsMatched=sorted(list(skills_matched)),
            technologiesMatched=sorted(list(techs_matched)),
        )


class EvidenceGraphService:
    """
    Factory & service for building and querying candidate Career Evidence Graphs.
    Always strictly scoped to AuthenticatedUser.uid.
    """

    @classmethod
    async def build_graph_for_user(cls, user: AuthenticatedUser) -> CareerEvidenceGraph:
        """
        Loads the candidate's workspace evidence, normalizes into EvidenceItems,
        and constructs an authoritative CareerEvidenceGraph.
        """
        evidence_items = await EvidenceService.get_user_evidence(user)
        return CareerEvidenceGraph(user_id=user.uid, items=evidence_items)
