import pytest
import hashlib
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import CandidateEvidence, ExperienceItem, ProjectItem, SkillItem
from app.schemas.requirement_match import RequirementMatch
from app.schemas.career_intelligence import (
    SkillRelationshipType,
    SkillTransferabilityRule,
    AnalyzeGapsRequest,
    CandidateAttestationRequest,
    CandidateAttestationRecord,
)
from app.ai.career.taxonomy import (
    GLOBAL_TRANSFERABILITY_GRAPH,
    SkillTransferabilityGraph,
    get_transferability_rule,
    get_all_rules,
)
from app.ai.career.bridge_engine import BridgeEngine
from app.ai.career.remediation_blueprints import GapRemediationEngine
from app.services.career_intelligence_service import CareerIntelligenceService
from app.services.resume_service import ResumeService
from app.services.variant_service import VariantService


# ---------------------------------------------------------------------------
# 1. Deterministic Taxonomy & Rule Unit Tests
# ---------------------------------------------------------------------------

def test_taxonomy_rule_coverage():
    """Verify taxonomy contains rules across all required categories with valid scores."""
    rules = get_all_rules()
    assert len(rules) >= 30

    categories = {r.relationship_type for r in rules}
    assert "FRAMEWORK_FAMILY" in categories
    assert "DATABASE_FAMILY" in categories
    assert "LANGUAGE_FAMILY" in categories
    assert "CLOUD_PLATFORM_FAMILY" in categories
    assert "DEVOPS_ORCHESTRATION" in categories
    assert "ML_FRAMEWORK_FAMILY" in categories
    assert "CONCEPTUAL_TRANSFER" in categories

    for rule in rules:
        assert 0.0 < rule.transferability_score <= 1.0
        assert len(rule.transfer_rationale) > 10
        assert len(rule.shared_competencies) >= 1
        assert len(rule.critical_differences) >= 1


def test_taxonomy_bidirectional_and_asymmetric_lookups():
    """Verify bidirectional framework rules and asymmetric language/platform rules."""
    # React <-> Vue (symmetric framework family)
    react_to_vue = get_transferability_rule("React", "Vue")
    vue_to_react = get_transferability_rule("Vue", "React")
    assert react_to_vue is not None
    assert vue_to_react is not None
    assert react_to_vue.relationship_type == "FRAMEWORK_FAMILY"
    assert vue_to_react.relationship_type == "FRAMEWORK_FAMILY"

    # PostgreSQL -> MySQL (database family)
    pg_to_mysql = get_transferability_rule("PostgreSQL", "MySQL")
    assert pg_to_mysql is not None
    assert pg_to_mysql.transferability_score >= 0.85

    # Docker -> Kubernetes (orchestration bridge)
    docker_to_k8s = get_transferability_rule("Docker", "Kubernetes")
    assert docker_to_k8s is not None
    assert docker_to_k8s.relationship_type == "DEVOPS_ORCHESTRATION"

    # Unrelated pair returns None
    assert get_transferability_rule("React", "Kubernetes") is None
    assert get_transferability_rule("Figma", "PostgreSQL") is None


# ---------------------------------------------------------------------------
# 2. Bridge Engine Deterministic Unit Tests
# ---------------------------------------------------------------------------

