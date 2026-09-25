"""
Resume Planning Service for ResumeIQ

Implements the Standalone Resume Planning Layer:
Evidence Ranking -> Resume Planning -> Resume Generation.

This service is 100% deterministic (no LLM, no database writes).
It consumes structured job requirements, candidate evidence, and ranking scores
to construct an authoritative ResumePlan contract.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Set, Any, Tuple
from fastapi import HTTPException, status

from app.schemas.candidate import CandidateEvidence
from app.schemas.evidence import EvidenceItem
from app.schemas.job_description import StructuredJobDescription, SkillRequirement
from app.schemas.plan import (
    ResumePlan,
    SectionPlan,
    SelectedEvidenceItem,
    ExcludedEvidenceItem,
    PrioritizedSkill,
    HardGap,
    RequirementStrategy,
)
from app.schemas.decision import AIAbstentionDecision
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.ai.retrieval.hybrid_matcher import HybridMatcher, MatchClass, RequirementMatchResult
from app.ai.retrieval.evidence_ranker import EvidenceRanker, RankedEvidenceItem
from app.ai.decision_engine import DecisionEngine
from app.ai.skills import normalize_skill_name, normalize_skill_category
from app.ai.claim_validator import compute_candidate_experience_years


class ResumePlanningService:
    """
    Deterministic Resume Planning Engine.
    Produces an explicit ResumePlan specifying:
    - Target page budget and section ordering
    - Selected vs. excluded evidence with deterministic justifications
    - Prioritized skills and ATS keywords
    - Hard gaps and prohibited claims
    """

    @classmethod
    def create_resume_plan(
        cls,
        target_role: str,
        target_company: Optional[str] = "",
        candidate_evidence: Optional[CandidateEvidence] = None,
        normalized_items: Optional[List[EvidenceItem]] = None,
        evidence_graph: Optional[CareerEvidenceGraph] = None,
        structured_jd: Optional[StructuredJobDescription] = None,
        job_description_text: Optional[str] = "",
        user_id: str = "candidate",
        max_experience: Optional[int] = None,
        max_projects: Optional[int] = None,
        target_page_budget: Optional[int] = None,
    ) -> ResumePlan:
        """
        Deterministically builds an authoritative ResumePlan.
        """
        if not candidate_evidence:
            candidate_evidence = CandidateEvidence()

        # 1. Normalize workspace evidence if not provided
        if normalized_items is None:
            normalized_items = EvidenceService.normalize_candidate_evidence(
                user_id=user_id, evidence=candidate_evidence
            )

        # 2. Build or use CareerEvidenceGraph
        if evidence_graph is None:
            evidence_graph = CareerEvidenceGraph(user_id=user_id, items=normalized_items)

        # 3. Parse Job Description deterministically if not provided
        if structured_jd is None:
            structured_jd = HybridMatcher.parse_job_description_deterministic(
                target_role=target_role,
                job_description_text=job_description_text or "",
                target_company=target_company or "",
            )

        # 4. Execute Hybrid Requirement Matching against CareerEvidenceGraph
        match_response = HybridMatcher.match_job_requirements(structured_jd, evidence_graph)

        direct_matched_ids: Set[str] = set()
        must_have_skills_list: List[str] = []
        preferred_skills_list: List[str] = []

        for req in structured_jd.must_have_skills:
            must_have_skills_list.append(req.name)
        for req in structured_jd.preferred_skills:
            preferred_skills_list.append(req.name)

        missing_requirements: List[RequirementMatchResult] = []
        related_unverified: List[RequirementMatchResult] = []
        user_confirmation: List[RequirementMatchResult] = []
        direct_matches: List[RequirementMatchResult] = []

        for m in match_response.matches:
            if m.match_class == "direct_match":
                direct_matches.append(m)
                for eid in m.candidate_evidence_ids:
                    direct_matched_ids.add(eid)
            elif m.match_class == "user_confirmation_required":
                user_confirmation.append(m)
                for eid in m.candidate_evidence_ids:
                    direct_matched_ids.add(eid)
            elif m.match_class == "related_but_unverified":
                related_unverified.append(m)
            elif m.match_class == "missing":
                missing_requirements.append(m)

        # 5. Rank Evidence using Multi-Factor EvidenceRanker
        ranking_must_haves = must_have_skills_list if must_have_skills_list else preferred_skills_list
        ranked_items = EvidenceRanker.rank_evidence(
            items=normalized_items,
            target_role=target_role,
            job_description=job_description_text or "",
            must_have_skills=ranking_must_haves,
            direct_matched_evidence_ids=direct_matched_ids,
        )

        ranked_by_id: Dict[str, RankedEvidenceItem] = {
            r.evidence_item.evidence_id: r for r in ranked_items
        }

        # 6. Determine Target Page Budget & Capacity Constraints
        computed_years = compute_candidate_experience_years(candidate_evidence)
        total_exp_count = len(candidate_evidence.experience)
        total_proj_count = len(candidate_evidence.projects)

        if target_page_budget is not None:
            final_page_budget = max(1, min(5, target_page_budget))
        else:
            # Deterministic heuristic: 2 pages if 7+ years of experience or heavy content (>=4 exp & >=3 proj)
            if computed_years >= 7.0 or (total_exp_count >= 4 and total_proj_count >= 3):
                final_page_budget = 2
            else:
                final_page_budget = 1

        # Budget-driven capacity limits
        if final_page_budget >= 2:
            budget_max_exp = max_experience if max_experience is not None else 6
            budget_max_proj = max_projects if max_projects is not None else 4
        else:
            budget_max_exp = max_experience if max_experience is not None else 4
            budget_max_proj = max_projects if max_projects is not None else 3

        # 7. Partition Evidence into Selected vs. Excluded
        selected_evidence: List[SelectedEvidenceItem] = []
        excluded_evidence: List[ExcludedEvidenceItem] = []

        # Filter ranked experience and project items
        exp_ranked = [r for r in ranked_items if r.evidence_item.source_type == "experience"]
        proj_ranked = [r for r in ranked_items if r.evidence_item.source_type == "projects"]

        # Select top experience items up to capacity
        for idx, r in enumerate(exp_ranked):
            item = r.evidence_item
            if idx < budget_max_exp:
                match_str = f"matched skills: {', '.join(r.matched_skills)}" if r.matched_skills else "relevant experience"
                selected_evidence.append(
                    SelectedEvidenceItem(
                        evidenceId=item.evidence_id,
                        sourceType=item.source_type,
                        sourceItemId=item.source_item_id,
                        title=item.title,
                        rankScore=r.rank_score,
                        selectionReason=f"Ranked #{idx + 1} (score {r.rank_score:.2f}); {match_str}",
                        matchedSkills=r.matched_skills,
                    )
                )
            else:
                excluded_evidence.append(
                    ExcludedEvidenceItem(
                        evidenceId=item.evidence_id,
                        sourceType=item.source_type,
                        sourceItemId=item.source_item_id,
                        title=item.title,
                        rankScore=r.rank_score,
                        exclusionReason=f"Page budget constraint ({final_page_budget} page(s)); rank score {r.rank_score:.2f} is lower than top {budget_max_exp} selected experience items",
                    )
                )

        # Select top project items up to capacity
        for idx, r in enumerate(proj_ranked):
            item = r.evidence_item
            if idx < budget_max_proj:
                match_str = f"matched skills: {', '.join(r.matched_skills)}" if r.matched_skills else "demonstrates technical capability"
                selected_evidence.append(
                    SelectedEvidenceItem(
                        evidenceId=item.evidence_id,
                        sourceType=item.source_type,
                        sourceItemId=item.source_item_id,
                        title=item.title,
                        rankScore=r.rank_score,
                        selectionReason=f"Ranked #{idx + 1} (score {r.rank_score:.2f}); {match_str}",
                        matchedSkills=r.matched_skills,
                    )
                )
            else:
                excluded_evidence.append(
                    ExcludedEvidenceItem(
                        evidenceId=item.evidence_id,
                        sourceType=item.source_type,
                        sourceItemId=item.source_item_id,
                        title=item.title,
                        rankScore=r.rank_score,
                        exclusionReason=f"Page budget constraint ({final_page_budget} page(s)); rank score {r.rank_score:.2f} is lower than top {budget_max_proj} selected projects",
                    )
                )

        # Include other workspace items (Education, Certifications, Achievements)
        for r in ranked_items:
            item = r.evidence_item
            if item.source_type in ("education", "certifications", "achievements", "publications", "awards", "volunteering"):
                selected_evidence.append(
                    SelectedEvidenceItem(
                        evidenceId=item.evidence_id,
                        sourceType=item.source_type,
                        sourceItemId=item.source_item_id,
                        title=item.title,
                        rankScore=r.rank_score,
                        selectionReason=f"Standard credential/qualification in {item.source_type}",
                        matchedSkills=r.matched_skills,
                    )
                )

        selected_exp_ids = [s.evidence_id for s in selected_evidence if s.source_type == "experience"]
        selected_proj_ids = [s.evidence_id for s in selected_evidence if s.source_type == "projects"]
        selected_edu_ids = [s.evidence_id for s in selected_evidence if s.source_type == "education"]
        selected_cert_ids = [s.evidence_id for s in selected_evidence if s.source_type == "certifications"]
        selected_ach_ids = [s.evidence_id for s in selected_evidence if s.source_type == "achievements"]

        # 8. Skill & Keyword Prioritization
        seen_skill_names: Set[str] = set()
        prioritized_skills: List[PrioritizedSkill] = []

        match_by_name: Dict[str, RequirementMatchResult] = {
            m.requirement_name.lower(): m for m in match_response.matches
        }

        # Priority 1: Must-Have skills from JD
        for req in structured_jd.must_have_skills:
            norm_name = normalize_skill_name(req.name)
            key = norm_name.lower()
            if key in seen_skill_names:
                continue
            seen_skill_names.add(key)

            m_result = match_by_name.get(key)
            match_class: MatchClass = m_result.match_class if m_result else "missing"
            is_dem = match_class in ("direct_match", "user_confirmation_required")
            ev_ids = m_result.candidate_evidence_ids if m_result else []

            prioritized_skills.append(
                PrioritizedSkill(
                    name=norm_name,
                    category=normalize_skill_category(norm_name, req.category),
                    importance="MustHave",
                    matchClass=match_class,
                    isDirectlyDemonstrated=is_dem,
                    evidenceIds=ev_ids,
                )
            )

        # Priority 2: Preferred skills from JD
        for req in structured_jd.preferred_skills:
            norm_name = normalize_skill_name(req.name)
            key = norm_name.lower()
            if key in seen_skill_names:
                continue
            seen_skill_names.add(key)

            m_result = match_by_name.get(key)
            match_class: MatchClass = m_result.match_class if m_result else "missing"
            is_dem = match_class in ("direct_match", "user_confirmation_required")
            ev_ids = m_result.candidate_evidence_ids if m_result else []

            prioritized_skills.append(
                PrioritizedSkill(
                    name=norm_name,
                    category=normalize_skill_category(norm_name, req.category),
                    importance="Preferred",
                    matchClass=match_class,
                    isDirectlyDemonstrated=is_dem,
                    evidenceIds=ev_ids,
                )
            )

        # Priority 3: Candidate's other verified workspace skills
        for s in candidate_evidence.skills:
            norm_name = normalize_skill_name(s.name)
            key = norm_name.lower()
            if key in seen_skill_names:
                continue
            seen_skill_names.add(key)

            matching_ev = evidence_graph.find_by_skill(norm_name)
            ev_ids = [e.evidence_id for e in matching_ev]

            prioritized_skills.append(
                PrioritizedSkill(
                    name=norm_name,
                    category=normalize_skill_category(norm_name, s.category or "Other"),
                    importance="Unspecified",
                    matchClass="direct_match" if ev_ids else "user_confirmation_required",
                    isDirectlyDemonstrated=True,
                    evidenceIds=ev_ids,
                )
            )

        # Construct Prioritized ATS Keywords
        prioritized_keywords: List[str] = []
        seen_kws: Set[str] = set()

        for kw in (structured_jd.technical_stack + structured_jd.tools + structured_jd.domain_terminology + structured_jd.keywords):
            cleaned_kw = kw.strip()
            if cleaned_kw and cleaned_kw.lower() not in seen_kws:
                seen_kws.add(cleaned_kw.lower())
                prioritized_keywords.append(cleaned_kw)

        for s in prioritized_skills:
            if s.name.lower() not in seen_kws:
                seen_kws.add(s.name.lower())
                prioritized_keywords.append(s.name)

        # 9. Hard Gaps & Prohibited Claims
        hard_gaps: List[HardGap] = []
        for m in missing_requirements:
            hard_gaps.append(
                HardGap(
                    requirementName=m.requirement_name,
                    category=m.category,
                    gapType="MissingEvidence",
                    reason=m.explanation or f"No verified evidence found in candidate workspace for '{m.requirement_name}'.",
                    prohibitedClaimInstruction=f"Do not claim or imply experience with '{m.requirement_name}' unless independently supported by verified workspace evidence.",
                )
            )

        related_but_unverified_reqs = [m.requirement_name for m in related_unverified]
        user_confirmation_reqs = [m.requirement_name for m in user_confirmation]

        # 10. Construct Section Plans & Ordering
        sections: List[SectionPlan] = [
            SectionPlan(
                sectionName="Header",
                included=True,
                selectedEvidenceIds=[],
                priority=1,
                order=1,
                rationale="Candidate identity and contact details",
            ),
            SectionPlan(
                sectionName="Summary",
                included=True,
                selectedEvidenceIds=[],
                priority=1,
                order=2,
                rationale=f"Tailored professional summary aligned with target role '{target_role}'",
            ),
            SectionPlan(
                sectionName="Skills",
                included=len(prioritized_skills) > 0,
                selectedEvidenceIds=[s.name for s in prioritized_skills],
                priority=2,
                order=3,
                rationale=f"Prioritized technical skills ({len(prioritized_skills)} planned)",
            ),
            SectionPlan(
                sectionName="Experience",
                included=len(selected_exp_ids) > 0,
                selectedEvidenceIds=selected_exp_ids,
                priority=1,
                order=4,
                rationale=f"Selected {len(selected_exp_ids)} most relevant professional experience entries based on multi-factor ranking",
            ),
            SectionPlan(
                sectionName="Projects",
                included=len(selected_proj_ids) > 0,
                selectedEvidenceIds=selected_proj_ids,
                priority=2,
                order=5,
                rationale=f"Selected {len(selected_proj_ids)} technical projects highlighting relevant domain capabilities",
            ),
            SectionPlan(
                sectionName="Education",
                included=len(selected_edu_ids) > 0,
                selectedEvidenceIds=selected_edu_ids,
                priority=3,
                order=6,
                rationale="Academic background and degrees",
            ),
            SectionPlan(
                sectionName="Certifications",
                included=len(selected_cert_ids) > 0,
                selectedEvidenceIds=selected_cert_ids,
                priority=3,
                order=7,
                rationale="Verified professional certifications",
            ),
            SectionPlan(
                sectionName="Achievements",
                included=len(selected_ach_ids) > 0,
                selectedEvidenceIds=selected_ach_ids,
                priority=4,
                order=8,
                rationale="Notable awards and verified achievements",
            ),
        ]

        section_order = [s.section_name for s in sections if s.included]

        # 11. Requirement Strategy
        focus_areas = [s.name for s in prioritized_skills if s.importance == "MustHave" and s.is_directly_demonstrated][:4]
        if not focus_areas:
            focus_areas = [s.name for s in prioritized_skills if s.is_directly_demonstrated][:4]

        req_strategy = RequirementStrategy(
            focusAreas=focus_areas,
            summaryTheme=f"Highlight verified expertise in {', '.join(focus_areas) if focus_areas else target_role} tailored for {target_role}.",
            highlightedDomains=structured_jd.domain_terminology[:5],
            notes=[
                f"Page budget: {final_page_budget} page(s)",
                f"Direct matches: {len(direct_matches)}, Hard gaps: {len(hard_gaps)}",
            ],
        )

        # 12. Evaluate Deterministic Abstention Decisions for Requirements
        abstention_decisions: List[AIAbstentionDecision] = []
        for m in match_response.matches:
            ev_items = [
                evidence_graph._items_by_id[eid]
                for eid in m.candidate_evidence_ids
                if eid in evidence_graph._items_by_id
            ]
            decision = DecisionEngine.evaluate_decision(
                requirement=m.requirement_name,
                match_class=m.match_class,
                matched_technology=m.matched_technology,
                evidence_items=ev_items,
                retrieval_score=m.confidence,
                auth_context={"evaluatingUid": user_id, "resourceOwnerUid": user_id} if user_id else None,
            )
            abstention_decisions.append(decision)

        now_iso = datetime.now(timezone.utc).isoformat()
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"

        plan = ResumePlan(
            planId=plan_id,
            userId=user_id,
            targetRole=target_role,
            targetCompany=target_company or "",
            targetPageBudget=final_page_budget,
            sectionOrder=section_order,
            sections=sections,
            selectedEvidence=selected_evidence,
            excludedEvidence=excluded_evidence,
            prioritizedSkills=prioritized_skills,
            prioritizedKeywords=prioritized_keywords,
            requirementStrategy=req_strategy,
            hardGaps=hard_gaps,
            relatedButUnverifiedRequirements=related_but_unverified_reqs,
            userConfirmationRequired=user_confirmation_reqs,
            abstentionDecisions=abstention_decisions,
            planningMetadata={
                "directMatchCount": len(direct_matches),
                "hardGapCount": len(hard_gaps),
                "relatedUnverifiedCount": len(related_unverified),
                "userConfirmationCount": len(user_confirmation),
                "abstentionDecisionCount": len(abstention_decisions),
                "selectedExperienceCount": len(selected_exp_ids),
                "selectedProjectsCount": len(selected_proj_ids),
                "totalNormalizedItems": len(normalized_items),
                "experienceYearsComputed": computed_years,
            },
            createdAt=now_iso,
        )

        return plan

    @classmethod
    def validate_resume_plan(
        cls,
        plan: ResumePlan,
        candidate_items: List[EvidenceItem],
        expected_user_id: Optional[str] = None,
    ) -> bool:
        """
        Validates the ResumePlan contract deterministically against candidate evidence:
        1. Verifies ownership boundary (user isolation).
        2. Verifies that all selected evidence IDs exist and belong to the candidate.
        3. Verifies that all excluded evidence IDs exist and belong to the candidate.
        4. Verifies no duplicate IDs within selected evidence.
        5. Verifies target page budget and section order are valid.
        Raises ValueError on validation failure.
        """
        if expected_user_id:
            if plan.user_id and plan.user_id != expected_user_id:
                raise ValueError(
                    f"ResumePlan validation failed: Plan owner '{plan.user_id}' does not match expected user '{expected_user_id}'."
                )

        valid_items_map: Dict[str, EvidenceItem] = {item.evidence_id: item for item in candidate_items}

        # 1. Selected Evidence Validation
        seen_selected: Set[str] = set()
        for item in plan.selected_evidence:
            if item.evidence_id not in valid_items_map:
                raise ValueError(
                    f"ResumePlan validation failed: Selected evidence ID '{item.evidence_id}' does not exist in candidate evidence."
                )
            if expected_user_id and valid_items_map[item.evidence_id].user_id != expected_user_id:
                raise ValueError(
                    f"ResumePlan validation failed: Selected evidence ID '{item.evidence_id}' belongs to another user."
                )
            if item.evidence_id in seen_selected:
                raise ValueError(
                    f"ResumePlan validation failed: Duplicate selected evidence ID '{item.evidence_id}'."
                )
            seen_selected.add(item.evidence_id)

        # 2. Excluded Evidence Validation
        for item in plan.excluded_evidence:
            if item.evidence_id not in valid_items_map:
                raise ValueError(
                    f"ResumePlan validation failed: Excluded evidence ID '{item.evidence_id}' does not exist in candidate evidence."
                )
            if expected_user_id and valid_items_map[item.evidence_id].user_id != expected_user_id:
                raise ValueError(
                    f"ResumePlan validation failed: Excluded evidence ID '{item.evidence_id}' belongs to another user."
                )

        # 3. Page budget & Section order validation
        if plan.target_page_budget < 1 or plan.target_page_budget > 5:
            raise ValueError(
                f"ResumePlan validation failed: Invalid page budget {plan.target_page_budget}."
            )

        if not plan.section_order:
            raise ValueError("ResumePlan validation failed: section_order cannot be empty.")

        return True
