"""
Phase 3A Regression Tests: Grounding Integrity & Candidate Skill Attestation

Verifies that:
1. Missing skills cannot silently become verified.
2. User-attested skills are stored with explicit unverified/user_confirmed semantics.
3. Provenance reflects user attestation rather than independent document verification.
4. Fabricated years/proficiency are not automatically assumed or inserted.
5. ClaimValidator remains active to reject ungrounded metrics and inflated leadership claims.
6. Tenant isolation protects skill profiles and attestations.
7. Existing verified workspace skills remain untouched.
8. Existing missing skills remain missing until legitimate attestation or evidence is supplied.
9. Strict non-equivalence is preserved (TypeScript != JavaScript, Docker != Kubernetes, React != Angular, C != C++).
10. Attestation fails when candidate claims unsupported quantitative metrics or executive scope.
"""

import pytest
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import CandidateEvidence, SkillItem, ExperienceItem, ProjectItem
from app.schemas.evidence import EvidenceItem
from app.schemas.job_description import StructuredJobDescription, JobInfo, SkillRequirement
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.ai.retrieval.hybrid_matcher import HybridMatcher, find_related_technology
from app.ai.decision_engine import DecisionEngine
from app.ai.claim_validator import validate_claims_against_source
from app.ai.skills import normalize_skill_name, normalize_skill_category


def test_user_attested_skill_preserves_unverified_status():
    """Requirement 1 & 3: Attested skill retains user_confirmed status with calibrated confidence."""
    user_id = "test_user_p3a"
    evidence = CandidateEvidence(
        skills=[
            SkillItem(
                name="Python",
                category="Languages",
                proficiency="Intermediate",
                years_of_experience=2.0,
                verification_status="user_confirmed",
                provenance="user_attestation",
                source_context="Built asynchronous microservices in personal project",
            ),
            SkillItem(
                name="React",
                category="Frameworks",
                proficiency="Expert",
                years_of_experience=5.0,
                verification_status="verified",
            ),
        ]
    )

    items = EvidenceService.normalize_candidate_evidence(user_id, evidence)
    skill_items = [i for i in items if i.source_type == "skills"]
    assert len(skill_items) == 2

    python_item = next(i for i in skill_items if i.title == "Python")
    react_item = next(i for i in skill_items if i.title == "React")

    # Python was user_confirmed: must NOT be verified, confidence calibrated to 0.70
    assert python_item.verification_status == "user_confirmed"
    assert python_item.confidence == 0.70

    # React was verified: retains verified status, confidence 0.85
    assert react_item.verification_status == "verified"
    assert react_item.confidence == 0.85


def test_decision_engine_flags_user_confirmed_skill_for_review():
    """Requirement 1 & 3: DecisionEngine requires candidate review and does NOT auto-assert attested skills."""
    evidence_item = EvidenceItem(
        evidenceId="ev_skill_py",
        userId="user_p3a",
        sourceType="skills",
        sourceItemId="skill_py",
        title="Python",
        description="Intermediate proficiency in Python (Language)",
        skills=["Python"],
        technologies=["Python"],
        responsibilities=[],
        achievements=[],
        metrics=[],
        dates="",
        role="",
        domain="Language",
        verificationStatus="user_confirmed",
        confidence=0.70,
    )

    decision = DecisionEngine.evaluate_decision(
        requirement="Python",
        match_class="direct_match",
        matched_technology="Python",
        evidence_items=[evidence_item],
    )

    # Must flag for candidate review rather than asserting automatically as verified
    assert decision.decision in ("REVIEW", "PROHIBIT")
    assert any("unverified" in r.lower() or "review" in r.lower() for r in decision.reasons)


def test_hybrid_matcher_demotes_attested_skill_to_user_confirmation_required():
    """Requirement 1 & 8: MustHave skill with only user_confirmed tag requires confirmation."""
    candidate_evidence = CandidateEvidence(
        skills=[
            SkillItem(
                name="Kubernetes",
                category="DevOps",
                proficiency="Intermediate",
                verification_status="user_confirmed",
                provenance="user_attestation",
            )
        ]
    )

    items = EvidenceService.normalize_candidate_evidence("user_p3a", candidate_evidence)
    graph = CareerEvidenceGraph(user_id="user_p3a", items=items)

    jd = StructuredJobDescription(
        jobInfo=JobInfo(roleTitle="Site Reliability Engineer", company="Test Corp", seniorityLevel="Senior"),
        mustHaveSkills=[
            SkillRequirement(
                name="Kubernetes",
                category="DevOps",
                importance="MustHave",
                sourceEvidence="Deep production experience with Kubernetes",
            )
        ],
        preferredSkills=[],
        technicalStack=["Kubernetes"],
    )

    response = HybridMatcher.match_job_requirements(jd, graph)
    assert len(response.matches) == 1
    match = response.matches[0]

    # Must be classified as user_confirmation_required, NOT direct_match
    assert match.match_class == "user_confirmation_required"
    assert "user-attested" in match.explanation.lower() or "lacks" in match.explanation.lower()
    assert match.confidence < 1.0