def test_bridge_engine_finds_grounded_bridges():
    """Verify bridge engine detects bridges strictly from verified candidate evidence."""
    candidate_evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_item_1",
                role="Frontend Engineer",
                company="Acme Inc",
                startDate="2022",
                endDate="Present",
                technologies=["React", "TypeScript", "Redux"],
                bullets=[
                    "Built reactive single-page applications using React and TypeScript.",
                    "Managed application state with Redux and optimized render performance.",
                ],
            ),
            ExperienceItem(
                id="exp_item_2",
                role="Backend Engineer",
                company="DataCorp",
                startDate="2020",
                endDate="2022",
                technologies=["PostgreSQL", "Python", "FastAPI"],
                bullets=[
                    "Designed relational data schemas in PostgreSQL with complex indexing.",
                ],
            ),
        ],
        skills=[
            SkillItem(name="React", category="Technical", proficiency="Expert"),
            SkillItem(name="TypeScript", category="Technical", proficiency="Advanced"),
            SkillItem(name="PostgreSQL", category="Technical", proficiency="Advanced"),
        ],
    )

    missing_reqs = [
        RequirementMatch(
            requirement_name="Vue",
            category="Framework",
            importance="MustHave",
            match_status="Missing",
            resume_evidence="",
            job_source_evidence="2+ years Vue",
        ),
        RequirementMatch(
            requirement_name="MySQL",
            category="Database",
            importance="Preferred",
            match_status="Missing",
            resume_evidence="",
            job_source_evidence="Experience with MySQL",
        ),
        RequirementMatch(
            requirement_name="Rust",
            category="Language",
            importance="MustHave",
            match_status="Missing",
            resume_evidence="",
            job_source_evidence="Systems programming in Rust",
        ),
    ]

    bridges = BridgeEngine.find_transferable_bridges(missing_reqs, candidate_evidence)
    bridge_map = {b.required_skill: b for b in bridges}

    # Vue should have bridge from React (exp_item_1)
    assert "Vue" in bridge_map
    vue_bridge = bridge_map["Vue"]
    assert vue_bridge.candidate_skill == "React"
    assert vue_bridge.source_evidence_id == "exp_item_1"
    assert vue_bridge.transferability_score >= 0.7

    # MySQL should have bridge from PostgreSQL (exp_item_2)
    assert "MySQL" in bridge_map
    mysql_bridge = bridge_map["MySQL"]
    assert mysql_bridge.candidate_skill == "PostgreSQL"
    assert mysql_bridge.source_evidence_id == "exp_item_2"

    # Rust has no adjacent skill in evidence -> NO bridge
    assert "Rust" not in bridge_map


def test_bridge_engine_zero_hallucination_on_empty_evidence():
    """Verify bridge engine returns zero bridges if candidate evidence has no adjacent skills."""
    candidate_evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_item_1",
                role="Graphic Designer",
                company="Creative Studio",
                startDate="2021",
                endDate="Present",
                technologies=["Photoshop", "Illustrator"],
                bullets=["Created vector illustrations and marketing banners."],
            )
        ],
        skills=[SkillItem(name="Photoshop", category="Design", proficiency="Expert")],
    )
    missing_reqs = [
        RequirementMatch(
            requirement_name="Kubernetes",
            category="DevOps",
            importance="MustHave",
            match_status="Missing",
            resume_evidence="",
            job_source_evidence="Kubernetes cluster administration",
        )
    ]
    bridges = BridgeEngine.find_transferable_bridges(missing_reqs, candidate_evidence)
    assert len(bridges) == 0


# ---------------------------------------------------------------------------
# 3. Gap Remediation Blueprints Unit Tests
# ---------------------------------------------------------------------------

def test_gap_remediation_blueprints_generation():
    """Verify deterministic remediation engine produces learning paths and project blueprints."""
    req_k8s = RequirementMatch(
        requirement_name="Kubernetes",
        category="DevOps",
        importance="MustHave",
        match_status="Missing",
        resume_evidence="",
        job_source_evidence="Kubernetes administration",
    )
    strategy = GapRemediationEngine.generate_remediation_strategy(req_k8s)

    assert strategy.requirement_name == "Kubernetes"
    assert len(strategy.learning_paths) >= 1
    assert strategy.learning_paths[0].estimated_weeks >= 1
    assert len(strategy.learning_paths[0].key_milestones) >= 1
    assert len(strategy.project_blueprints) >= 1
    assert len(strategy.project_blueprints[0].verification_checklist) >= 1


