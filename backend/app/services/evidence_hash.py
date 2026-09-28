"""Deterministic hashing of live workspace candidate evidence.

Used to detect when a user's workspace has changed since a targeted resume
variant was generated or last synced, without persisting a copy of the
evidence on the variant itself.
"""

import hashlib
import json

from app.schemas.candidate import CandidateEvidence


def compute_workspace_evidence_hash(evidence: CandidateEvidence) -> str:
    """
    Computes a stable SHA-256 hex digest over the workspace candidate evidence.

    Serializes with camelCase aliases, sorted keys, and str() coercion for
    non-JSON-native values so the hash is deterministic across identical
    evidence payloads regardless of object identity or construction order.
    """
    payload = json.dumps(
        evidence.model_dump(by_alias=True),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
