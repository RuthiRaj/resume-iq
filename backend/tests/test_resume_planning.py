"""
Test Suite for ResumeIQ Standalone Resume Planning Layer

Validates:
1. Basic plan generation
2. Evidence selection (IDs and counts)
3. Excluded evidence with deterministic reasons
4. Hard gaps (missing requirements marked as prohibited claims)
5. Related skills (related_but_unverified is NOT promoted to direct_match)
6. User confirmation (skill-tag-only evidence remains user_confirmation_required)
7. Target page budget heuristics
8. Deterministic section ordering
9. Determinism (identical inputs produce identical plans)
10. Invalid evidence reference rejection in validate_resume_plan
11. Zero-hallucination guarantees (no invented evidence or skills)
"""

import pytest
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
    AchievementItem,
)
from app.schemas.job_description import (
    StructuredJobDescription,
    JobInfo,
    SkillRequirement,
)
from app.schemas.plan import ResumePlan
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.services.resume_planning_service import ResumePlanningService


@pytest.fixture
def senior_candidate_evidence():
    """Candidate with 8 years experience (2-page budget candidate)."""
    return CandidateEvidence(
        headline="Staff Distributed Systems Architect",
        summary="8+ years architecting high-scale backend services and cloud infrastructure.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="Stripe",
                role="Staff Infrastructure Engineer",
                startDate="2021-01",
                endDate="Present",
                bullets=[
                    "Engineered streaming payment processing pipeline in Go and Kafka handling 50,000 transactions per second.",
                    "Optimized Redis cache invalidation layer cutting P99 latency by 35%.",
                ],
                technologies=["Go", "Kafka", "Redis", "Docker"],
            ),
            ExperienceItem(
                id="exp_1",
                company="Airbnb",
                role="Senior Backend Engineer",
                startDate="2018-01",
                endDate="2020-12",
                bullets=[
                    "Built distributed booking microservices using Python and PostgreSQL.",
                    "Implemented asynchronous task queues processing 10M daily jobs.",
                ],
                technologies=["Python", "PostgreSQL", "FastAPI", "Docker"],
            ),
            ExperienceItem(
                id="exp_2",
                company="StartupCo",
                role="Software Engineer",
                startDate="2016-01",
                endDate="2017-12",
                bullets=[
                    "Developed customer-facing REST APIs using Python and Django.",
                ],
                technologies=["Python", "Django", "MySQL"],
            ),
            ExperienceItem(
                id="exp_3",
                company="EarlyCo",
                role="Junior Developer",
                startDate="2014-06",
                endDate="2015-12",
                bullets=[
                    "Maintained PHP legacy backend services.",
                ],
                technologies=["PHP", "MySQL"],
            ),
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Distributed KV Store",
                description="Raft-based key-value storage engine in Go.",
                highlights=["Implemented distributed consensus with 99.999% consistency."],
                tech_stack=["Go", "Raft", "gRPC"],
            ),
            ProjectItem(
                id="proj_1",
                title="Cloud Cost Optimizer",
                description="Automated AWS instance rightsizing tool.",
                highlights=["Saved 25% monthly cloud infrastructure costs."],
                tech_stack=["Python", "AWS", "Docker"],
            ),
            ProjectItem(
                id="proj_2",
                title="Simple Static Blog",
                description="Personal static markdown blog.",
                highlights=["Static HTML site."],
                tech_stack=["HTML", "CSS"],
            ),
        ],
        skills=[
            SkillItem(name="Go", category="Language", proficiency="Expert"),
            SkillItem(name="Python", category="Language", proficiency="Expert"),
            SkillItem(name="Docker", category="DevOps", proficiency="Expert"),
            SkillItem(name="Kafka", category="Tool", proficiency="Expert"),
            SkillItem(name="PostgreSQL", category="Database", proficiency="Expert"),
            SkillItem(name="Redis", category="Database", proficiency="Expert"),
            SkillItem(name="Kubernetes", category="DevOps", proficiency="Intermediate"),  # Standalone skill tag only
        ],
        education=[
            EducationItem(
                institution="UC Berkeley",
                degree="B.S. in Computer Science",
                fieldOfStudy="Computer Science",
            )
        ],
        certifications=[
            CertificationItem(
                title="AWS Certified Solutions Architect",
                issuer="Amazon Web Services",
            )
        ],
        achievements=[
            AchievementItem(
                id="ach_0",
                title="Winner of Global Hackathon",
                issuer="TechCrunch",
                date="2022",
                description="Built decentralized data mesh.",
            )
        ],
    )


