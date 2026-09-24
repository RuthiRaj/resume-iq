"""
Deterministic Evaluators for ResumeIQ Phase 4.0.2 AI Evaluation Framework

Implements deterministic evaluation functions for:
- evaluate_retrieval_case
- evaluate_grounding_case
- evaluate_planning_case
- evaluate_security_case
- evaluate_determinism_case
- evaluate_case (unified dispatcher)

Zero external LLM dependencies — all evaluations run offline deterministically.
"""

import asyncio
from typing import Dict, Any, List, Optional, Set
from app.schemas.candidate import CandidateEvidence
from app.schemas.evidence import EvidenceItem
from app.schemas.job_description import StructuredJobDescription, JobInfo, SkillRequirement
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.services.resume_planning_service import ResumePlanningService
from app.ai.retrieval.hybrid_matcher import HybridMatcher
from app.ai.retrieval.hybrid_retriever import HybridRetriever
from app.ai.retrieval.embedding_provider import DeterministicFeatureEmbeddingProvider
from app.ai.retrieval.vector_store import InMemoryVectorStore
from app.ai.claim_validator import (
    validate_claims_against_source,
    validate_summary_grounding,
)
from app.evaluation.schemas import EvaluationCase, EvaluationResult


def evaluate_retrieval_case(case: EvaluationCase) -> EvaluationResult:
    """Evaluates keyword matching, canonical classification, and hybrid retrieval ranking."""
    user_id = (case.auth_context or {}).get("resourceOwnerUid", "eval_user_default")
    failures: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, float] = {}
    actual: Dict[str, Any] = {}

    # 1. Normalize workspace evidence
    evidence_items = EvidenceService.normalize_candidate_evidence(user_id, case.workspace_fixture)
    graph = CareerEvidenceGraph(user_id=user_id, items=evidence_items)

    # 2. Build structured job description from fixture
    jd_fixture = case.job_description_fixture
    target_role = jd_fixture.get("targetRole", "")
    must_have = jd_fixture.get("mustHaveSkills", [])
    jd_text = jd_fixture.get("jobDescription", "")

    skills_req = [
        SkillRequirement(name=s, category="Other", importance="MustHave")
        for s in must_have
    ]
    structured_jd = StructuredJobDescription(
        job_info=JobInfo(role_title=target_role or "Software Engineer"),
        must_have_skills=skills_req,
    )

    # 3. Execute Match Classification
    match_resp = HybridMatcher.match_job_requirements(structured_jd, graph)
    matches = match_resp.matches
    match_map = {m.requirement_name.lower(): m for m in matches}
    actual["matchClasses"] = {m.requirement_name: m.match_class for m in matches}

    # Verify Expected Match Classes
    matched_correctly = 0
    total_expected_matches = len(case.expected_match_classes)
    for req_name, expected_class in case.expected_match_classes.items():
        req_lower = req_name.lower()
        if req_lower not in match_map:
            failures.append(f"Requirement '{req_name}' was not classified in match results.")
        else:
            actual_class = match_map[req_lower].match_class
            if actual_class != expected_class:
                failures.append(
                    f"MatchClass mismatch for '{req_name}': expected '{expected_class}', got '{actual_class}'"
                )
            else:
                matched_correctly += 1

    metrics["match_class_accuracy"] = (
        matched_correctly / total_expected_matches if total_expected_matches > 0 else 1.0
    )

    # 4. Execute Retrieval Engine
    store = InMemoryVectorStore()
    embedding_provider = DeterministicFeatureEmbeddingProvider()
    retriever = HybridRetriever(embedding_provider=embedding_provider, store=store)
    
    retrieved = asyncio.run(retriever.retrieve_candidates(
        user_id=user_id,
        target_role=target_role,
        query_text=jd_text,
        must_have_skills=must_have,
        candidate_items=evidence_items,
        top_k=5,
    ))
    retrieved_ids = [r.evidence_id for r in retrieved]
    actual["retrievedIds"] = retrieved_ids

    # Check Expected Evidence Retrieval
    hits = 0
    for exp_id in case.expected_evidence:
        if exp_id in retrieved_ids or any(exp_id.lower() in (r.evidence_item.title.lower() if r.evidence_item else "") for r in retrieved):
            hits += 1
        else:
            failures.append(f"Expected evidence '{exp_id}' was not retrieved in top-{len(retrieved_ids)} results.")
    metrics["hit_rate"] = hits / len(case.expected_evidence) if case.expected_evidence else 1.0

    # Check Expected Non-Matches
    false_positives = 0
    for non_match in case.expected_non_matches:
        nm_lower = non_match.lower()
        for r in retrieved:
            item_title = r.evidence_item.title.lower() if r.evidence_item else ""
            if nm_lower in r.evidence_id.lower() or nm_lower in item_title:
                failures.append(f"Disallowed evidence/tech '{non_match}' was retrieved in candidate: {r.evidence_id}")
                false_positives += 1
        # Also check match_classes
        if nm_lower in match_map and match_map[nm_lower].match_class == "direct_match":
            failures.append(f"Disallowed requirement '{non_match}' was classified as direct_match.")
            false_positives += 1

    metrics["false_positive_count"] = float(false_positives)

    passed = len(failures) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(failures) * 0.25))

    return EvaluationResult(
        caseId=case.case_id,
        taskType="retrieval",
        passed=passed,
        score=score,
        metrics=metrics,
        expected={
            "matchClasses": case.expected_match_classes,
            "expectedEvidence": case.expected_evidence,
            "expectedNonMatches": case.expected_non_matches,
        },
        actual=actual,
        failures=failures,
        warnings=warnings,
    )


