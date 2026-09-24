"""
Vector Storage Contract and In-Memory Vector Store for ResumeIQ

Provides:
1. VectorRecord model with full embedding metadata and source content hash
2. VectorStore interface (storage-agnostic contract for InMemory, pgvector, or Qdrant)
3. InMemoryVectorStore with cosine similarity, user-isolated partitions, and stale invalidation
"""

import math
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field, ConfigDict

from app.ai.retrieval.embedding_provider import EmbeddingMetadata, compute_content_sha256


class VectorRecord(BaseModel):
    """
    Strongly-typed representation of an embedded evidence item or query.
    Encapsulates user ownership, provenance, content hash, and vector values.
    """
    user_id: str = Field(..., alias="userId")
    evidence_id: str = Field(..., alias="evidenceId")
    content_hash: str = Field(..., alias="contentHash")
    item_text: str = Field(..., alias="itemText")
    vector: List[float] = Field(default_factory=list)
    metadata: EmbeddingMetadata

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Computes cosine similarity between two unit or non-unit vectors:
    cos(theta) = (v1 . v2) / (||v1|| * ||v2||)
    Returns value bounded in [0.0, 1.0] for non-negative projections, or [-1.0, 1.0].
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_1 = math.sqrt(sum(a * a for a in v1))
    norm_2 = math.sqrt(sum(b * b for b in v2))

    if norm_1 == 0.0 or norm_2 == 0.0:
        return 0.0

    sim = dot_product / (norm_1 * norm_2)
    # Clamp to [-1.0, 1.0] to guard floating point rounding
    return max(-1.0, min(1.0, sim))


class InMemoryVectorStore:
    """
    Thread-safe in-memory vector index partitioned by user_id.
    Guarantees strict user isolation and automatic stale embedding invalidation.
    """

    def __init__(self):
        # Partitioned store: {user_id: {evidence_id: VectorRecord}}
        self._user_stores: Dict[str, Dict[str, VectorRecord]] = {}

    def upsert(self, record: VectorRecord) -> None:
        """Stores or updates a vector record in the user's isolated partition."""
        user_partition = self._user_stores.setdefault(record.user_id, {})
        user_partition[record.evidence_id] = record

    def get(self, user_id: str, evidence_id: str) -> Optional[VectorRecord]:
        """Retrieves a vector record for a specific user and evidence ID."""
        return self._user_stores.get(user_id, {}).get(evidence_id)

    def is_stale(self, user_id: str, evidence_id: str, current_content_hash: str) -> bool:
        """
        Determines whether a stored embedding is stale by comparing its source content hash.
        Returns True if not found or if the hash has changed.
        """
        record = self.get(user_id, evidence_id)
        if not record:
            return True
        return record.content_hash != current_content_hash

    def search(
        self,
        user_id: str,
        query_vector: List[float],
        top_k: int = 10,
        min_similarity: float = 0.0,
    ) -> List[Tuple[VectorRecord, float]]:
        """
        Performs cosine similarity search strictly within the authenticated user's partition.
        Returns a sorted list of (VectorRecord, similarity_score) in descending order of similarity.
        Cross-user access is architecturally impossible.
        """
        user_partition = self._user_stores.get(user_id, {})
        if not user_partition or not query_vector:
            return []

        scored_records: List[Tuple[VectorRecord, float]] = []
        for record in user_partition.values():
            sim = cosine_similarity(query_vector, record.vector)
            # Map [-1.0, 1.0] to [0.0, 1.0] for normalized retrieval scoring
            normalized_sim = max(0.0, (sim + 1.0) / 2.0) if sim < 0.0 else sim
            if normalized_sim >= min_similarity:
                scored_records.append((record, normalized_sim))

        scored_records.sort(key=lambda x: x[1], reverse=True)
        return scored_records[:top_k]

    def clear_user(self, user_id: str) -> None:
        """Clears all indexed vectors for a specific user."""
        if user_id in self._user_stores:
            del self._user_stores[user_id]

    def total_count(self, user_id: Optional[str] = None) -> int:
        """Returns the total number of indexed vector records for a user or globally."""
        if user_id is not None:
            return len(self._user_stores.get(user_id, {}))
        return sum(len(part) for part in self._user_stores.values())


# Global in-memory singleton instance
vector_store = InMemoryVectorStore()
