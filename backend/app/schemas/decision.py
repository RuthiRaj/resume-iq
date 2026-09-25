"""
AI Abstention & Multi-Dimensional Confidence Schemas for ResumeIQ (Phase 4.0.5)

Defines strongly-typed, deterministic Pydantic v2 contracts for:
- ConfidenceBreakdown: Multi-factor confidence metrics across independent architectural layers
- DecisionType: Deterministic ternary classification (ACCEPT, REVIEW, ABSTAIN)
- AIAbstentionDecision: Explainable, auditable safety decision with provenance and reasoning
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.ai.retrieval.hybrid_matcher import MatchClass

DecisionType = Literal["ACCEPT", "REVIEW", "ABSTAIN"]


class ConfidenceBreakdown(BaseModel):
    """
    Multi-dimensional confidence scores across distinct, decoupled architectural layers.
    Never conflates retrieval relevance or semantic similarity with factual truth.
    All scalar values are deterministic and bounded strictly to [0.0, 1.0].
    """
    evidence_strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        alias="evidenceStrength",
        description="Factual trustworthiness of workspace evidence, respecting VerificationStatus (verified=1.0, unverified=0.5, missing=0.0)",
    )
    retrieval_relevance: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        alias="retrievalRelevance",
        description="Hybrid retrieval score (0.60 canonical + 0.40 dense semantic) matching evidence to target requirement",
    )
    grounding_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        alias="groundingConfidence",
        description="Degree to which generated claim is strictly grounded in candidate workspace facts without mutation or ungrounded tokens",
    )
    claim_safety: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        alias="claimSafety",
        description="Deterministic ClaimValidator safety score (1.0 for valid claims, 0.0 for metric/scope/outcome/tech violations)",
    )
    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        alias="overallConfidence",
        description="Weighted aggregate confidence for decision support: 0.30*EvStrength + 0.25*RetRelevance + 0.25*Grounding + 0.20*Safety. NEVER overrides hard safety failures.",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AIAbstentionDecision(BaseModel):
    """
    Authoritative, deterministic safety and abstention decision for a target requirement or resume claim.
    Provides explicit reasoning, candidate review prompts, and negative prohibited directives.
    """
    decision: DecisionType = Field(
        ...,
        description="Deterministic outcome: ACCEPT (safe to assert), REVIEW (requires user confirmation), ABSTAIN (hard safety prohibition)",
    )
    confidence: ConfidenceBreakdown = Field(
        ...,
        description="Granular multi-dimensional confidence breakdown",
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Deterministic human-readable justifications explaining the decision",
    )
    review_prompts: List[str] = Field(
        default_factory=list,
        alias="reviewPrompts",
        description="Structured candidate review prompts when decision is REVIEW",
    )
    prohibited_claims: List[str] = Field(
        default_factory=list,
        alias="prohibitedClaims",
        description="Strict negative directives preventing generator from asserting ungrounded claims",
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        alias="evidenceIds",
        description="Workspace EvidenceItem IDs evaluated for this decision",
    )
    requirement: Optional[str] = Field(
        default=None,
        description="Target job requirement or skill name evaluated",
    )
    match_class: Optional[MatchClass] = Field(
        default=None,
        alias="matchClass",
        description="Retrieval match classification from HybridMatcher",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional diagnostic metadata or audit tracing info",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