def evaluate_grounding_case(case: EvaluationCase) -> EvaluationResult:
    """
    Evaluates factual grounding, metric verification, provenance preservation,
    and immutability of candidate workspace evidence.
    """
    failures: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, float] = {}
    actual: Dict[str, Any] = {}

    # 0. Verify Workspace Immutability Baseline Snapshot
    workspace_snapshot_before = case.workspace_fixture.model_dump_json()

    user_id = (case.auth_context or {}).get("resourceOwnerUid", "eval_user_default")
    evidence_items = EvidenceService.normalize_candidate_evidence(user_id, case.workspace_fixture)

    # 1. Test Provenance Preservation
    provenance_verified = True
    if case.expected_provenance:
        exp_prov = case.expected_provenance
        found_item = None
        for item in evidence_items:
            if item.source_item_id == exp_prov.get("sourceItemId") or item.evidence_id in case.expected_evidence:
                found_item = item
                break
        
        if not found_item:
            failures.append(f"Evidence item for provenance verification '{exp_prov.get('sourceItemId')}' not found.")
            provenance_verified = False
        else:
            actual["provenance"] = {
                "sourceType": found_item.source_type,
                "sourceItemId": found_item.source_item_id,
                "sourceDocumentId": found_item.source_document_id,
                "sourceDocumentName": found_item.source_document_name,
            }
            if exp_prov.get("sourceDocumentId") and found_item.source_document_id != exp_prov.get("sourceDocumentId"):
                failures.append(
                    f"sourceDocumentId mismatch: expected {exp_prov.get('sourceDocumentId')}, got {found_item.source_document_id}"
                )
                provenance_verified = False
            if exp_prov.get("sourceDocumentName") and found_item.source_document_name != exp_prov.get("sourceDocumentName"):
                failures.append(
                    f"sourceDocumentName mismatch: expected {exp_prov.get('sourceDocumentName')}, got {found_item.source_document_name}"
                )
                provenance_verified = False

    metrics["provenance_preservation"] = 1.0 if (provenance_verified and case.expected_provenance) else (1.0 if not case.expected_provenance else 0.0)

    # 2. Test Claim Validation against Synthetic Generation Payload
    unsupported_claims_rejected = 0
    supported_claims_accepted = 0
    false_acceptance_count = 0
    false_rejection_count = 0
    metric_hallucination_rejection = 0
    technology_hallucination_rejection = 0
    leadership_scope_inflation_rejection = 0
    outcome_hallucination_rejection = 0

    if case.synthetic_generation_payload:
        payload = case.synthetic_generation_payload
        rewrites = payload.get("experienceRewrites", []) + payload.get("projectRewrites", [])
        
        candidate_technologies = [
            t for exp in case.workspace_fixture.experience for t in (exp.technologies or [])
        ] + [s.name for s in case.workspace_fixture.skills]

        for r in rewrites:
            orig = r.get("originalBullet", "")
            rewritten = r.get("rewrittenBullet", "")
            item_id = r.get("itemId", "")
            
            # Extract item context tokens
            item_context = set()
            for exp in case.workspace_fixture.experience:
                if exp.id == item_id or not item_id:
                    item_context.update(t.lower() for t in (exp.technologies or []))
                    if exp.company:
                        item_context.add(exp.company.lower())
                    if getattr(exp, "role", None):
                        item_context.add(exp.role.lower())
            for proj in case.workspace_fixture.projects:
                if proj.id == item_id or not item_id:
                    item_context.update(t.lower() for t in getattr(proj, "tech_stack", getattr(proj, "technologies", [])))

            val_res = validate_claims_against_source(
                proposed_bullet=rewritten,
                source_evidence=orig,
                candidate_skills=candidate_technologies,
                item_context_tokens=list(item_context) if item_context else None,
            )
            actual["claimValidation"] = {
                "rewritten": rewritten,
                "isValid": val_res.is_valid,
                "unsupportedClaims": [u.claim_text for u in val_res.unsupported_claims],
            }

            # Check if this case expected rejection (negative constraint)
            if case.expected_non_matches:
                if val_res.is_valid:
                    failures.append(
                        f"Claim validator failed to reject ungrounded rewrite: '{rewritten}'. Expected rejection of {case.expected_non_matches}"
                    )
                    false_acceptance_count += 1
                else:
                    unsupported_claims_rejected += 1
                    # Classify rejection category
                    for u in val_res.unsupported_claims:
                        cat = u.category or ""
                        if cat == "Metric":
                            metric_hallucination_rejection += 1
                        elif cat == "SkillTechnology":
                            technology_hallucination_rejection += 1
                        elif cat in ("SeniorityRole", "Leadership"):
                            leadership_scope_inflation_rejection += 1
                        elif cat in ("Scale", "Outcome"):
                            outcome_hallucination_rejection += 1
            else:
                # Positive case: should pass validation
                if not val_res.is_valid:
                    failures.append(
                        f"Claim validator falsely rejected valid grounded rewrite: '{rewritten}'. Unsupported: {[u.reason for u in val_res.unsupported_claims]}"
                    )
                    false_rejection_count += 1
                else:
                    supported_claims_accepted += 1

        # Evaluate Summary Grounding (if payload includes summary)
        if "summary" in payload and payload["summary"]:
            summary_text = payload["summary"]
            val_summary = validate_summary_grounding(summary_text, case.workspace_fixture)
            actual["summaryValidation"] = {
                "summary": summary_text,
                "isValid": val_summary.is_valid,
                "unsupportedClaims": [u.claim_text for u in val_summary.unsupported_claims],
            }
            if case.expected_non_matches:
                if val_summary.is_valid:
                    failures.append(
                        f"Summary validator failed to reject ungrounded summary: '{summary_text}'. Expected rejection of {case.expected_non_matches}"
                    )
                    false_acceptance_count += 1
                else:
                    unsupported_claims_rejected += 1
            else:
                if not val_summary.is_valid:
                    failures.append(
                        f"Summary validator falsely rejected valid summary: '{summary_text}'. Unsupported: {[u.reason for u in val_summary.unsupported_claims]}"
                    )
                    false_rejection_count += 1
                else:
                    supported_claims_accepted += 1

    total_unsupported_evaluated = unsupported_claims_rejected + false_acceptance_count
    metrics["supported_claims_accepted"] = float(supported_claims_accepted)
    metrics["unsupported_claims_rejected"] = float(unsupported_claims_rejected)
    metrics["false_acceptance_count"] = float(false_acceptance_count)
    metrics["false_rejection_count"] = float(false_rejection_count)
    metrics["hallucination_false_acceptance_rate"] = (
        float(false_acceptance_count) / float(total_unsupported_evaluated)
        if total_unsupported_evaluated > 0
        else 0.0
    )
    metrics["metric_hallucination_rejection"] = float(metric_hallucination_rejection)
    metrics["technology_hallucination_rejection"] = float(technology_hallucination_rejection)
    metrics["leadership_scope_inflation_rejection"] = float(leadership_scope_inflation_rejection)
    metrics["outcome_hallucination_rejection"] = float(outcome_hallucination_rejection)

    # 3. Assert Candidate Workspace Immutability
    workspace_snapshot_after = case.workspace_fixture.model_dump_json()
    if workspace_snapshot_before != workspace_snapshot_after:
        failures.append("Candidate workspace evidence fixture was mutated during evaluation.")

    passed = len(failures) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(failures) * 0.25))

    return EvaluationResult(
        caseId=case.case_id,
        taskType="grounding",
        passed=passed,
        score=score,
        metrics=metrics,
        expected={"provenance": case.expected_provenance, "nonMatches": case.expected_non_matches},
        actual=actual,
        failures=failures,
        warnings=warnings,
    )