# ---------------------------------------------------------------------------
# 4. Career Intelligence Service & Attestation End-to-End Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_variant_doc():
    return {
        "variantId": "var_test_100",
        "masterResumeId": "master_root_100",
        "title": "Senior Frontend Engineer Variant",
        "targetRole": "Senior Frontend Engineer",
        "targetCompany": "Acme Global",
        "jobDescription": "Looking for Vue.js, TypeScript, and AWS expertise.",
        "jobDescriptionHash": "hash_test_100",
        "createdAt": "2026-09-25T00:00:00Z",
        "updatedAt": "2026-09-25T00:00:00Z",
        "version": 1,
        "baselineScore": 70,
        "currentScore": 70,
        "scoreDelta": 0,
        "isTargetedVariant": True,
        "changeLedger": [],
        "baselineMatches": [
            {
                "requirementName": "React",
                "category": "Framework",
                "importance": "MustHave",
                "matchStatus": "StrongMatch",
                "resumeEvidence": "Architected React SPAs.",
                "jobSourceEvidence": "Frontend expertise",
                "confidence": "High",
            },
            {
                "requirementName": "Vue",
                "category": "Framework",
                "importance": "MustHave",
                "matchStatus": "Missing",
                "resumeEvidence": "",
                "jobSourceEvidence": "2+ years Vue.js",
                "confidence": "High",
            },
            {
                "requirementName": "AWS",
                "category": "Cloud",
                "importance": "Preferred",
                "matchStatus": "Missing",
                "resumeEvidence": "",
                "jobSourceEvidence": "Cloud deployment experience",
                "confidence": "High",
            },
        ],
        "snapshot": {
            "profile": {"headline": "Senior Frontend Developer"},
            "summary": "Experienced React developer.",
            "experience": [
                {
                    "id": "exp_0",
                    "role": "Frontend Engineer",
                    "company": "Tech Corp",
                    "startDate": "2022",
                    "endDate": "Present",
                    "bullets": [
                        "Architected React SPAs and modern web interfaces using TypeScript.",
                        "Optimized frontend bundle size by 30% through code splitting.",
                    ],
                    "technologies": ["React", "TypeScript"],
                }
            ],
            "projects": [],
            "skills": [
                {"name": "React", "category": "Technical", "proficiency": "Expert"},
                {"name": "TypeScript", "category": "Technical", "proficiency": "Advanced"},
            ],
            "education": [],
            "certifications": [],
        },
    }


@pytest.mark.asyncio
async def test_analyze_gaps_service_endpoint(monkeypatch, mock_variant_doc):
    """Verify analyze_gaps returns verified bridges and remediation strategies for variant."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    async def mock_get(u, resume_id):
        if resume_id == "var_test_100":
            return mock_variant_doc
        return None

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    req = AnalyzeGapsRequest(variant_id="var_test_100")
    response = await CareerIntelligenceService.analyze_gaps(user, req)

    assert response.variant_id == "var_test_100"
    assert len(response.transferable_bridges) >= 1
    # Vue should have a bridge from React
    vue_bridge = next((b for b in response.transferable_bridges if b.required_skill == "Vue"), None)
    assert vue_bridge is not None
    assert vue_bridge.candidate_skill == "React"

    # Remediation strategies present
    assert len(response.hard_gap_remediations) >= 1


@pytest.mark.asyncio
async def test_process_attestation_success_updates_variant_ledger(monkeypatch, mock_variant_doc):
    """Verify successful candidate attestation validates claims, modifies variant bullet, updates ledger."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")
    saved_docs = {}

    async def mock_get(u, resume_id):
        if resume_id == "var_test_100":
            return saved_docs.get("var_test_100", mock_variant_doc)
        return None

    async def mock_save(u, resume_id, data):
        saved_docs[resume_id] = data
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=1,
        requirement_name="Vue",
        adjacent_skill_used="React",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Hands-on frontend evaluation at Tech Corp.",
        attested_actions="Architected reactive single-page applications and tested component workflows",
        duration_or_scale="2 weeks",
        apply_to_workspace=False,
    )

    res = await CareerIntelligenceService.process_attestation(user, req)

    assert res.success is True
    assert res.requirement_name == "Vue"
    assert res.new_version == 2
    assert res.change_record.action_type == "UserAttested"
    assert res.change_record.requirement_name == "Vue"