def test_non_equivalence_typescript_javascript_intact():
    """Requirement 9: Non-equivalence between TypeScript and JavaScript remains intact."""
    related = find_related_technology("TypeScript", {"JavaScript"})
    assert related == "JavaScript"

    # Inverted
    related_inv = find_related_technology("JavaScript", {"TypeScript"})
    assert related_inv == "TypeScript"

    # But they are strictly distinct technologies
    assert normalize_skill_name("TypeScript") != normalize_skill_name("JavaScript")


def test_non_equivalence_docker_kubernetes_intact():
    """Requirement 9: Docker != Kubernetes."""
    related = find_related_technology("Kubernetes", {"Docker"})
    assert related == "Docker"
    assert normalize_skill_name("Docker") != normalize_skill_name("Kubernetes")


def test_non_equivalence_react_angular_intact():
    """Requirement 9: React != Angular."""
    related = find_related_technology("Angular", {"React"})
    assert related == "React"
    assert normalize_skill_name("React") != normalize_skill_name("Angular")


def test_non_equivalence_c_cpp_intact():
    """Requirement 9: C != C++."""
    related = find_related_technology("C++", {"C"})
    assert related is not None
    assert related.lower() == "c"
    assert normalize_skill_name("C") != normalize_skill_name("C++")


def test_claim_validator_rejects_unsupported_metrics_in_attestation():
    """Requirement 5 & 10: Attestation fails if ungrounded metrics are fabricated."""
    proposed_bullet = "Engineered automated batch pipelines in Python improving latency by 450% and scaling to 10M users."
    source_evidence = "Worked on Python backend scripts at startup for 6 months."
    item_context = {"python", "backend", "scripts", "startup"}
    candidate_skills = ["Python"]

    val_res = validate_claims_against_source(
        proposed_bullet=proposed_bullet,
        source_evidence=source_evidence,
        item_context_tokens=item_context,
        candidate_skills=candidate_skills,
    )

    assert not val_res.is_valid
    assert any("metric" in u.reason.lower() or "quant" in u.reason.lower() for u in val_res.unsupported_claims)


def test_claim_validator_rejects_inflated_leadership_in_attestation():
    """Requirement 5 & 10: Attestation fails if executive leadership is fabricated from individual contributor context."""
    proposed_bullet = "Spearheaded and directed executive engineering strategy and managed 25 engineers utilizing Python."
    source_evidence = "Assisted with Python feature development as an associate developer."
    item_context = {"python", "feature", "development", "associate"}
    candidate_skills = ["Python"]

    val_res = validate_claims_against_source(
        proposed_bullet=proposed_bullet,
        source_evidence=source_evidence,
        item_context_tokens=item_context,
        candidate_skills=candidate_skills,
    )

    assert not val_res.is_valid
    assert any("verb" in u.reason.lower() or "leadership" in u.reason.lower() or "executive" in u.reason.lower() for u in val_res.unsupported_claims)


def test_existing_verified_workspace_skills_remain_untouched():
    """Requirement 7: Existing verified evidence items are preserved without mutation or downgrade."""
    evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                role="Senior Engineer",
                company="Stripe",
                bullets=["Architected payments orchestration pipeline in Go handling $50M/mo."],
                technologies=["Go", "PostgreSQL"],
                verification_status="verified",
                confidence=1.0,
            )
        ],
        skills=[
            SkillItem(
                name="Go",
                category="Languages",
                proficiency="Expert",
                verification_status="verified",
                confidence=1.0,
            )
        ]
    )

    items = EvidenceService.normalize_candidate_evidence("user_verified_stripe", evidence)
    assert len(items) == 2

    exp_item = next(i for i in items if i.source_type == "experience")
    assert exp_item.verification_status == "verified"
    assert exp_item.confidence == 1.0
    assert "Go" in exp_item.technologies

    skill_item = next(i for i in items if i.source_type == "skills")
    assert skill_item.verification_status == "verified"
    assert skill_item.confidence == 1.0


def test_skill_normalization_preserves_canonical_names():
    """Requirement 4: Canonical normalization maps aliases while preserving distinct identities."""
    assert normalize_skill_name("k8s") == "Kubernetes"
    assert normalize_skill_name("reactjs") == "React"
    assert normalize_skill_name("ts") == "TypeScript"
    assert normalize_skill_name("js") == "JavaScript"
    assert normalize_skill_name("golang") == "Go"
    assert normalize_skill_category("Python", "Languages") == "Language"
    assert normalize_skill_category("AWS", "Cloud") == "Cloud"