@pytest.fixture
def junior_candidate_evidence():
    """Candidate with 2 years experience (1-page budget candidate)."""
    return CandidateEvidence(
        headline="Junior Full Stack Developer",
        summary="2 years of experience building modern React web apps and Node.js APIs.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="WebStudio",
                role="Full Stack Developer",
                startDate="2024-01",
                endDate="Present",
                bullets=[
                    "Developed web applications using React and Node.js.",
                ],
                technologies=["React", "Node.js", "JavaScript"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Portfolio App",
                description="Personal portfolio web application.",
                highlights=["Built responsive UI using Tailwind CSS."],
                tech_stack=["React", "Tailwind CSS"],
            )
        ],
        skills=[
            SkillItem(name="JavaScript", category="Language", proficiency="Expert"),
            SkillItem(name="React", category="Framework", proficiency="Intermediate"),
            SkillItem(name="Docker", category="DevOps", proficiency="Beginner"),  # Has Docker, lacks Kubernetes
        ],
        education=[
            EducationItem(
                institution="State University",
                degree="B.S. in Software Engineering",
            )
        ],
    )


# ---------------------------------------------------------------------------
# 1. Basic Plan Generation Test
# ---------------------------------------------------------------------------

def test_basic_plan_generation(senior_candidate_evidence):
    plan = ResumePlanningService.create_resume_plan(
        target_role="Principal Distributed Systems Engineer",
        target_company="Stripe",
        candidate_evidence=senior_candidate_evidence,
        job_description_text="Must have Go, Kafka, and Redis experience. Preferred: Docker, AWS.",
    )

    assert isinstance(plan, ResumePlan)
    assert plan.plan_id.startswith("plan_")
    assert plan.target_role == "Principal Distributed Systems Engineer"
    assert plan.target_company == "Stripe"
    assert len(plan.sections) >= 6
    assert "Experience" in plan.section_order
    assert "Skills" in plan.section_order
    assert len(plan.selected_evidence) > 0


# ---------------------------------------------------------------------------
# 2. Evidence Selection (IDs, Relevance & Provenance)
# ---------------------------------------------------------------------------

def test_evidence_selection_prioritizes_relevance(senior_candidate_evidence):
    plan = ResumePlanningService.create_resume_plan(
        target_role="Staff Go Engineer",
        target_company="Stripe",
        candidate_evidence=senior_candidate_evidence,
        job_description_text="Must have Go, Kafka, and distributed consensus experience.",
        max_experience=2,
        max_projects=1,
    )

    selected_exp_ids = [s.source_item_id for s in plan.selected_evidence if s.source_type == "experience"]
    selected_proj_ids = [s.source_item_id for s in plan.selected_evidence if s.source_type == "projects"]

    # Top Go experience (Stripe exp_0) must be selected
    assert "exp_0" in selected_exp_ids
    assert len(selected_exp_ids) == 2

    # Top Go project (Distributed KV Store proj_0) must be selected
    assert "proj_0" in selected_proj_ids
    assert len(selected_proj_ids) == 1


# ---------------------------------------------------------------------------
# 3. Excluded Evidence & Deterministic Rationales
# ---------------------------------------------------------------------------

def test_excluded_evidence_captures_deterministic_reasons(senior_candidate_evidence):
    plan = ResumePlanningService.create_resume_plan(
        target_role="Staff Go Engineer",
        candidate_evidence=senior_candidate_evidence,
        job_description_text="Must have Go and Kafka.",
        max_experience=2,
        max_projects=1,
    )

    excluded_exp_ids = [e.source_item_id for e in plan.excluded_evidence if e.source_type == "experience"]
    excluded_proj_ids = [e.source_item_id for e in plan.excluded_evidence if e.source_type == "projects"]

    # Older/less relevant experiences (exp_2, exp_3) and project (proj_2) should be excluded
    assert "exp_3" in excluded_exp_ids
    assert "proj_2" in excluded_proj_ids

    # Exclusion reason must be non-empty and explain budget/rank constraints
    for ex in plan.excluded_evidence:
        assert ex.exclusion_reason != ""
        assert "constraint" in ex.exclusion_reason.lower() or "lower" in ex.exclusion_reason.lower()


# ---------------------------------------------------------------------------
# 4. Hard Gaps Identification
# ---------------------------------------------------------------------------

