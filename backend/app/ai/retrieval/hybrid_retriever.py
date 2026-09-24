"""
Hybrid Retrieval Engine for ResumeIQ

Fuses Exact/Canonical Keyword Retrieval (Signal A) with Dense Semantic Retrieval (Signal B).
Features:
- Deterministic weighted score fusion (WEIGHT_EXACT=0.60, WEIGHT_SEMANTIC=0.40)
- Strict user isolation in vector and graph queries
- Intelligent embedding caching & stale hash invalidation
- Graceful degradation / fallback if embedding provider fails
- Clear boundary: Retrieval != Factual Match Classification
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.evidence import EvidenceItem
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.ai.skills import normalize_skill_name
from app.ai.retrieval.embedding_provider import (
    BaseEmbeddingProvider,
    EmbeddingMetadata,
    compute_content_sha256,
    get_embedding_provider,
)
from app.ai.retrieval.vector_store import (
    VectorRecord,
    InMemoryVectorStore,
    vector_store as default_vector_store,
)

logger = logging.getLogger(__name__)

# Named Configuration Weights for Deterministic Hybrid Fusion
# Sums to 1.00 when both signals are present.
WEIGHT_EXACT = 0.60
WEIGHT_SEMANTIC = 0.40

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
    "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were",
    "will", "with", "or", "our", "you", "your", "we", "they", "this", "but",
}


def _extract_keywords(text: str) -> Set[str]:
    """Extracts alphanumeric keywords ignoring common stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\+#\.]+\b", text.lower())
    return {t for t in tokens if len(t) > 1 and t not in STOPWORDS}


def compute_evidence_content(item: EvidenceItem) -> Tuple[str, str]:
    """
    Constructs a dense, semantically meaningful text representation of an EvidenceItem
    excluding ungrounded metadata or noisy IDs, along with its deterministic SHA-256 hash.
    """
    parts: List[str] = []
    if item.title:
        parts.append(f"Title: {item.title}")
    if item.role:
        parts.append(f"Role: {item.role}")
    if getattr(item, "domain", None):
        parts.append(f"Domain: {item.domain}")
    if item.description:
        parts.append(f"Description: {item.description}")
    if item.responsibilities:
        parts.append(f"Responsibilities: {' '.join(item.responsibilities)}")
    if item.achievements:
        parts.append(f"Achievements: {' '.join(item.achievements)}")
    
    all_tech = item.skills + item.technologies
    if all_tech:
        parts.append(f"Technologies: {', '.join(all_tech)}")

    content = " | ".join(parts)
    content_hash = compute_content_sha256(content)
    return content, content_hash


def compute_query_content(
    target_role: str,
    query_text: str = "",
    must_have_skills: Optional[List[str]] = None,
) -> str:
    """Constructs a dense representation of the job requirement query."""
    parts: List[str] = []
    if target_role:
        parts.append(f"Target Role: {target_role}")
    if must_have_skills:
        parts.append(f"Key Requirements: {', '.join(must_have_skills)}")
    if query_text:
        parts.append(f"Description: {query_text[:1000]}")
    return " | ".join(parts)