def evaluate_planning_case(case: EvaluationCase) -> EvaluationResult:
    """Evaluates deterministic ResumePlan creation, hard gap detection, and prohibited claims."""
    failures: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, float] = {}
    actual: Dict[str, Any] = {}

    user_id = (case.auth_context or {}).get("resourceOwnerUid", "eval_user_default")
    jd_fixture = case.job_description_fixture
    target_role = jd_fixture.get("targetRole", "Software Engineer")
    jd_text = jd_fixture.get("jobDescription", "")

    skills_req = [
        SkillRequirement(name=s, category="Other", importance="MustHave")
        for s in jd_fixture.get("mustHaveSkills", [])
    ]
    structured_jd = StructuredJobDescription(
        job_info=JobInfo(role_title=target_role or "Software Engineer"),
        must_have_skills=skills_req,
    )

    # 1. Create ResumePlan
    plan = ResumePlanningService.create_resume_plan(
        target_role=target_role,
        candidate_evidence=case.workspace_fixture,
        job_description_text=jd_text,
        structured_jd=structured_jd,
    )

    actual["hardGaps"] = [g.requirement_name for g in plan.hard_gaps]
    actual["selectedEvidenceIds"] = [s.evidence_id for s in plan.selected_evidence]
    actual["pageBudget"] = plan.target_page_budget

    # 2. Check Expected Gaps
    detected_gaps = {g.requirement_name.lower() for g in plan.hard_gaps}
    for exp_gap in case.expected_gaps:
        if exp_gap.lower() not in detected_gaps:
            failures.append(f"Expected hard gap '{exp_gap}' was not detected by ResumePlan.")
    
    # 3. Check Prohibited Claim Directives
    for exp_prohib in case.expected_prohibited_claims:
        found_prohib = any(
            exp_prohib.lower() in g.prohibited_claim_instruction.lower()
            or exp_prohib.lower() in g.requirement_name.lower()
            for g in plan.hard_gaps
        )
        if not found_prohib:
            failures.append(f"Expected prohibited claim directive for '{exp_prohib}' was not generated.")

    # 4. Check Selected Evidence Grounding
    norm_items = EvidenceService.normalize_candidate_evidence(user_id, case.workspace_fixture)
    valid_ids = {i.evidence_id for i in norm_items}
    
    for sel in plan.selected_evidence:
        if sel.evidence_id not in valid_ids and sel.source_item_id not in [i.source_item_id for i in norm_items]:
            failures.append(f"ResumePlan selected non-existent workspace evidence: '{sel.evidence_id}'")

    metrics["hard_gap_count"] = float(len(plan.hard_gaps))
    metrics["selected_evidence_count"] = float(len(plan.selected_evidence))

    passed = len(failures) == 0
    score = 1.0 if passed else max(0.0, 1.0 - (len(failures) * 0.25))

    return EvaluationResult(
        caseId=case.case_id,
        taskType="planning",
        passed=passed,
        score=score,
        metrics=metrics,
        expected={"gaps": case.expected_gaps, "prohibitedClaims": case.expected_prohibited_claims},
        actual=actual,
        failures=failures,
        warnings=warnings,
    )