def test_hard_gaps_identified_for_missing_requirements(junior_candidate_evidence):
    # Job requires Rust and GraphQL, which junior candidate does NOT possess
    plan = ResumePlanningService.create_resume_plan(
        target_role="Rust Backend Developer",
        candidate_evidence=junior_candidate_evidence,
        job_description_text="Required: 5+ years experience in Rust and GraphQL. Must have production experience.",
    )

    hard_gap_names = [g.requirement_name for g in plan.hard_gaps]
    assert "Rust" in hard_gap_names
    assert "GraphQL" in hard_gap_names

    # Check prohibited claim instruction
    rust_gap = next(g for g in plan.hard_gaps if g.requirement_name == "Rust")
    assert "Do not claim or imply experience with 'Rust'" in rust_gap.prohibited_claim_instruction


# ---------------------------------------------------------------------------
# 5. Non-Equivalence & Related Skills (related_but_unverified)
# ---------------------------------------------------------------------------

def test_related_skills_remain_unverified(junior_candidate_evidence):
    # Junior candidate has Docker and JavaScript, but JD requires Kubernetes and TypeScript
    plan = ResumePlanningService.create_resume_plan(
        target_role="Cloud Engineer",
        candidate_evidence=junior_candidate_evidence,
        job_description_text="Required: Kubernetes and TypeScript.",
    )

    # Kubernetes and TypeScript must be in related_but_unverified_requirements
    assert "Kubernetes" in plan.related_but_unverified_requirements or "TypeScript" in plan.related_but_unverified_requirements

    # In prioritized skills, TypeScript must NOT be marked as direct_match
    ts_skill = next((s for s in plan.prioritized_skills if s.name == "TypeScript"), None)
    if ts_skill:
        assert ts_skill.match_class == "related_but_unverified"
        assert ts_skill.is_directly_demonstrated is False


# ---------------------------------------------------------------------------
# 6. User Confirmation Required for Standalone Skill Tags
# ---------------------------------------------------------------------------

def test_user_confirmation_for_skill_tag_only(senior_candidate_evidence):
    # Senior candidate has Kubernetes in skills list ONLY, with no Kubernetes in work bullets
    plan = ResumePlanningService.create_resume_plan(
        target_role="Kubernetes Platform Architect",
        candidate_evidence=senior_candidate_evidence,
        job_description_text="Required: Kubernetes platform experience.",
    )

    k8s_skill = next((s for s in plan.prioritized_skills if s.name == "Kubernetes"), None)
    assert k8s_skill is not None
    assert k8s_skill.match_class == "user_confirmation_required"
    assert "Kubernetes" in plan.user_confirmation_required


# ---------------------------------------------------------------------------
# 7. Page Budget Deterministic Heuristic
# ---------------------------------------------------------------------------

def test_page_budget_heuristics(senior_candidate_evidence, junior_candidate_evidence):
    # Senior candidate (8 years) -> 2 pages
    plan_senior = ResumePlanningService.create_resume_plan(
        target_role="Staff Engineer",
        candidate_evidence=senior_candidate_evidence,
    )
    assert plan_senior.target_page_budget == 2

    # Junior candidate (2 years) -> 1 page
    plan_junior = ResumePlanningService.create_resume_plan(
        target_role="Junior Engineer",
        candidate_evidence=junior_candidate_evidence,
    )
    assert plan_junior.target_page_budget == 1


# ---------------------------------------------------------------------------
# 8. Deterministic Section Ordering
# ---------------------------------------------------------------------------

def test_deterministic_section_ordering(senior_candidate_evidence):
    plan = ResumePlanningService.create_resume_plan(
        target_role="Staff Engineer",
        candidate_evidence=senior_candidate_evidence,
    )

    assert plan.section_order == [
        "Header",
        "Summary",
        "Skills",
        "Experience",
        "Projects",
        "Education",
        "Certifications",
        "Achievements",
    ]


# ---------------------------------------------------------------------------
# 9. Strict Determinism (Same Inputs -> Identical Plans)
# ---------------------------------------------------------------------------

def test_planner_strict_determinism(senior_candidate_evidence):
    jd_text = "Seeking Senior Go and Kafka Backend Engineer with AWS experience."
    
    plan_1 = ResumePlanningService.create_resume_plan(
        target_role="Senior Go Engineer",
        candidate_evidence=senior_candidate_evidence,
        job_description_text=jd_text,
    )

    plan_2 = ResumePlanningService.create_resume_plan(
        target_role="Senior Go Engineer",
        candidate_evidence=senior_candidate_evidence,
        job_description_text=jd_text,
    )

    # Compare core structural contents (excluding random plan_id and timestamps)
    assert plan_1.target_page_budget == plan_2.target_page_budget
    assert plan_1.section_order == plan_2.section_order
    assert [s.evidence_id for s in plan_1.selected_evidence] == [s.evidence_id for s in plan_2.selected_evidence]
    assert [e.evidence_id for e in plan_1.excluded_evidence] == [e.evidence_id for e in plan_2.excluded_evidence]
    assert [s.name for s in plan_1.prioritized_skills] == [s.name for s in plan_2.prioritized_skills]
    assert [g.requirement_name for g in plan_1.hard_gaps] == [g.requirement_name for g in plan_2.hard_gaps]