class RetrievalCandidate(BaseModel):
    """
    Unified candidate evidence item returned by HybridRetriever.
    Maintains transparent signal provenance and hybrid fused score.
    """
    evidence_id: str = Field(..., alias="evidenceId")
    exact_score: float = Field(default=0.0, ge=0.0, le=1.0, alias="exactScore")
    semantic_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, alias="semanticScore")
    fused_score: float = Field(default=0.0, ge=0.0, le=1.0, alias="fusedScore")
    retrieval_sources: List[str] = Field(default_factory=list, alias="retrievalSources")
    matched_skills: List[str] = Field(default_factory=list, alias="matchedSkills")
    matched_terms: List[str] = Field(default_factory=list, alias="matchedTerms")
    evidence_item: Optional[EvidenceItem] = Field(default=None, alias="evidenceItem")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class HybridRetriever:
    """
    Production Hybrid Retrieval Engine.
    Coordinates exact canonical matching and dense vector search to retrieve
    ranked evidence candidates for a candidate user.
    """

    def __init__(
        self,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        store: Optional[InMemoryVectorStore] = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.store = store or default_vector_store

    async def index_evidence_items(
        self,
        user_id: str,
        items: List[EvidenceItem],
        force_reindex: bool = False,
    ) -> int:
        """
        Indexes a list of EvidenceItems for dense semantic retrieval.
        Utilizes content hash validation to avoid redundant embedding generations:
        only computes embeddings for items that are new or whose content has changed.
        Returns the count of newly embedded items.
        """
        if not items:
            return 0

        # Filter items for authenticated user
        user_items = [item for item in items if item.user_id == user_id]
        new_or_stale: List[Tuple[EvidenceItem, str, str]] = []

        for item in user_items:
            content, content_hash = compute_evidence_content(item)
            if force_reindex or self.store.is_stale(user_id, item.evidence_id, content_hash):
                new_or_stale.append((item, content, content_hash))

        if not new_or_stale:
            return 0

        texts_to_embed = [content for _, content, _ in new_or_stale]
        try:
            vectors = await self.embedding_provider.embed_batch(texts_to_embed)
        except Exception as e:
            logger.warning(f"HybridRetriever: Failed to embed batch of {len(texts_to_embed)} items: {e}")
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        for (item, content, content_hash), vec in zip(new_or_stale, vectors):
            record = VectorRecord(
                userId=user_id,
                evidenceId=item.evidence_id,
                contentHash=content_hash,
                itemText=content,
                vector=vec,
                metadata=EmbeddingMetadata(
                    modelName=self.embedding_provider.model_name,
                    modelVersion=self.embedding_provider.version,
                    sourceContentHash=content_hash,
                    dimension=self.embedding_provider.dimension,
                    createdAt=now_iso,
                ),
            )
            self.store.upsert(record)

        return len(new_or_stale)

    async def retrieve_candidates(
        self,
        user_id: str,
        target_role: str,
        query_text: str = "",
        must_have_skills: Optional[List[str]] = None,
        candidate_items: Optional[List[EvidenceItem]] = None,
        top_k: int = 10,
        enable_semantic: bool = True,
    ) -> List[RetrievalCandidate]:
        """
        Retrieves top candidate evidence items fusing exact and dense semantic signals.
        - Signal A: Exact keyword / skill token overlap against candidate items
        - Signal B: Dense semantic vector cosine similarity
        - Hybrid Fusion: Weighted combination
        Guarantees strict user isolation and deterministic fallback.
        """
        items_by_id: Dict[str, EvidenceItem] = {}
        if candidate_items:
            for item in candidate_items:
                if item.user_id == user_id:
                    items_by_id[item.evidence_id] = item

        # Auto-index un-indexed or stale items
        if candidate_items and enable_semantic:
            await self.index_evidence_items(user_id, candidate_items)

        # 1. Compute Exact Retrieval Scores (Signal A)
        query_kws = _extract_keywords(f"{target_role} {query_text} {' '.join(must_have_skills or [])}")
        exact_scores: Dict[str, float] = {}
        matched_skills_map: Dict[str, List[str]] = {}
        matched_terms_map: Dict[str, List[str]] = {}

        for eid, item in items_by_id.items():
            content_text, _ = compute_evidence_content(item)
            item_kws = _extract_keywords(content_text)
            overlap = query_kws & item_kws
            matched_terms_map[eid] = sorted(list(overlap))

            # Skill-specific overlap
            item_skills_lower = {s.lower() for s in (item.skills + item.technologies)}
            matched_s: List[str] = []
            if must_have_skills:
                for req in must_have_skills:
                    if req.lower() in item_skills_lower or req.lower() in item_kws:
                        matched_s.append(req)
            matched_skills_map[eid] = matched_s

            base_exact = len(overlap) / max(1, len(query_kws)) if query_kws else 0.0
            skill_boost = (len(matched_s) / max(1, len(must_have_skills))) if must_have_skills else 0.0
            exact_score = min(1.0, (base_exact * 0.5) + (skill_boost * 0.5)) if must_have_skills else base_exact
            exact_scores[eid] = exact_score

        # 2. Compute Dense Semantic Scores (Signal B)
        semantic_scores: Dict[str, float] = {}
        if enable_semantic:
            query_repr = compute_query_content(target_role, query_text, must_have_skills)
            try:
                query_vector = await self.embedding_provider.embed_text(query_repr)
                search_results = self.store.search(user_id=user_id, query_vector=query_vector, top_k=top_k * 2)
                for rec, sim in search_results:
                    if rec.evidence_id in items_by_id:
                        semantic_scores[rec.evidence_id] = sim
            except Exception as e:
                logger.warning(f"HybridRetriever: Dense semantic retrieval failed, falling back to exact: {e}")

        # 3. Fuse Signals Deterministically
        all_candidate_ids = set(items_by_id.keys())
        candidates: List[RetrievalCandidate] = []

        for eid in all_candidate_ids:
            item = items_by_id[eid]
            exact_sc = exact_scores.get(eid, 0.0)
            sem_sc = semantic_scores.get(eid)

            sources: List[str] = []
            if exact_sc > 0.0:
                sources.append("exact_lexical")
            if sem_sc is not None and sem_sc > 0.1:
                sources.append("dense_semantic")

            if sem_sc is not None:
                fused_sc = (WEIGHT_EXACT * exact_sc) + (WEIGHT_SEMANTIC * sem_sc)
            else:
                fused_sc = exact_sc

            candidates.append(
                RetrievalCandidate(
                    evidenceId=eid,
                    exactScore=round(exact_sc, 4),
                    semanticScore=round(sem_sc, 4) if sem_sc is not None else None,
                    fusedScore=round(min(1.0, max(0.0, fused_sc)), 4),
                    retrievalSources=sources,
                    matchedSkills=matched_skills_map.get(eid, []),
                    matchedTerms=matched_terms_map.get(eid, []),
                    evidenceItem=item,
                )
            )

        candidates.sort(key=lambda c: c.fused_score, reverse=True)
        return candidates[:top_k]
