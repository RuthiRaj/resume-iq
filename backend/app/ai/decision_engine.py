"""
AI Abstention & Decision Engine for ResumeIQ (Phase 4.0.5)

Deterministic, multi-dimensional safety and abstention engine.
Evaluates candidate evidence, hybrid retrieval matches, and post-generation claim validation
to produce transparent, reproducible ACCEPT / REVIEW / ABSTAIN decisions.

Key Invariants:
1. Multi-Dimensional Confidence: Evaluates Evidence Strength, Retrieval Relevance,
   Grounding Confidence, and Claim Safety as independent dimensions.
2. Hard Safety Precedence: Hard safety failures (tenant mismatch, missing evidence,
   unsupported metrics, scope inflation, prompt injection) ALWAYS trigger ABSTAIN,
   and CANNOT be overridden by numerical overall confidence.
3. Zero Statistical Fabrications: Scores are deterministic decision-support metrics,
   never falsely represented as statistically calibrated probabilities.
"""

from typing import List, Dict, Optional, Set, Any, Tuple
from app.schemas.evidence import EvidenceItem, VerificationStatus
from app.schemas.remediation import ValidationResult, UnsupportedClaim
from app.schemas.decision import ConfidenceBreakdown, AIAbstentionDecision, DecisionType
from app.ai.retrieval.hybrid_matcher import MatchClass, RequirementMatchResult

# Multi-factor confidence weights (strictly sum to 1.00)
WEIGHT_EVIDENCE_STRENGTH = 0.30
WEIGHT_RETRIEVAL_RELEVANCE = 0.25
WEIGHT_GROUNDING_CONFIDENCE = 0.25
WEIGHT_CLAIM_SAFETY = 0.20

# Decision policy thresholds
ACCEPT_CONFIDENCE_THRESHOLD = 0.85
REVIEW_CONFIDENCE_THRESHOLD = 0.60