def evaluate_security_case(case: EvaluationCase) -> EvaluationResult:
    """Evaluates prompt injection resistance, tenant isolation, and unverified draft exclusion."""
    failures: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, float] = {}
    actual: Dict[str, Any] = {}

    auth_ctx = case.auth_context or {}
    owner_uid = auth_ctx.get("resourceOwnerUid", "user_owner_default")
    eval_uid = auth_ctx.get("evaluatingUid", owner_uid)

    # 1. Multi-Tenant Isolation Test
    if owner_uid != eval_uid:
        # User B attempts to access User A's evidence
        owner_items = EvidenceService.normalize_candidate_evidence(owner_uid, case.workspace_fixture)
        
        # Test VectorStore isolation
        store = InMemoryVectorStore()
        provider = DeterministicFeatureEmbeddingProvider()
        retriever = HybridRetriever(embedding_provider=provider, store=store)
        
        # Populate for owner
        asyncio.run(retriever.index_evidence_items(owner_uid, owner_items))
        
        # Search as adversary (eval_uid)
        adversary_results = asyncio.run(retriever.retrieve_candidates(
            user_id=eval_uid,
            target_role=case.job_description_fixture.get("targetRole", ""),
            query_text=case.job_description_fixture.get("jobDescription", ""),
            must_have_skills=case.job_description_fixture.get("mustHaveSkills", []),
            candidate_items=[],  # Adversary has no items
        ))
        actual["crossTenantRetrievedCount"] = len(adversary_results)
        
        if len(adversary_results) > 0:
            failures.append(
                f"Multi-tenant security breach: User '{eval_uid}' retrieved {len(adversary_results)} items belonging to '{owner_uid}'."
            )
        metrics["unauthorized_leak_count"] = float(len(adversary_results))

    # 2. Prompt Injection Resistance Test
    # Verify that malicious instructions in candidate text or JD do NOT grant unverified skills
    norm_items = EvidenceService.normalize_candidate_evidence(eval_uid, case.workspace_fixture)
    graph = CareerEvidenceGraph(user_id=eval_uid, items=norm_items)
    
    for non_match in case.expected_non_matches:
        nm_lower = non_match.lower()
        has_skill = bool(graph.find_by_skill(nm_lower) or graph.find_by_technology(nm_lower))
        if has_skill:
            failures.append(
                f"Prompt injection vulnerability: Candidate falsely acquired skill '{non_match}' from adversarial text."
            )

    # 3. Unverified Draft Staging Test
    if "unverified_draft" in case.evaluation_tags:
        # Verify that unverified draft items do not satisfy target role requirements as verified direct matches
        jd_fixture = case.job_description_fixture
        skills_req = [
            SkillRequirement(name=s, category="Other", importance="MustHave")
            for s in jd_fixture.get("mustHaveSkills", [])
        ]
        structured_jd = StructuredJobDescription(
            job_info=JobInfo(role_title=jd_fixture.get("targetRole", "") or "Software Engineer"),
            must_have_skills=skills_req,
        )
        match_resp = HybridMatcher.match_job_requirements(structured_jd, graph)
        for m in match_resp.matches:
            if m.requirement_name.lower() in [nm.lower() for nm in case.expected_non_matches]:
                if m.match_class == "direct_match":
                    failures.append(f"Unverified draft was improperly elevated to direct_match for '{m.requirement_name}'.")

    passed = len(failures) == 0
    score = 1.0 if passed else 0.0

    return EvaluationResult(
        caseId=case.case_id,
        taskType="security",
        passed=passed,
        score=score,
        metrics=metrics,
        expected={"nonMatches": case.expected_non_matches},
        actual=actual,
        failures=failures,
        warnings=warnings,
    )