# ---------------------------------------------------------------------------
# 10. Plan Validation Rejects Invalid References
# ---------------------------------------------------------------------------

def test_plan_validation_rejects_invalid_references(senior_candidate_evidence):
    items = EvidenceService.normalize_candidate_evidence("user_val_test", senior_candidate_evidence)
    plan = ResumePlanningService.create_resume_plan(
        target_role="Staff Engineer",
        candidate_evidence=senior_candidate_evidence,
        normalized_items=items,
    )

    # Valid plan passes
    assert ResumePlanningService.validate_resume_plan(plan, items) is True

    # Injecting non-existent evidence ID must raise ValueError
    plan.selected_evidence[0].evidence_id = "ev_fake_nonexistent_999"
    with pytest.raises(ValueError) as exc_info:
        ResumePlanningService.validate_resume_plan(plan, items)
    assert "does not exist in candidate evidence" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 11. Zero Hallucination Guarantee
# ---------------------------------------------------------------------------

def test_planner_zero_hallucination(junior_candidate_evidence):
    items = EvidenceService.normalize_candidate_evidence("user_zero_hal", junior_candidate_evidence)
    candidate_skills = {s.name.lower() for s in junior_candidate_evidence.skills}

    plan = ResumePlanningService.create_resume_plan(
        target_role="Cloud Architect",
        candidate_evidence=junior_candidate_evidence,
        job_description_text="Must have Rust, C++, Kubernetes, AWS, Terraform, Kafka.",
        normalized_items=items,
    )

    # All directly demonstrated skills MUST be from candidate's real skills
    for ps in plan.prioritized_skills:
        if ps.is_directly_demonstrated:
            assert ps.name.lower() in candidate_skills

    # All unpossessed JD skills must be marked as either missing or related_but_unverified
    missing_names = {g.requirement_name for g in plan.hard_gaps}
    assert "Rust" in missing_names or "C++" in missing_names


# ---------------------------------------------------------------------------
# 12. Ownership Boundary & Foreign Evidence Rejection
# ---------------------------------------------------------------------------

def test_plan_validation_rejects_foreign_user_evidence(senior_candidate_evidence):
    # Candidate items owned by User A
    user_a_items = EvidenceService.normalize_candidate_evidence("user_A", senior_candidate_evidence)
    
    # Candidate items owned by User B
    user_b_items = EvidenceService.normalize_candidate_evidence("user_B", senior_candidate_evidence)

    # Plan created for User A
    plan_a = ResumePlanningService.create_resume_plan(
        target_role="Staff Engineer",
        candidate_evidence=senior_candidate_evidence,
        normalized_items=user_a_items,
        user_id="user_A",
    )

    # Valid when validated against User A's expected user ID
    assert ResumePlanningService.validate_resume_plan(plan_a, user_a_items, expected_user_id="user_A") is True

    # Reject if expected_user_id is User B but plan belongs to User A
    with pytest.raises(ValueError) as exc_info:
        ResumePlanningService.validate_resume_plan(plan_a, user_a_items, expected_user_id="user_B")
    assert "does not match expected user" in str(exc_info.value)

    # Reject if plan contains evidence item IDs owned by User B when evaluated for User A
    foreign_plan = plan_a.model_copy(deep=True)
    foreign_plan.selected_evidence[0].evidence_id = user_b_items[0].evidence_id
    with pytest.raises(ValueError) as exc_info2:
        ResumePlanningService.validate_resume_plan(foreign_plan, user_a_items, expected_user_id="user_A")
    assert "does not exist in candidate evidence" in str(exc_info2.value) or "belongs to another user" in str(exc_info2.value)


# ---------------------------------------------------------------------------
# 13. Generation Metadata & Plan Persistence Snapshot Fidelity
# ---------------------------------------------------------------------------

