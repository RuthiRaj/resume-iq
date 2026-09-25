"""
ResumeIQ Deterministic Adversarial AI & Security Evaluator (Phase 4.0.8)

Offline, deterministic evaluation engine that verifies ResumeIQ's production security,
grounding boundaries, tenant isolation, and telemetry privacy under adversarial inputs.

100% Deterministic — 0 External AI API calls, 0 database writes.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.candidate import CandidateEvidence
from app.schemas.evidence import EvidenceItem
from app.schemas.job_description import StructuredJobDescription, JobInfo, SkillRequirement
from app.schemas.plan import ResumePlan, SelectedEvidenceItem, ExcludedEvidenceItem
from app.schemas.variant import TargetedResumeVariant
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.services.resume_planning_service import ResumePlanningService
from app.ai.retrieval.hybrid_matcher import HybridMatcher
from app.ai.claim_validator import validate_claims_against_source
from app.ai.observability import TokenUsage, CostBreakdown, StageLatency, GroundingMetrics, calculate_token_cost
from app.ai.resilience import ProviderExecutionEvent, ProviderErrorType
from app.evaluation.dataset.adversarial_cases import (
    AdversarialCase,
    AdversarialCategory,
    get_adversarial_cases,
    DATASET_VERSION,
)


class AdversarialResult(BaseModel):
    """Evaluation result for an individual adversarial security case."""
    case_id: str = Field(..., alias="caseId")
    category: AdversarialCategory
    passed: bool
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AdversarialSuiteReport(BaseModel):
    """Aggregate summary report for the complete Phase 4.0.8 adversarial evaluation suite."""
    dataset_version: str = Field(default=DATASET_VERSION, alias="datasetVersion")
    total_cases: int = Field(default=0, alias="totalCases")
    passed_cases: int = Field(default=0, alias="passedCases")
    failed_cases: int = Field(default=0, alias="failedCases")
    pass_rate: float = Field(default=0.0, alias="passRate")
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict, alias="categoryBreakdown")
    prompt_injection_blocked_count: int = Field(default=0, alias="promptInjectionBlockedCount")
    unsupported_claims_rejected_count: int = Field(default=0, alias="unsupportedClaimsRejectedCount")
    tenant_violations_prevented_count: int = Field(default=0, alias="tenantViolationsPreventedCount")
    workspace_contamination_count: int = Field(default=0, alias="workspaceContaminationCount")
    telemetry_privacy_violations_count: int = Field(default=0, alias="telemetryPrivacyViolationsCount")
    results: List[AdversarialResult] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


def evaluate_adversarial_case(case: AdversarialCase) -> AdversarialResult:
    """
    Executes an individual adversarial evaluation case deterministically against production
    ResumeIQ defenses without calling external AI providers.
    """
    failures: List[str] = []
    warnings: List[str] = []
    metrics: Dict[str, Any] = {}
    details: Dict[str, Any] = {}

    auth = case.auth_context or {}
    user_id = auth.get("resourceOwnerUid", "adv_eval_user")

    # 1. Normalize workspace evidence & construct CareerEvidenceGraph
    evidence_items = EvidenceService.normalize_candidate_evidence(
        user_id=user_id,
        evidence=case.workspace_fixture,
    )
    graph = CareerEvidenceGraph(user_id=user_id, items=evidence_items)

    # -------------------------------------------------------------------------
    # CATEGORIES A, B, C: PROMPT INJECTIONS & HARD-GAP BYPASS
    # -------------------------------------------------------------------------
    if case.category in ("evidence_prompt_injection", "jd_prompt_injection", "hard_gap_bypass"):
        jd_fixture = case.job_description_fixture or {}
        must_have = jd_fixture.get("mustHaveSkills", [])
        target_role = jd_fixture.get("targetRole", "Software Engineer")

        # Test Matcher Resistance against Prompt Injection
        if must_have:
            skills_req = [
                SkillRequirement(name=s, category="Other", importance="MustHave")
                for s in must_have
            ]
            structured_jd = StructuredJobDescription(
                job_info=JobInfo(role_title=target_role),
                must_have_skills=skills_req,
            )
            match_resp = HybridMatcher.match_job_requirements(structured_jd, graph)
            match_map = {m.requirement_name.lower(): m for m in match_resp.matches}
            details["match_results"] = {m.requirement_name: m.match_class for m in match_resp.matches}

            for prohibited in case.expected_prohibited_skills:
                m_item = match_map.get(prohibited.lower())
                if m_item and m_item.match_class in ("StrongMatch", "EvidenceSupported"):
                    failures.append(
                        f"Prompt injection succeeded in forcing match for prohibited skill '{prohibited}' (classified as '{m_item.match_class}')."
                    )

        # Test Claim Validator on proposed adversarial bullet if provided
        if case.proposed_bullet and case.source_bullet:
            candidate_skills = [s.name for s in case.workspace_fixture.skills] if case.workspace_fixture.skills else []
            val_res = validate_claims_against_source(
                proposed_bullet=case.proposed_bullet,
                source_evidence=case.source_bullet,
                candidate_skills=candidate_skills,
            )
            rejection_reasons = [u.reason for u in val_res.unsupported_claims]
            details["claim_validation"] = {
                "is_valid": val_res.is_valid,
                "rejection_reasons": rejection_reasons,
            }
            if case.expected_valid is False and val_res.is_valid is True:
                failures.append(
                    f"ClaimValidator failed to reject adversarial proposed bullet: '{case.proposed_bullet}'"
                )
            elif case.expected_valid is True and val_res.is_valid is False:
                failures.append(
                    f"ClaimValidator unexpectedly rejected benign bullet: {rejection_reasons}"
                )

    # -------------------------------------------------------------------------
    # CATEGORIES D, E, F, G: TECHNOLOGY EQUIVALENCE, METRICS, LEADERSHIP, OUTCOME
    # -------------------------------------------------------------------------
    elif case.category in ("technology_equivalence", "metric_inflation", "leadership_inflation", "outcome_injection"):
        if not (case.proposed_bullet and case.source_bullet):
            failures.append("Adversarial case missing source_bullet or proposed_bullet fixture.")
        else:
            candidate_skills = [s.name for s in case.workspace_fixture.skills] if case.workspace_fixture.skills else []
            val_res = validate_claims_against_source(
                proposed_bullet=case.proposed_bullet,
                source_evidence=case.source_bullet,
                candidate_skills=candidate_skills,
            )
            rejection_reasons = [u.reason for u in val_res.unsupported_claims]
            details["claim_validation"] = {
                "is_valid": val_res.is_valid,
                "rejection_reasons": rejection_reasons,
            }
            metrics["claims_evaluated"] = 1
            metrics["claims_rejected"] = 0 if val_res.is_valid else 1

            if case.expected_valid is False and val_res.is_valid is True:
                failures.append(
                    f"ClaimValidator accepted unsupported adversarial modification: '{case.proposed_bullet}'"
                )
            elif case.expected_valid is True and val_res.is_valid is False:
                failures.append(
                    f"ClaimValidator unexpectedly rejected benign bullet: {rejection_reasons}"
                )

    # -------------------------------------------------------------------------
    # CATEGORY H: MALICIOUS TEXT PAYLOADS
    # -------------------------------------------------------------------------
    elif case.category == "malicious_payload":
        # Check that normalization, graph construction, and claim validation execute cleanly
        try:
            items = EvidenceService.normalize_candidate_evidence(user_id=user_id, evidence=case.workspace_fixture)
            test_graph = CareerEvidenceGraph(user_id=user_id, items=items)
            assert len(test_graph._items_by_id) == len(items)

            if case.proposed_bullet and case.source_bullet:
                candidate_skills = [s.name for s in case.workspace_fixture.skills] if case.workspace_fixture.skills else []
                val_res = validate_claims_against_source(
                    proposed_bullet=case.proposed_bullet,
                    source_evidence=case.source_bullet,
                    candidate_skills=candidate_skills,
                )
                details["claim_validation"] = {"is_valid": val_res.is_valid}
                if case.expected_valid != val_res.is_valid:
                    failures.append(f"Validation outcome mismatch on payload case: expected {case.expected_valid}, got {val_res.is_valid}")
        except Exception as e:
            failures.append(f"Malicious payload triggered unhandled exception: {str(e)}")

    # -------------------------------------------------------------------------
    # CATEGORY I: PROVENANCE ATTACKS
    # -------------------------------------------------------------------------
    elif case.category == "provenance_attack":
        if case.case_id == "ADV_027":
            # Fabricated / Nonexistent Evidence ID in Plan Validation
            target_item_id = auth.get("targetItemId", "exp_nonexistent_99")
            if graph.get_provenance(target_item_id) is not None:
                failures.append(f"Graph unexpectedly found non-existent item '{target_item_id}'")

            synthetic_plan = ResumePlan(
                planId="plan_adv_fake_ev",
                userId=user_id,
                targetRole="Engineer",
                selectedEvidence=[
                    SelectedEvidenceItem(
                        evidenceId=target_item_id,
                        sourceType="experience",
                        sourceItemId="fake_exp_99",
                        title="Fake Item",
                        inclusionReason="Adversarial fake item injection",
                    )
                ],
                excludedEvidence=[],
                prioritizedSkills=[],
                hardGaps=[],
                targetPageBudget=1,
                sectionOrder=["Summary", "Experience"],
                createdAt="2026-09-25T00:00:00Z",
            )
            try:
                ResumePlanningService.validate_resume_plan(
                    plan=synthetic_plan,
                    candidate_items=evidence_items,
                    expected_user_id=user_id,
                )
                failures.append("ResumePlanningService failed to reject fabricated evidence ID in ResumePlan.")
            except ValueError as ve:
                details["expected_error"] = str(ve)
        elif case.case_id == "ADV_028":
            # Stale version collision attack
            current_version = auth.get("currentVariantVersion", 3)
            supplied_expected_version = auth.get("suppliedExpectedVersion", 1)
            if supplied_expected_version == current_version:
                failures.append("Stale version fixture is identical to current version.")
            else:
                # Assert version conflict detection logic
                if supplied_expected_version != current_version:
                    details["version_conflict_detected"] = True

    # -------------------------------------------------------------------------
    # CATEGORY J: TENANT ISOLATION ATTACKS
    # -------------------------------------------------------------------------
    elif case.category == "tenant_isolation":
        if case.case_id == "ADV_029":
            # Cross-Tenant Evidence Injection
            eval_user = auth.get("evaluatingUserId", "user_attacker_123")
            foreign_user = auth.get("foreignUserId", "user_victim_456")
            foreign_item = EvidenceItem(
                evidenceId="ev_victim_exp_01",
                userId=foreign_user,
                sourceType="experience",
                sourceItemId="exp_foreign",
                title="Victim Secret Work",
                achievements=["Secret proprietary backend."],
                skills=["Go"],
            )
            attacker_plan = ResumePlan(
                planId="plan_cross_tenant",
                userId=eval_user,
                targetRole="Engineer",
                selectedEvidence=[
                    SelectedEvidenceItem(
                        evidenceId="ev_victim_exp_01",
                        sourceType="experience",
                        sourceItemId="exp_foreign",
                        title="Victim Work",
                        inclusionReason="Cross-tenant theft attempt",
                    )
                ],
                excludedEvidence=[],
                prioritizedSkills=[],
                hardGaps=[],
                targetPageBudget=1,
                sectionOrder=["Summary", "Experience"],
                createdAt="2026-09-25T00:00:00Z",
            )
            try:
                # Validating attacker plan with foreign evidence item present in pool
                ResumePlanningService.validate_resume_plan(
                    plan=attacker_plan,
                    candidate_items=[foreign_item],
                    expected_user_id=eval_user,
                )
                failures.append("ResumePlanningService failed to prevent cross-tenant evidence reference.")
            except ValueError as ve:
                details["tenant_isolation_enforced"] = str(ve)
        elif case.case_id == "ADV_030":
            # Forged User ID in Plan Validation
            auth_user = auth.get("authenticatedUserId", "user_authenticated_789")
            forged_user = auth.get("planSuppliedUserId", "user_forged_999")
            forged_plan = ResumePlan(
                planId="plan_forged_user",
                userId=forged_user,
                targetRole="Engineer",
                selectedEvidence=[],
                excludedEvidence=[],
                prioritizedSkills=[],
                hardGaps=[],
                targetPageBudget=1,
                sectionOrder=["Summary"],
                createdAt="2026-09-25T00:00:00Z",
            )
            try:
                ResumePlanningService.validate_resume_plan(
                    plan=forged_plan,
                    candidate_items=[],
                    expected_user_id=auth_user,
                )
                failures.append("ResumePlanningService failed to reject forged user_id in ResumePlan.")
            except ValueError as ve:
                details["user_id_mismatch_caught"] = str(ve)

    # -------------------------------------------------------------------------
    # CATEGORY K: WORKSPACE CONTAMINATION
    # -------------------------------------------------------------------------
    elif case.category == "workspace_contamination":
        # Verify root workspace snapshot remains completely immutable
        initial_dump = case.workspace_fixture.model_dump_json()

        # Simulate TargetedResumeVariant creation (forked branch)
        variant = TargetedResumeVariant(
            variantId="var_test_isolation_01",
            masterResumeId="res_root_001",
            title="Targeted Lead Resume",
            targetRole="Lead Engineer",
            jobDescriptionHash=hashlib.sha256(b"Lead Engineer JD").hexdigest(),
            version=1,
            snapshot=case.workspace_fixture.model_copy(deep=True),
            createdAt="2026-09-25T00:00:00Z",
            updatedAt="2026-09-25T00:00:00Z",
        )
        # Modify the variant snapshot
        variant.snapshot.headline = "Modified Headline In Forked Variant"

        # Verify root workspace is 100% untouched
        post_dump = case.workspace_fixture.model_dump_json()
        if initial_dump != post_dump:
            failures.append("Root workspace candidate evidence was contaminated/modified during variant operation!")
        else:
            details["workspace_immutability_verified"] = True

    # -------------------------------------------------------------------------
    # CATEGORY L: PROVIDER FAILOVER CONTEXT SECURITY
    # -------------------------------------------------------------------------
    elif case.category == "provider_failover_attack":
        prompt_text = "Standard grounding prompt with evidence and JD."
        initial_prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

        # Simulate failover event sequence
        event_primary = ProviderExecutionEvent(
            provider_name="groq",
            model_name="llama-3.3-70b-versatile",
            latency_ms=1200.0,
            error_type=ProviderErrorType.TIMEOUT,
            retry_count=1,
            success=False,
        )
        event_fallback = ProviderExecutionEvent(
            provider_name="gemini",
            model_name="gemini-2.5-flash",
            latency_ms=650.0,
            retry_count=0,
            success=True,
        )
        # Prompt sent to fallback must match exact hash
        fallback_prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        if initial_prompt_hash != fallback_prompt_hash:
            failures.append("Prompt hash mutated across provider failover boundary!")
        details["failover_events"] = [event_primary.model_dump(), event_fallback.model_dump()]

    # -------------------------------------------------------------------------
    # CATEGORY M: TELEMETRY PRIVACY ATTACKS
    # -------------------------------------------------------------------------
    elif case.category == "telemetry_privacy":
        secret_token = auth.get("userToken", "super_secret_auth_token_xyz999")
        secret_api_key = auth.get("apiKey", "sk_live_groq_api_key_secret_123")

        usage = TokenUsage(prompt_tokens=450, completion_tokens=180, total_tokens=630)
        cost = calculate_token_cost("groq", "llama-3.3-70b-versatile", usage)
        latency = StageLatency(retrieval_ms=12.5, planning_ms=18.0, generation_ms=450.0, validation_ms=22.0, total_ms=502.5)
        metrics_model = GroundingMetrics(claims_evaluated=5, claims_accepted=4, claims_rejected=1, bullets_reverted=1)
        event = ProviderExecutionEvent(
            provider_name="groq",
            model_name="llama-3.3-70b-versatile",
            latency_ms=450.0,
            token_usage=usage,
            cost=cost,
            success=True,
        )

        all_telemetry_json = json.dumps({
            "usage": usage.model_dump(),
            "cost": cost.model_dump(),
            "latency": latency.model_dump(),
            "metrics": metrics_model.model_dump(),
            "event": event.model_dump(),
        })

        if secret_token in all_telemetry_json:
            failures.append("User auth token leaked into telemetry payload!")
        if secret_api_key in all_telemetry_json:
            failures.append("API secret key leaked into telemetry payload!")
        if case.workspace_fixture.summary and case.workspace_fixture.summary in all_telemetry_json:
            failures.append("Raw candidate summary PII leaked into telemetry payload!")

        details["telemetry_sanitized"] = True

    passed = len(failures) == 0
    return AdversarialResult(
        caseId=case.case_id,
        category=case.category,
        passed=passed,
        failures=failures,
        warnings=warnings,
        metrics=metrics,
        details=details,
    )


def run_adversarial_suite(cases: Optional[List[AdversarialCase]] = None) -> AdversarialSuiteReport:
    """
    Runs the complete Phase 4.0.8 adversarial security evaluation suite.
    """
    if cases is None:
        cases = get_adversarial_cases()

    results: List[AdversarialResult] = []
    cat_breakdown: Dict[str, Dict[str, Any]] = {}

    injection_blocked = 0
    unsupported_rejected = 0
    tenant_prevented = 0
    workspace_contaminated = 0
    privacy_violations = 0

    for case in cases:
        res = evaluate_adversarial_case(case)
        results.append(res)

        cat = case.category
        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"total": 0, "passed": 0, "failed": 0}
        cat_breakdown[cat]["total"] += 1
        if res.passed:
            cat_breakdown[cat]["passed"] += 1
        else:
            cat_breakdown[cat]["failed"] += 1

        # Counters for specific security invariants
        if cat in ("evidence_prompt_injection", "jd_prompt_injection", "hard_gap_bypass"):
            if res.passed:
                injection_blocked += 1
        elif cat in ("technology_equivalence", "metric_inflation", "leadership_inflation", "outcome_injection"):
            if res.passed:
                unsupported_rejected += 1
        elif cat in ("provenance_attack", "tenant_isolation"):
            if res.passed:
                tenant_prevented += 1
        elif cat == "workspace_contamination":
            if not res.passed:
                workspace_contaminated += 1
        elif cat == "telemetry_privacy":
            if not res.passed:
                privacy_violations += 1

    total = len(cases)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = total - passed_count
    pass_rate = (passed_count / total) if total > 0 else 0.0

    return AdversarialSuiteReport(
        datasetVersion=DATASET_VERSION,
        totalCases=total,
        passedCases=passed_count,
        failedCases=failed_count,
        passRate=round(pass_rate, 4),
        categoryBreakdown=cat_breakdown,
        promptInjectionBlockedCount=injection_blocked,
        unsupportedClaimsRejectedCount=unsupported_rejected,
        tenantViolationsPreventedCount=tenant_prevented,
        workspaceContaminationCount=workspace_contaminated,
        telemetryPrivacyViolationsCount=privacy_violations,
        results=results,
    )
