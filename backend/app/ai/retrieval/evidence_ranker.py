import re
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.evidence import EvidenceItem
from app.ai.skills import normalize_skill_name

# Multi-factor ranking weights (strictly sum to 1.00)
WEIGHT_REQUIRED_SKILL = 0.35
WEIGHT_ROLE_RELEVANCE = 0.20
WEIGHT_KEYWORD_OVERLAP = 0.15
WEIGHT_ACHIEVEMENT_METRICS = 0.15
WEIGHT_RECENCY = 0.10
WEIGHT_CONFIDENCE = 0.05

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
    "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were",
    "will", "with", "or", "our", "you", "your", "we", "they", "this", "but",
}


def _extract_keywords(text: str) -> Set[str]:
    """Extracts normalized alphanumeric keywords from text, ignoring stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\+#\.]+\b", text.lower())
    return {
        t for t in tokens
        if len(t) > 1 and t not in STOPWORDS
    }


def _compute_recency_score(dates_str: Optional[str]) -> float:
    """
    Computes a deterministic recency score in [0.0, 1.0].
    'Present' or recent years score 1.0; older entries scale downward gracefully.
    """
    if not dates_str:
        return 0.5  # Neutral default for undated projects/skills
    clean = dates_str.lower()
    if "present" in clean or "current" in clean:
        return 1.0

    # Extract 4-digit years
    years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", dates_str)]
    if not years:
        return 0.5

    max_year = max(years)
    current_year = 2026
    diff = max(0, current_year - max_year)
    if diff == 0:
        return 1.0
    elif diff <= 2:
        return 0.9
    elif diff <= 4:
        return 0.7
    elif diff <= 6:
        return 0.5
    else:
        return 0.3


class RankedEvidenceItem(BaseModel):
    """
    Individual evidence item scored and ranked across multi-factor criteria.
    """
    evidence_item: EvidenceItem = Field(..., alias="evidenceItem")
    rank_score: float = Field(..., ge=0.0, le=1.0, alias="rankScore")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, alias="scoreBreakdown")
    matched_skills: List[str] = Field(default_factory=list, alias="matchedSkills")
    matched_keywords: List[str] = Field(default_factory=list, alias="matchedKeywords")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvidenceRanker:
    """
    Multi-Factor Deterministic Evidence Ranking Engine for ResumeIQ.
    Ranks workspace evidence items based on transparent, reproducible criteria.
    """

    @classmethod
    def score_item(
        cls,
        item: EvidenceItem,
        target_role_keywords: Set[str],
        jd_keywords: Set[str],
        must_have_skills: Set[str],
        direct_matched_evidence_ids: Optional[Set[str]] = None,
        semantic_scores: Optional[Dict[str, float]] = None,
    ) -> RankedEvidenceItem:
        """Computes the multi-factor weighted score for a single EvidenceItem."""
        item_text = f"{item.title} {item.description} {' '.join(item.responsibilities)} {' '.join(item.achievements)} {' '.join(item.skills)} {' '.join(item.technologies)}"
        item_tokens = _extract_keywords(item_text)

        # 1. Required Skill Coverage Score
        matched_skills: List[str] = []
        is_direct_matched = bool(direct_matched_evidence_ids and item.evidence_id in direct_matched_evidence_ids)

        if must_have_skills:
            item_tech_and_skills = {normalize_skill_name(s).lower() for s in (item.skills + item.technologies)}
            for req in must_have_skills:
                norm_req = normalize_skill_name(req).lower()
                if norm_req in item_tech_and_skills or any(norm_req in tok for tok in item_tokens):
                    matched_skills.append(req)
            base_skill_score = len(matched_skills) / max(1, len(must_have_skills))
            if is_direct_matched:
                skill_score = min(1.0, max(base_skill_score, 0.8))
            else:
                skill_score = min(1.0, base_skill_score)
        else:
            if is_direct_matched:
                skill_score = 1.0
            else:
                skill_score = 0.5  # Neutral if no explicit must-haves provided

        # 2. Role Relevance Score
        matched_role_kws = target_role_keywords & _extract_keywords(f"{item.title} {item.role}")
        role_score = min(1.0, len(matched_role_kws) / max(1, len(target_role_keywords))) if target_role_keywords else 0.5

        # 3. Keyword Overlap Score (blended with semantic score if available)
        matched_jd_kws = jd_keywords & item_tokens
        base_kw_score = min(1.0, len(matched_jd_kws) / max(1, len(jd_keywords))) if jd_keywords else 0.5
        
        sem_score = semantic_scores.get(item.evidence_id) if semantic_scores else None
        if sem_score is not None:
            keyword_score = min(1.0, (base_kw_score * 0.5) + (sem_score * 0.5))
        else:
            keyword_score = base_kw_score

        # 4. Achievement & Metrics Strength Score
        metrics_count = len(item.metrics)
        if metrics_count >= 2:
            metrics_score = 1.0
        elif metrics_count == 1:
            metrics_score = 0.7
        else:
            metrics_score = 0.2

        # 5. Recency Score
        recency_score = _compute_recency_score(item.dates)

        # 6. Confidence Score
        confidence_score = float(item.confidence)

        # Total Weighted Score
        total_score = (
            (skill_score * WEIGHT_REQUIRED_SKILL)
            + (role_score * WEIGHT_ROLE_RELEVANCE)
            + (keyword_score * WEIGHT_KEYWORD_OVERLAP)
            + (metrics_score * WEIGHT_ACHIEVEMENT_METRICS)
            + (recency_score * WEIGHT_RECENCY)
            + (confidence_score * WEIGHT_CONFIDENCE)
        )
        total_score = round(max(0.0, min(1.0, total_score)), 4)

        breakdown = {
            "requiredSkills": round(skill_score, 4),
            "roleRelevance": round(role_score, 4),
            "keywordOverlap": round(keyword_score, 4),
            "metricsStrength": round(metrics_score, 4),
            "recency": round(recency_score, 4),
            "confidence": round(confidence_score, 4),
        }
        if sem_score is not None:
            breakdown["semanticRelevance"] = round(sem_score, 4)

        return RankedEvidenceItem(
            evidenceItem=item,
            rankScore=total_score,
            scoreBreakdown=breakdown,
            matchedSkills=sorted(list(set(matched_skills))),
            matchedKeywords=sorted(list(matched_role_kws | matched_jd_kws)),
        )

    @classmethod
    def rank_evidence(
        cls,
        items: List[EvidenceItem],
        target_role: str,
        job_description: Optional[str] = "",
        must_have_skills: Optional[List[str]] = None,
        direct_matched_evidence_ids: Optional[Set[str]] = None,
        semantic_scores: Optional[Dict[str, float]] = None,
    ) -> List[RankedEvidenceItem]:
        """
        Ranks a collection of EvidenceItems against a target role and JD.
        Returns a sorted list of RankedEvidenceItems (highest rank_score first).
        """
        role_kws = _extract_keywords(target_role)
        jd_kws = _extract_keywords(job_description or "")
        req_skills = set(must_have_skills or [])

        scored_items = [
            cls.score_item(
                item=item,
                target_role_keywords=role_kws,
                jd_keywords=jd_kws,
                must_have_skills=req_skills,
                direct_matched_evidence_ids=direct_matched_evidence_ids,
                semantic_scores=semantic_scores,
            )
            for item in items
        ]

        scored_items.sort(key=lambda x: x.rank_score, reverse=True)
        return scored_items