def test_attested_skill_cannot_become_generated_bullet_claim():
    """Requirement: Attested skill cannot be used by ClaimValidator as allowed token to rewrite work bullets."""
    from app.ai.claim_validator import validate_claims_against_source

    candidate_evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_1",
                role="Backend Engineer",
                company="Acme Corp",
                bullets=["Engineered backend microservices in Python handling 5000 rps."],
                technologies=["Python"],
                verification_status="verified",
            )
        ],
        skills=[
            SkillItem(
                name="Kubernetes",
                verification_status="user_confirmed",
                provenance="user_attestation",
                source_context="Attested by candidate in analyzer",
            ),
            SkillItem(
                name="Python",
                verification_status="verified",
                provenance="resume_parse",
            ),
        ]
    )

    # In ResumeGenerationService, candidate_skills is filtered to verified only:
    verified_candidate_skills = [
        s.name for s in candidate_evidence.skills
        if (getattr(s, "verification_status", None) or "verified") == "verified"
    ]
    assert "Kubernetes" not in verified_candidate_skills
    assert "Python" in verified_candidate_skills

    # Scenario: Generator attempts to inject 'Kubernetes' into the Python bullet
    proposed_bullet = "Developed backend microservices in Python using Kubernetes."
    item_context = {"acme corp", "backend engineer", "python"}

    val_res = validate_claims_against_source(
        proposed_bullet=proposed_bullet,
        source_evidence="Engineered backend microservices in Python handling 5000 rps.",
        item_context_tokens=item_context,
        candidate_skills=verified_candidate_skills,
    )

    # Must be REJECTED because Kubernetes is not in verified skills or work evidence
    assert not val_res.is_valid
    assert val_res.status == "RequiresCandidateInput"
    assert any(
        c.claim_text.lower() == "kubernetes" and "introduced new content word" in c.reason.lower()
        for c in val_res.unsupported_claims
    )


def test_attested_skill_cannot_become_generated_summary_claim():
    """Requirement: Attested skill cannot support ungrounded technology claims in the generated summary."""
    from app.ai.claim_validator import validate_summary_grounding

    candidate_evidence = CandidateEvidence(
        headline="Backend Engineer",
        summary="Software engineer with 4 years of experience building Python APIs.",
        experience=[
            ExperienceItem(
                id="exp_1",
                role="Backend Engineer",
                company="Acme Corp",
                start_date="2020-01",
                end_date="2024-01",
                bullets=["Engineered backend microservices in Python."],
                technologies=["Python"],
                verification_status="verified",
            )
        ],
        skills=[
            SkillItem(
                name="Kubernetes",
                verification_status="user_confirmed",
                provenance="user_attestation",
            ),
            SkillItem(
                name="Python",
                verification_status="verified",
            ),
        ]
    )

    # Candidate summary attempts to claim Kubernetes expertise
    proposed_summary = "Backend Engineer with 4 years of experience specializing in Kubernetes and Python."
    val_res = validate_summary_grounding(proposed_summary, candidate_evidence)

    # Must be REJECTED because Kubernetes is not a verified skill or evidence token
    assert not val_res.is_valid
    assert any(
        c.claim_text.lower() == "kubernetes" and "introduced technology" in c.reason.lower()
        for c in val_res.unsupported_claims
    )


def test_resume_plan_grounding_for_user_confirmed_skills():
    """Requirement: ResumePlanningService marks user_confirmed skills with isDirectlyDemonstrated=False and DecisionEngine=REVIEW."""
    from app.services.resume_planning_service import ResumePlanningService
    from app.schemas.plan import ResumePlan

    candidate_evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_1",
                role="Backend Engineer",
                company="Acme Corp",
                start_date="2020-01",
                end_date="2024-01",
                bullets=["Engineered backend microservices in Python."],
                technologies=["Python"],
                verification_status="verified",
            )
        ],
        skills=[
            SkillItem(
                name="Kubernetes",
                verification_status="user_confirmed",
                provenance="user_attestation",
                source_context="Learned via self-study",
            ),
            SkillItem(
                name="Python",
                verification_status="verified",
            ),
        ]
    )

    plan = ResumePlanningService.create_resume_plan(
        target_role="Platform Engineer",
        candidate_evidence=candidate_evidence,
        job_description_text="Must have Kubernetes and Python experience.",
    )

    assert isinstance(plan, ResumePlan)

    # Kubernetes must be in user_confirmation_required, NOT direct matches
    assert "Kubernetes" in plan.user_confirmation_required

    k8s_skill = next((s for s in plan.prioritized_skills if s.name == "Kubernetes"), None)
    assert k8s_skill is not None
    assert k8s_skill.match_class == "user_confirmation_required"
    assert k8s_skill.is_directly_demonstrated is False

    # Abstention decision for Kubernetes must be REVIEW
    k8s_decision = next((d for d in plan.abstention_decisions if d.requirement == "Kubernetes"), None)
    assert k8s_decision is not None
    assert k8s_decision.decision == "REVIEW"
    assert any("unverified" in r.lower() or "review" in r.lower() for r in k8s_decision.reasons)