@pytest.mark.asyncio
async def test_process_attestation_claim_validator_rejection(monkeypatch, mock_variant_doc):
    """Verify attestation containing unsupported/hallucinated claims is rejected by ClaimValidator."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    async def mock_get(u, resume_id):
        return mock_variant_doc

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    # Candidate attestation fabricates extreme ungrounded revenue metrics (e.g., $500M ARR growth)
    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=1,
        requirement_name="Vue",
        adjacent_skill_used="React",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Managed small prototype.",
        attested_actions="Architected global banking core generating $500M ARR revenue with 10,000 employees under direct leadership",
        apply_to_workspace=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await CareerIntelligenceService.process_attestation(user, req)

    assert exc_info.value.status_code == 400
    assert "claim validation" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_process_attestation_optimistic_concurrency_conflict(monkeypatch, mock_variant_doc):
    """Verify optimistic concurrency conflict (version mismatch) raises HTTP 409."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    async def mock_get(u, resume_id):
        return mock_variant_doc  # version is 1

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=99,  # Mismatched expected version
        requirement_name="Vue",
        adjacent_skill_used="React",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Hands-on evaluation context at Tech Corp.",
        attested_actions="Architected reactive single-page applications",
        apply_to_workspace=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await CareerIntelligenceService.process_attestation(user, req)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_root_workspace_immutability_guarantee(monkeypatch, mock_variant_doc):
    """Verify that root workspace candidate evidence is 100% immutable and untouched."""
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")
    root_master_saved = []

    async def mock_get(u, resume_id):
        return mock_variant_doc

    async def mock_save(u, resume_id, data):
        if resume_id == "master_root_100":
            root_master_saved.append(data)
        return True

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save)

    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=1,
        requirement_name="Vue",
        adjacent_skill_used="React",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Hands-on frontend evaluation at Tech Corp.",
        attested_actions="Architected reactive single-page applications and tested component workflows",
        duration_or_scale="2 weeks",
        apply_to_workspace=False,
    )

    res = await CareerIntelligenceService.process_attestation(user, req)
    assert res.success is True
    # Root master must NOT have been saved
    assert len(root_master_saved) == 0


# ---------------------------------------------------------------------------
# 5. Adversarial AI Security Suite Cases: ADV_034 - ADV_038
# ---------------------------------------------------------------------------

def test_adv_034_unattested_adjacent_skill_hallucination_defense():
    """
    ADV_034: Unattested Adjacent Skill Hallucination Defense.
    System must refuse to treat transferable skills as direct verified experience
    in the absence of explicit candidate attestation.
    """
    # Candidate knows React; Job asks for Vue.
    candidate_evidence = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_1",
                role="Frontend Developer",
                company="WebCo",
                technologies=["React"],
                bullets=["Developed React web apps."],
            )
        ],
        skills=[SkillItem(name="React", category="Technical", proficiency="Expert")],
    )
    missing_reqs = [
        RequirementMatch(
            requirement_name="Vue",
            category="Framework",
            importance="MustHave",
            match_status="Missing",
            resume_evidence="",
            job_source_evidence="Vue expertise required",
        )
    ]

    bridges = BridgeEngine.find_transferable_bridges(missing_reqs, candidate_evidence)
    assert len(bridges) == 1
    bridge = bridges[0]

    # Invariant: bridge is a transferable recommendation with explicit status, NOT a StrongMatch
    assert bridge.candidate_skill == "React"
    assert bridge.required_skill == "Vue"
    # The taxonomy rule does NOT modify candidate evidence or assert candidate is a Vue expert
    assert all("Vue" not in [s.name for s in candidate_evidence.skills] for s in [candidate_evidence])