def evaluate_determinism_case(case: EvaluationCase, runs: int = 3) -> EvaluationResult:
    """Verifies that running deterministic components multiple times produces identical outputs."""
    failures: List[str] = []
    metrics: Dict[str, float] = {}
    
    first_run_plan: Optional[str] = None
    first_run_matches: Optional[str] = None
    
    for i in range(runs):
        user_id = f"eval_user_det_{case.case_id}"
        items = EvidenceService.normalize_candidate_evidence(user_id, case.workspace_fixture)
        graph = CareerEvidenceGraph(user_id=user_id, items=items)
        
        jd_fixture = case.job_description_fixture
        skills_req = [
            SkillRequirement(name=s, category="Other", importance="MustHave")
            for s in jd_fixture.get("mustHaveSkills", [])
        ]
        structured_jd = StructuredJobDescription(
            job_info=JobInfo(role_title=jd_fixture.get("targetRole", "") or "Software Engineer"),
            must_have_skills=skills_req,
        )
        
        match_resp = HybridMatcher.match_job_requirements(structured_jd, graph)
        matches = match_resp.matches
        matches_serialized = str([(m.requirement_name, m.match_class) for m in matches])
        
        plan = ResumePlanningService.create_resume_plan(
            target_role=jd_fixture.get("targetRole", ""),
            candidate_evidence=case.workspace_fixture,
            job_description_text=jd_fixture.get("jobDescription", ""),
            structured_jd=structured_jd,
        )
        plan_serialized = str([
            (s.evidence_id, s.source_item_id) for s in plan.selected_evidence
        ] + [g.requirement_name for g in plan.hard_gaps])
        
        if first_run_matches is None:
            first_run_matches = matches_serialized
            first_run_plan = plan_serialized
        else:
            if matches_serialized != first_run_matches:
                failures.append(f"Non-deterministic match classification detected on run {i+1}.")
            if plan_serialized != first_run_plan:
                failures.append(f"Non-deterministic ResumePlan detected on run {i+1}.")

    passed = len(failures) == 0
    metrics["repetition_consistency"] = 1.0 if passed else 0.0

    return EvaluationResult(
        caseId=case.case_id,
        taskType="determinism",
        passed=passed,
        score=1.0 if passed else 0.0,
        metrics=metrics,
        expected={"deterministicRuns": runs},
        actual={"successfulIdenticalRuns": runs if passed else 0},
        failures=failures,
    )


def evaluate_case(case: EvaluationCase) -> EvaluationResult:
    """Dispatches an EvaluationCase to its specific task evaluator."""
    if case.task_type == "retrieval":
        return evaluate_retrieval_case(case)
    elif case.task_type == "grounding":
        return evaluate_grounding_case(case)
    elif case.task_type == "planning":
        return evaluate_planning_case(case)
    elif case.task_type == "security":
        return evaluate_security_case(case)
    elif case.task_type == "determinism":
        return evaluate_determinism_case(case)
    else:
        return evaluate_retrieval_case(case)
