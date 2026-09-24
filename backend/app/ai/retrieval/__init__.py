"""
ResumeIQ Hybrid Retrieval Foundation
Combines Exact / Canonical Retrieval with Dense Semantic Retrieval.
"""

from app.ai.retrieval.embedding_provider import (
    BaseEmbeddingProvider,
    DeterministicFeatureEmbeddingProvider,
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
    EmbeddingMetadata,
    compute_content_sha256,
    get_embedding_provider,
)
from app.ai.retrieval.vector_store import (
    VectorRecord,
    InMemoryVectorStore,
    cosine_similarity,
    vector_store,
)
from app.ai.retrieval.hybrid_retriever import (
    RetrievalCandidate,
    HybridRetriever,
    compute_evidence_content,
    compute_query_content,
    WEIGHT_EXACT,
    WEIGHT_SEMANTIC,
)
from app.ai.retrieval.evidence_ranker import (
    EvidenceRanker,
    RankedEvidenceItem,
)
from app.ai.retrieval.hybrid_matcher import (
    HybridMatcher,
    MatchClass,
    RequirementMatchResult,
    HybridMatchResponse,
    TECHNOLOGY_CLUSTERS,
    find_related_technology,
)

__all__ = [
    "BaseEmbeddingProvider",
    "DeterministicFeatureEmbeddingProvider",
    "GeminiEmbeddingProvider",
    "MockEmbeddingProvider",
    "EmbeddingMetadata",
    "compute_content_sha256",
    "get_embedding_provider",
    "VectorRecord",
    "InMemoryVectorStore",
    "cosine_similarity",
    "vector_store",
    "RetrievalCandidate",
    "HybridRetriever",
    "compute_evidence_content",
    "compute_query_content",
    "WEIGHT_EXACT",
    "WEIGHT_SEMANTIC",
    "EvidenceRanker",
    "RankedEvidenceItem",
    "HybridMatcher",
    "MatchClass",
    "RequirementMatchResult",
    "HybridMatchResponse",
    "TECHNOLOGY_CLUSTERS",
    "find_related_technology",
]
