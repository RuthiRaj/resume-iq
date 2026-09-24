"""
Embedding Provider Abstraction for ResumeIQ

Defines the vendor-agnostic BaseEmbeddingProvider interface and concrete providers:
1. DeterministicFeatureEmbeddingProvider (100% deterministic, offline, zero-network)
2. GeminiEmbeddingProvider (Google GenAI text-embedding-004)
3. MockEmbeddingProvider (for fault injection & testing)
"""

import abc
import hashlib
import math
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.core.config import settings


class EmbeddingMetadata(BaseModel):
    """Metadata contract associated with any computed embedding vector."""
    model_name: str = Field(..., alias="modelName")
    model_version: str = Field(default="1.0", alias="modelVersion")
    source_content_hash: str = Field(..., alias="sourceContentHash")
    dimension: int = Field(default=256)
    created_at: str = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


def compute_content_sha256(text: str) -> str:
    """Computes a deterministic SHA-256 hash for normalized text content."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class BaseEmbeddingProvider(abc.ABC):
    """Abstract Base Class for all ResumeIQ Embedding Providers."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Returns the canonical model identifier."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @property
    def version(self) -> str:
        """Returns the provider version string."""
        return "1.0"

    @abc.abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generates a unit-normalized embedding vector for single input text."""
        pass

    @abc.abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates unit-normalized embedding vectors for a batch of input texts."""
        pass


class DeterministicFeatureEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic semantic feature hashing embedding provider.
    Computes a 256-dimensional L2-normalized vector using sub-word n-grams and
    term-frequency projection with known semantic synonym expansions.
    
    Guarantees:
    - 100% deterministic (reproducible across test runs and environments)
    - Zero network calls / zero latency
    - L2-normalized (|v| = 1.0)
    - High cosine similarity for semantically related software concepts
    """

    def __init__(self, dimension: int = 256):
        self._dim = dimension
        # Semantic expansion clusters for local concept projection
        self._synonym_map = {
            "rest": ["api", "http", "service", "endpoint", "microservice", "fastapi", "django", "flask"],
            "api": ["rest", "http", "endpoint", "service", "backend"],
            "backend": ["server", "service", "api", "database", "python", "go", "fastapi"],
            "frontend": ["ui", "client", "web", "react", "browser"],
            "cloud": ["infrastructure", "deploy", "serverless", "aws", "gcp", "azure"],
            "database": ["storage", "query", "sql", "postgres", "mysql", "data"],
            "container": ["docker", "image", "service", "deploy"],
        }

    @property
    def model_name(self) -> str:
        return "deterministic-feature-v1"

    @property
    def dimension(self) -> int:
        return self._dim

    def _embed_single_sync(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self._dim

        tokens = re.findall(r"\b[a-zA-Z0-9_\-\+#\.]+\b", text.lower())
        if not tokens:
            return [0.0] * self._dim

        vec = [0.0] * self._dim

        # 1. Primary token feature hashing
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) == 1 else -1.0
            vec[idx] += sign * 1.5

            # 2. Character 3-grams for subword matching
            if len(tok) >= 3:
                for i in range(len(tok) - 2):
                    tri = tok[i:i+3]
                    h_tri = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16)
                    idx_tri = h_tri % self._dim
                    sign_tri = 1.0 if ((h_tri >> 8) & 1) == 1 else -1.0
                    vec[idx_tri] += sign_tri * 0.5

            # 3. Semantic expansion projection
            if tok in self._synonym_map:
                for syn in self._synonym_map[tok]:
                    h_syn = int(hashlib.md5(syn.encode("utf-8")).hexdigest(), 16)
                    idx_syn = h_syn % self._dim
                    sign_syn = 1.0 if ((h_syn >> 8) & 1) == 1 else -1.0
                    vec[idx_syn] += sign_syn * 0.75

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [x / norm for x in vec]
        return [0.0] * self._dim

    async def embed_text(self, text: str) -> List[float]:
        return self._embed_single_sync(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single_sync(t) for t in texts]


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google GenAI Embedding Provider using text-embedding-004.
    Requires GEMINI_API_KEY. Falls back gracefully on error.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self._client = None
        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception:
                self._client = None

    @property
    def model_name(self) -> str:
        return "text-embedding-004"

    @property
    def dimension(self) -> int:
        return 768

    async def embed_text(self, text: str) -> List[float]:
        if not self._client:
            raise RuntimeError("GeminiEmbeddingProvider: client not configured or GEMINI_API_KEY missing.")
        
        response = self._client.models.embed_content(
            model=self.model_name,
            contents=text,
        )
        embedding = response.embeddings[0].values
        # L2-normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        return [x / norm for x in embedding] if norm > 0 else embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._client:
            raise RuntimeError("GeminiEmbeddingProvider: client not configured.")
        return [await self.embed_text(t) for t in texts]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock Embedding Provider for unit tests, failure simulation, and fixed vector testing."""

    def __init__(
        self,
        dimension: int = 128,
        model_name: str = "mock-embedding-v1",
        should_fail: bool = False,
        fixed_vectors: Optional[Dict[str, List[float]]] = None,
    ):
        self._dimension = dimension
        self._model_name = model_name
        self.should_fail = should_fail
        self.fixed_vectors = fixed_vectors or {}
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> List[float]:
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("MockEmbeddingProvider simulated failure")
        if text in self.fixed_vectors:
            return self.fixed_vectors[text]
        # Return deterministic dummy unit vector based on text length
        vec = [0.0] * self._dimension
        idx = len(text) % self._dimension
        vec[idx] = 1.0
        return vec

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [await self.embed_text(t) for t in texts]


def get_embedding_provider(name: Optional[str] = None) -> BaseEmbeddingProvider:
    """
    Factory function for obtaining the active EmbeddingProvider.
    Defaults to Gemini if configured, otherwise DeterministicFeatureEmbeddingProvider.
    """
    target = name.lower() if name else "auto"
    if target == "gemini" or (target == "auto" and getattr(settings, "GEMINI_API_KEY", "")):
        try:
            return GeminiEmbeddingProvider()
        except Exception:
            pass
    return DeterministicFeatureEmbeddingProvider()