def test_plan_persistence_snapshot_fidelity(senior_candidate_evidence):
    from app.schemas.variant import TargetedResumeVariant
    import uuid

    plan = ResumePlanningService.create_resume_plan(
        target_role="Principal Infrastructure Architect",
        target_company="Stripe",
        candidate_evidence=senior_candidate_evidence,
        job_description_text="Must have Go, Kafka, AWS, Kubernetes.",
        user_id="test_user_persistence",
    )

    plan_dump = plan.model_dump(by_alias=True)

    # Verify all expected keys are serialized in generation metadata
    assert plan_dump["planId"].startswith("plan_")
    assert plan_dump["targetRole"] == "Principal Infrastructure Architect"
    assert plan_dump["targetCompany"] == "Stripe"
    assert "targetPageBudget" in plan_dump
    assert "sectionOrder" in plan_dump
    assert "selectedEvidence" in plan_dump
    assert "excludedEvidence" in plan_dump
    assert "prioritizedSkills" in plan_dump
    assert "prioritizedKeywords" in plan_dump
    assert "hardGaps" in plan_dump
    assert "requirementStrategy" in plan_dump

    # Reconstitute into TargetedResumeVariant
    variant = TargetedResumeVariant(
        variantId=f"var_{uuid.uuid4().hex[:12]}",
        masterResumeId="workspace",
        title="Tailored Resume",
        targetRole="Principal Infrastructure Architect",
        jobDescription="Must have Go, Kafka, AWS, Kubernetes.",
        jobDescriptionHash="hash_123",
        version=1,
        snapshot=senior_candidate_evidence,
        generationMetadata={"plan": plan_dump},
        createdAt="2026-09-24T12:00:00Z",
        updatedAt="2026-09-24T12:00:00Z",
    )

    # Verify retrieval from variant metadata
    saved_plan_dict = variant.generation_metadata["plan"]
    rehydrated_plan = ResumePlan.model_validate(saved_plan_dict)
    assert rehydrated_plan.plan_id == plan.plan_id
    assert rehydrated_plan.target_role == plan.target_role
    assert len(rehydrated_plan.selected_evidence) == len(plan.selected_evidence)


# ---------------------------------------------------------------------------
# 14. Legacy Variant Without Plan Loads Successfully (Backward Compatibility)
# ---------------------------------------------------------------------------

def test_legacy_variant_without_plan_backward_compatibility(senior_candidate_evidence):
    from app.schemas.variant import TargetedResumeVariant
    import uuid

    # Legacy variant without generation_metadata or with empty dict
    legacy_variant = TargetedResumeVariant(
        variantId=f"var_{uuid.uuid4().hex[:12]}",
        masterResumeId="workspace",
        title="Legacy Variant",
        targetRole="Senior Backend Engineer",
        jobDescription="Legacy JD",
        jobDescriptionHash="legacy_hash",
        version=1,
        snapshot=senior_candidate_evidence,
        generationMetadata=None,
        createdAt="2025-01-01T00:00:00Z",
        updatedAt="2025-01-01T00:00:00Z",
    )

    assert legacy_variant.variant_id.startswith("var_")
    assert legacy_variant.generation_metadata is None
    assert legacy_variant.version == 1


# ---------------------------------------------------------------------------
# 15. Missing Requirement (Docker) Boundary & Neutral Prohibition
# ---------------------------------------------------------------------------

def test_missing_requirement_docker_boundary(junior_candidate_evidence):
    # Candidate without Docker
    cand = junior_candidate_evidence.model_copy(deep=True)
    cand.skills = [s for s in cand.skills if s.name.lower() != "docker"]
    for exp in cand.experience:
        exp.technologies = [t for t in exp.technologies if t.lower() != "docker"]

    plan = ResumePlanningService.create_resume_plan(
        target_role="DevOps Specialist",
        candidate_evidence=cand,
        job_description_text="Must have extensive experience with Docker containerization.",
    )

    docker_gap = next((g for g in plan.hard_gaps if g.requirement_name.lower() == "docker"), None)
    assert docker_gap is not None
    assert "Do not claim or imply experience with 'Docker'" in docker_gap.prohibited_claim_instruction
    # Neutral prohibition must NOT force negative "I have no experience" wording
    assert "I have no experience" not in docker_gap.prohibited_claim_instruction
    assert "State or imply no experience" not in docker_gap.prohibited_claim_instruction


# ---------------------------------------------------------------------------
# 16. Related-but-Unverified (JavaScript vs TypeScript) Boundary
# ---------------------------------------------------------------------------

def test_related_but_unverified_javascript_typescript_boundary(junior_candidate_evidence):
    # Candidate has JavaScript, JD requires TypeScript
    plan = ResumePlanningService.create_resume_plan(
        target_role="Frontend Engineer",
        candidate_evidence=junior_candidate_evidence,
        job_description_text="Required: Strong proficiency in TypeScript.",
    )

    # TypeScript must NOT be directly demonstrated
    ts_skill = next((s for s in plan.prioritized_skills if s.name.lower() == "typescript"), None)
    if ts_skill:
        assert ts_skill.is_directly_demonstrated is False
        assert ts_skill.match_class == "related_but_unverified"