class DecisionEngine:
    """
    Deterministic Decision Engine enforcing safe AI resume generation and claim assertion.
    """

    @staticmethod
    def compute_overall_confidence(
        evidence_strength: float,
        retrieval_relevance: float,
        grounding_confidence: float,
        claim_safety: float,
    ) -> float:
        """
        Computes weighted aggregate confidence for decision support.
        Formula:
          0.30 * EvidenceStrength + 0.25 * RetrievalRelevance + 0.25 * GroundingConfidence + 0.20 * ClaimSafety
        Note: Overall confidence NEVER overrides hard safety constraints.
        """
        raw = (
            (evidence_strength * WEIGHT_EVIDENCE_STRENGTH)
            + (retrieval_relevance * WEIGHT_RETRIEVAL_RELEVANCE)
            + (grounding_confidence * WEIGHT_GROUNDING_CONFIDENCE)
            + (claim_safety * WEIGHT_CLAIM_SAFETY)
        )
        return round(max(0.0, min(1.0, raw)), 4)

    @classmethod
    def evaluate_decision(
        cls,
        requirement: Optional[str] = None,
        match_class: Optional[MatchClass] = None,
        matched_technology: Optional[str] = None,
        evidence_items: Optional[List[EvidenceItem]] = None,
        validation_result: Optional[ValidationResult] = None,
        retrieval_score: float = 1.0,
        auth_context: Optional[Dict[str, str]] = None,
        has_conflicting_evidence: bool = False,
        is_prompt_injection_detected: bool = False,
    ) -> AIAbstentionDecision:
        """
        Deterministically evaluates evidence, retrieval classification, and claim validation
        to produce an AIAbstentionDecision with full justification.
        """
        reasons: List[str] = []
        review_prompts: List[str] = []
        prohibited_claims: List[str] = []
        evidence_ids: List[str] = [i.evidence_id for i in (evidence_items or [])]

        # Base dimensional scores
        evidence_strength = 1.0
        retrieval_relevance = max(0.0, min(1.0, float(retrieval_score)))
        grounding_confidence = 1.0
        claim_safety = 1.0

        auth_ctx = auth_context or {}
        resource_owner = auth_ctx.get("resourceOwnerUid")
        evaluating_uid = auth_ctx.get("evaluatingUid")

        # =========================================================================
        # 1. HARD SAFETY PRECEDENCE: Multi-Tenant Security & Isolation Check
        # =========================================================================
        if resource_owner and evaluating_uid and resource_owner != evaluating_uid:
            claim_safety = 0.0
            grounding_confidence = 0.0
            evidence_strength = 0.0
            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="ABSTAIN",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=[
                    f"Multi-tenant isolation violation: evaluating UID '{evaluating_uid}' does not match resource owner '{resource_owner}'."
                ],
                reviewPrompts=[],
                prohibitedClaims=["Access to foreign tenant evidence is strictly prohibited."],
                evidenceIds=[],
                requirement=requirement,
                matchClass="missing",
            )

        # Cross-tenant item ownership check
        if evaluating_uid and evidence_items:
            for item in evidence_items:
                if item.user_id and item.user_id != evaluating_uid:
                    claim_safety = 0.0
                    grounding_confidence = 0.0
                    evidence_strength = 0.0
                    overall_conf = cls.compute_overall_confidence(
                        evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
                    )
                    return AIAbstentionDecision(
                        decision="ABSTAIN",
                        confidence=ConfidenceBreakdown(
                            evidenceStrength=evidence_strength,
                            retrievalRelevance=retrieval_relevance,
                            groundingConfidence=grounding_confidence,
                            claimSafety=claim_safety,
                            overallConfidence=overall_conf,
                        ),
                        reasons=[
                            f"Multi-tenant isolation violation: evidence item '{item.evidence_id}' belongs to user '{item.user_id}', not '{evaluating_uid}'."
                        ],
                        reviewPrompts=[],
                        prohibitedClaims=["Access to foreign tenant evidence is strictly prohibited."],
                        evidenceIds=[],
                        requirement=requirement,
                        matchClass="missing",
                    )

        # =========================================================================
        # 2. HARD SAFETY PRECEDENCE: Adversarial Prompt Injection
        # =========================================================================
        if is_prompt_injection_detected:
            claim_safety = 0.0
            grounding_confidence = 0.0
            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="ABSTAIN",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=["Adversarial prompt injection attempt detected in input stream."],
                reviewPrompts=[],
                prohibitedClaims=["Execution or assertion of injected instructions is strictly prohibited."],
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass=match_class,
            )

        # =========================================================================
        # 3. HARD SAFETY PRECEDENCE: Post-Generation Claim Validation Failure
        # =========================================================================
        if validation_result and not validation_result.is_valid:
            claim_safety = 0.0
            grounding_confidence = 0.0
            reasons.extend(c.reason for c in validation_result.unsupported_claims)
            review_prompts.extend(
                c.prompt_for_user for c in validation_result.unsupported_claims if c.prompt_for_user
            )
            for c in validation_result.unsupported_claims:
                prohibited_claims.append(f"Do not claim unsupported {c.category or 'fact'}: '{c.claim_text}'")

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="ABSTAIN",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons or ["Claim validation failed: ungrounded tokens or metrics detected."],
                reviewPrompts=review_prompts,
                prohibitedClaims=prohibited_claims,
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass=match_class,
            )

        # =========================================================================
        # 4. HARD SAFETY PRECEDENCE: Missing Evidence / Hard Gaps
        # =========================================================================
        if match_class == "missing" or (not evidence_items and not match_class):
            evidence_strength = 0.0
            grounding_confidence = 0.0
            retrieval_relevance = 0.0
            reasons.append(f"No verified evidence found in candidate workspace for requirement '{requirement or 'unspecified'}'.")
            prohibited_claims.append(f"Do not fabricate or assert experience for missing requirement '{requirement or 'unspecified'}'.")

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="ABSTAIN",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons,
                reviewPrompts=[],
                prohibitedClaims=prohibited_claims,
                evidenceIds=[],
                requirement=requirement,
                matchClass="missing",
            )

        # =========================================================================
        # 5. REVIEW CONDITION: Related-but-Unverified Technology Cluster
        # =========================================================================
        if match_class == "related_but_unverified":
            evidence_strength = 0.40
            grounding_confidence = 0.30
            retrieval_relevance = min(retrieval_relevance, 0.75)
            rel_tech = matched_technology or "related technology"
            reasons.append(
                f"Candidate demonstrates related experience with '{rel_tech}', but '{requirement}' is not verified in workspace."
            )
            review_prompts.append(
                f"Do you have direct verified experience with {requirement}? Your profile currently verifies {rel_tech}."
            )
            prohibited_claims.append(
                f"Do not claim direct experience with {requirement} without candidate confirmation."
            )

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="REVIEW",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons,
                reviewPrompts=review_prompts,
                prohibitedClaims=prohibited_claims,
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass="related_but_unverified",
            )

        # =========================================================================
        # 6. REVIEW CONDITION: Unverified Evidence Items / Ingestion Drafts
        # =========================================================================
        has_unverified = bool(
            evidence_items and any(i.verification_status == "unverified" for i in evidence_items)
        )
        if has_unverified:
            evidence_strength = 0.50
            grounding_confidence = 0.60
            reasons.append("Evidence item is unverified and requires candidate confirmation before assertion.")
            review_prompts.append("Please review and confirm this unverified draft evidence item in your workspace.")

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="REVIEW",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons,
                reviewPrompts=review_prompts,
                prohibitedClaims=[],
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass=match_class or "direct_match",
            )

        # =========================================================================
        # 7. REVIEW CONDITION: User Confirmation Required (Standalone Skill Tag)
        # =========================================================================
        if match_class == "user_confirmation_required":
            evidence_strength = 0.70
            grounding_confidence = 0.70
            reasons.append(
                f"'{requirement}' is listed as a skill tag in workspace, but lacks accomplishment bullets or project evidence."
            )
            review_prompts.append(
                f"Please add narrative project or work experience demonstrating your use of {requirement}."
            )

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="REVIEW",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons,
                reviewPrompts=review_prompts,
                prohibitedClaims=[],
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass="user_confirmation_required",
            )

        # =========================================================================
        # 8. REVIEW CONDITION: Conflicting Evidence Across Workspace
        # =========================================================================
        if has_conflicting_evidence:
            evidence_strength = 0.50
            grounding_confidence = 0.50
            reasons.append("Conflicting evidence detected across workspace items.")
            review_prompts.append("Please reconcile conflicting dates, titles, or metrics across your workspace items.")

            overall_conf = cls.compute_overall_confidence(
                evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
            )
            return AIAbstentionDecision(
                decision="REVIEW",
                confidence=ConfidenceBreakdown(
                    evidenceStrength=evidence_strength,
                    retrievalRelevance=retrieval_relevance,
                    groundingConfidence=grounding_confidence,
                    claimSafety=claim_safety,
                    overallConfidence=overall_conf,
                ),
                reasons=reasons,
                reviewPrompts=review_prompts,
                prohibitedClaims=[],
                evidenceIds=evidence_ids,
                requirement=requirement,
                matchClass=match_class,
            )

        # =========================================================================
        # 9. EVALUATE POSITIVE EVIDENCE CONFIDENCE & DECISION POLICY
        # =========================================================================
        if evidence_items:
            # Aggregate item-level confidence
            min_item_conf = min(float(i.confidence) for i in evidence_items)
            evidence_strength = min_item_conf

        overall_conf = cls.compute_overall_confidence(
            evidence_strength, retrieval_relevance, grounding_confidence, claim_safety
        )

        if overall_conf >= ACCEPT_CONFIDENCE_THRESHOLD and evidence_strength >= 0.85 and claim_safety == 1.0:
            decision: DecisionType = "ACCEPT"
            reasons.append(
                f"Verified direct evidence found for '{requirement or 'requirement'}' with high grounding confidence."
            )
        elif overall_conf >= REVIEW_CONFIDENCE_THRESHOLD:
            decision = "REVIEW"
            reasons.append("Borderline evidence confidence requires candidate confirmation.")
            review_prompts.append(
                f"Please review and verify the accuracy of your evidence supporting '{requirement or 'this claim'}'."
            )
        else:
            decision = "ABSTAIN"
            reasons.append("Insufficient evidence confidence to support claim safely.")
            prohibited_claims.append(f"Do not assert claim for '{requirement or 'requirement'}' due to low confidence.")

        return AIAbstentionDecision(
            decision=decision,
            confidence=ConfidenceBreakdown(
                evidenceStrength=evidence_strength,
                retrievalRelevance=retrieval_relevance,
                groundingConfidence=grounding_confidence,
                claimSafety=claim_safety,
                overallConfidence=overall_conf,
            ),
            reasons=reasons,
            reviewPrompts=review_prompts,
            prohibitedClaims=prohibited_claims,
            evidenceIds=evidence_ids,
            requirement=requirement,
            matchClass=match_class or "direct_match",
        )