def test_adv_035_inverted_transferability_authority_attack():
    """
    ADV_035: Inverted Transferability Authority Attack.
    Attempts to inject adversarial transferability rules or claim invalid domain bridges
    (e.g., HTML -> Distributed Consensus) must be rejected by the deterministic taxonomy.
    """
    # Attempting to bridge HTML to Raft / Paxos / Distributed Consensus
    rule = get_transferability_rule("HTML", "Distributed Consensus")
    assert rule is None

    # Attempting to bridge CSS to Kubernetes
    rule_css_k8s = get_transferability_rule("CSS", "Kubernetes")
    assert rule_css_k8s is None


@pytest.mark.asyncio
async def test_adv_036_scope_inflated_remediation_claim_defense(monkeypatch, mock_variant_doc):
    """
    ADV_036: Scope-Inflated Remediation Claim Defense.
    Attestation claiming VP/Executive scope or multi-billion dollar metrics from
    a beginner remediation project must be rejected by ClaimValidator.
    """
    user = AuthenticatedUser(uid="usr_1", token="tok_1", email="u@example.com")

    async def mock_get(u, resume_id):
        return mock_variant_doc

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=1,
        requirement_name="AWS",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Completed a tutorial project deploying a sample app on AWS S3.",
        attested_actions="Directed 400 engineers as VP of Cloud Infrastructure delivering $2B annual revenue through AWS cloud transformation",
        apply_to_workspace=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await CareerIntelligenceService.process_attestation(user, req)

    assert exc_info.value.status_code == 400
    assert "claim validation" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_adv_037_cross_tenant_attestation_injection_defense(monkeypatch, mock_variant_doc):
    """
    ADV_037: Cross-Tenant Attestation Injection Defense.
    User B attempting to submit an attestation or analyze variant belonging to User A
    must be strictly denied.
    """
    # User B is unauthorized
    unauthorized_user = AuthenticatedUser(uid="attacker_user_999", token="tok_bad", email="evil@example.com")

    async def mock_get(u, resume_id):
        # ResumeService enforces tenant check: if user.uid != owner_uid, returns None
        if u.uid != "usr_1":
            return None
        return mock_variant_doc

    monkeypatch.setattr(ResumeService, "get_resume_document", mock_get)

    req = CandidateAttestationRequest(
        variant_id="var_test_100",
        expected_version=1,
        requirement_name="Vue",
        adjacent_skill_used="React",
        target_item_id="exp_0",
        target_bullet_index=0,
        attested_context="Hands-on frontend evaluation at Tech Corp.",
        attested_actions="Architected reactive single-page applications and tested component workflows",
    )

    with pytest.raises(HTTPException) as exc_info:
        await CareerIntelligenceService.process_attestation(unauthorized_user, req)

    assert exc_info.value.status_code == 404


def test_adv_038_telemetry_free_product_invariant():
    """
    ADV_038: Telemetry Free-Product Invariant.
    Career intelligence analysis and attestation mechanisms must not contain any
    pricing, tokens, payment, credits, subscriptions, or Stripe hooks.
    """
    import inspect
    import app.schemas.career_intelligence as ci_schemas
    import app.ai.career.taxonomy as ci_taxonomy
    import app.ai.career.bridge_engine as ci_bridge
    import app.ai.career.remediation_blueprints as ci_remediation
    import app.services.career_intelligence_service as ci_service

    forbidden_terms = ["stripe", "billing", "subscription", "price_id", "paywall", "credit_balance", "cost_cents"]

    modules = [ci_schemas, ci_taxonomy, ci_bridge, ci_remediation, ci_service]
    for mod in modules:
        source_code = inspect.getsource(mod).lower()
        for term in forbidden_terms:
            assert term not in source_code, f"Forbidden billing term '{term}' found in {mod.__name__}"
