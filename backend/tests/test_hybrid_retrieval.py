import pytest
from app.schemas.job_description import (
    StructuredJobDescription,
    JobInfo,
    SkillRequirement,
)
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
)
from app.schemas.evidence import EvidenceItem
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph
from app.ai.retrieval.hybrid_matcher import HybridMatcher, find_related_technology
from app.ai.retrieval.evidence_ranker import EvidenceRanker, RankedEvidenceItem


@pytest.fixture
def candidate_with_docker_react_js():
    """Candidate profile with Docker, React, JavaScript, and Machine Learning (explicitly lacking K8s, Angular, TS, DL)."""
    candidate = CandidateEvidence(
        headline="Full Stack & DevOps Engineer",
        summary="Building scalable web apps and containerized services.",
        experience=[
            ExperienceItem(
                id="exp_0",
                role="Senior Engineer",
                company="TechCorp",
                start_date="2023",
                end_date="Present",
                bullets=["Built React web portal and containerized backend microservices with Docker handling 50k RPS."],
                technologies=["React", "JavaScript", "Docker", "Python"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="ML Data Pipeline",
                description="Machine Learning model serving pipeline.",
                highlights=["Processed 10M events with 99.9% accuracy."],
                tech_stack=["Python", "Machine Learning", "Docker"],
            )
        ],
        skills=[
            SkillItem(name="JavaScript", category="Language", proficiency="Expert"),
            SkillItem(name="React", category="Framework", proficiency="Expert"),
            SkillItem(name="Docker", category="DevOps", proficiency="Expert"),
            SkillItem(name="Machine Learning", category="Domain", proficiency="Intermediate"),
            SkillItem(name="PostgreSQL", category="Database", proficiency="Intermediate"),
        ],
    )
    items = EvidenceService.normalize_candidate_evidence("user_retrieval_test", candidate)
    return CareerEvidenceGraph(user_id="user_retrieval_test", items=items)


def test_exact_matches(candidate_with_docker_react_js):
    """Verifies that direct matching produces direct_match with full provenance."""
    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="Senior Frontend Engineer", seniority_level="Senior"),
        must_have_skills=[
            SkillRequirement(name="React", category="Framework", importance="MustHave"),
            SkillRequirement(name="Docker", category="DevOps", importance="MustHave"),
        ],
        preferred_skills=[
            SkillRequirement(name="JavaScript", category="Language", importance="Preferred"),
        ],
    )

    result = HybridMatcher.match_job_requirements(jd, candidate_with_docker_react_js)

    assert result.direct_match_count == 3
    assert result.missing_count == 0
    assert result.related_unverified_count == 0

    react_match = next(m for m in result.matches if m.requirement_name == "React")
    assert react_match.match_class == "direct_match"
    assert react_match.matched_technology == "React"
    assert len(react_match.candidate_evidence_ids) >= 1
    assert any("experience" in p or "projects" in p for p in react_match.provenance_sources)

    docker_match = next(m for m in result.matches if m.requirement_name == "Docker")
    assert docker_match.match_class == "direct_match"
    assert docker_match.matched_technology == "Docker"


def test_non_equivalence_guards(candidate_with_docker_react_js):
    """
    CRITICAL NON-EQUIVALENCE TEST:
    - Candidate has Docker -> JD requires Kubernetes -> related_but_unverified (NOT direct_match)
    - Candidate has JS -> JD requires TypeScript -> related_but_unverified (NOT direct_match)
    - Candidate has React -> JD requires Angular -> related_but_unverified (NOT direct_match)
    - Candidate has Machine Learning -> JD requires Deep Learning -> related_but_unverified (NOT direct_match)
    """
    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="Cloud Engineer", seniority_level="Mid"),
        must_have_skills=[
            SkillRequirement(name="Kubernetes", category="DevOps", importance="MustHave"),
            SkillRequirement(name="TypeScript", category="Language", importance="MustHave"),
            SkillRequirement(name="Angular", category="Framework", importance="MustHave"),
            SkillRequirement(name="Deep Learning", category="Domain", importance="MustHave"),
        ],
        preferred_skills=[
            SkillRequirement(name="Rust", category="Language", importance="Preferred"),
        ],
    )

    result = HybridMatcher.match_job_requirements(jd, candidate_with_docker_react_js)

    # NONE of these 4 non-equivalent requirements may become direct_match
    assert result.direct_match_count == 0
    assert result.related_unverified_count == 4
    assert result.missing_count == 1  # Rust is completely missing

    # 1. Kubernetes check
    k8s_match = next(m for m in result.matches if m.requirement_name == "Kubernetes")
    assert k8s_match.match_class == "related_but_unverified"
    assert k8s_match.matched_technology == "Docker"
    assert "Docker" in k8s_match.explanation
    assert "not explicitly verified" in k8s_match.explanation

    # 2. TypeScript check
    ts_match = next(m for m in result.matches if m.requirement_name == "TypeScript")
    assert ts_match.match_class == "related_but_unverified"
    assert ts_match.matched_technology == "JavaScript"
    assert "JavaScript" in ts_match.explanation

    # 3. Angular check
    angular_match = next(m for m in result.matches if m.requirement_name == "Angular")
    assert angular_match.match_class == "related_but_unverified"
    assert angular_match.matched_technology == "React"

    # 4. Deep Learning check
    dl_match = next(m for m in result.matches if m.requirement_name == "Deep Learning")
    assert dl_match.match_class == "related_but_unverified"
    assert dl_match.matched_technology == "Machine Learning"

    # 5. Rust check (no related technology in candidate evidence)
    rust_match = next(m for m in result.matches if m.requirement_name == "Rust")
    assert rust_match.match_class == "missing"
    assert rust_match.matched_technology is None


def test_user_confirmation_required_for_standalone_tags():
    """Verifies that a MustHave requirement appearing only as a skill tag requires confirmation."""
    candidate = CandidateEvidence(
        skills=[SkillItem(name="Redis", category="Database", proficiency="Intermediate")]
    )
    items = EvidenceService.normalize_candidate_evidence("user_tag_test", candidate)
    graph = CareerEvidenceGraph(user_id="user_tag_test", items=items)

    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="Backend Engineer"),
        must_have_skills=[SkillRequirement(name="Redis", category="Database", importance="MustHave")],
    )

    result = HybridMatcher.match_job_requirements(jd, graph)
    assert result.user_confirmation_count == 1
    redis_match = result.matches[0]
    assert redis_match.match_class == "user_confirmation_required"
    assert "lacks accomplishment bullets" in redis_match.explanation


def test_evidence_ranking_multi_factor():
    """Verifies that EvidenceRanker scores relevant, metric-rich items above irrelevant items."""
    item_relevant = EvidenceItem(
        evidenceId="ev_exp_0",
        userId="user_rank_test",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Senior Backend Engineer at Stripe",
        description="Engineered Python microservices processing 10k QPS with 99.99% uptime.",
        skills=["Python", "FastAPI", "PostgreSQL"],
        technologies=["Python", "FastAPI", "PostgreSQL"],
        responsibilities=["Engineered Python microservices."],
        achievements=["Processed 10k QPS with 99.99% uptime."],
        metrics=["10k QPS", "99.99%"],
        dates="2023 - Present",
        role="Senior Backend Engineer",
        domain="Engineering",
        verificationStatus="verified",
        confidence=1.0,
    )

    item_irrelevant = EvidenceItem(
        evidenceId="ev_exp_1",
        userId="user_rank_test",
        sourceType="experience",
        sourceItemId="exp_1",
        title="Marketing Coordinator at RetailCo",
        description="Managed social media campaigns.",
        skills=["Social Media", "Copywriting"],
        technologies=[],
        responsibilities=["Managed social media campaigns."],
        achievements=[],
        metrics=[],
        dates="2018 - 2019",
        role="Marketing Coordinator",
        domain="Marketing",
        verificationStatus="verified",
        confidence=1.0,
    )

    ranked = EvidenceRanker.rank_evidence(
        items=[item_irrelevant, item_relevant],
        target_role="Senior Python Backend Engineer",
        job_description="Looking for a Python Backend Engineer with FastAPI and PostgreSQL experience.",
        must_have_skills=["Python", "FastAPI"],
    )

    assert len(ranked) == 2
    # Relevant item must rank #1 with significantly higher score
    assert ranked[0].evidence_item.evidence_id == "ev_exp_0"
    assert ranked[0].rank_score > ranked[1].rank_score
    assert "Python" in ranked[0].matched_skills
    assert ranked[0].score_breakdown["metricsStrength"] == 1.0


def test_empty_workspace_hybrid_matching():
    """Verifies that an empty workspace produces 0 matches and 100% missing requirements."""
    empty_graph = CareerEvidenceGraph(user_id="empty_user", items=[])

    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="Backend Engineer"),
        must_have_skills=[
            SkillRequirement(name="Go", category="Language", importance="MustHave"),
            SkillRequirement(name="gRPC", category="Tool", importance="MustHave"),
        ],
    )

    result = HybridMatcher.match_job_requirements(jd, empty_graph)
    assert result.direct_match_count == 0
    assert result.related_unverified_count == 0
    assert result.missing_count == 2
    assert result.overall_coverage_score == 0.0


def test_parse_job_description_deterministic():
    """Verifies deterministic JD parsing extracts seniority, skills, and must-have/preferred split."""
    jd_text = """
    We are looking for a Senior Full Stack Engineer.
    Must have experience with React, TypeScript, and Docker.
    Preferred qualifications:
    Experience with GraphQL and AWS.
    """
    structured = HybridMatcher.parse_job_description_deterministic(
        target_role="Senior Full Stack Engineer",
        job_description_text=jd_text,
    )

    assert structured.job_info.seniority_level == "Senior"
    assert structured.job_info.role_title == "Senior Full Stack Engineer"
    must_have_names = [s.name for s in structured.must_have_skills]
    assert "React" in must_have_names
    assert "TypeScript" in must_have_names
    assert "Docker" in must_have_names

    preferred_names = [s.name for s in structured.preferred_skills]
    assert "GraphQL" in preferred_names or "AWS" in preferred_names


def test_rank_and_select_evidence_hybrid_matcher_integration():
    """
    Verifies that rank_and_select_evidence runs HybridMatcher and prioritizes
    direct-matched evidence over non-matching evidence in the production pipeline.
    """
    from app.services.resume_generation_service import rank_and_select_evidence

    candidate = CandidateEvidence(
        headline="Software Engineer",
        summary="Polyglot developer.",
        experience=[
            ExperienceItem(
                id="exp_python",
                role="Python Backend Engineer",
                company="PyCo",
                start_date="2022",
                end_date="Present",
                bullets=["Developed Django REST APIs with PostgreSQL."],
                technologies=["Python", "Django", "PostgreSQL"],
            ),
            ExperienceItem(
                id="exp_react",
                role="Frontend Engineer",
                company="WebCo",
                start_date="2021",
                end_date="2022",
                bullets=["Built React UI components."],
                technologies=["React", "JavaScript", "CSS"],
            ),
        ],
        projects=[
            ProjectItem(
                id="proj_python",
                title="Data Scraper",
                description="Scraping system in Python.",
                tech_stack=["Python"],
            ),
            ProjectItem(
                id="proj_react",
                title="Design System",
                description="Component library in React.",
                tech_stack=["React", "Storybook"],
            ),
        ],
        skills=[
            SkillItem(name="Python", category="Language", proficiency="Expert"),
            SkillItem(name="React", category="Framework", proficiency="Expert"),
        ],
    )

    # 1. Target: React Role -> React items must be selected first
    react_jd = "Looking for a Senior React Engineer with deep React knowledge."
    exp_react_sel, proj_react_sel, skills_react_sel = rank_and_select_evidence(
        evidence=candidate,
        target_role="Senior React Engineer",
        job_description=react_jd,
        max_experience=1,
        max_projects=1,
    )

    assert len(exp_react_sel) == 1
    assert exp_react_sel[0].id == "exp_react"
    assert len(proj_react_sel) == 1
    assert proj_react_sel[0].id == "proj_react"
    assert skills_react_sel[0].name == "React"

    # 2. Target: Python Role -> Python items must be selected first
    python_jd = "Looking for a Python Backend Developer experienced with Django."
    exp_py_sel, proj_py_sel, skills_py_sel = rank_and_select_evidence(
        evidence=candidate,
        target_role="Python Backend Developer",
        job_description=python_jd,
        max_experience=1,
        max_projects=1,
    )

    assert len(exp_py_sel) == 1
    assert exp_py_sel[0].id == "exp_python"
    assert len(proj_py_sel) == 1
    assert proj_py_sel[0].id == "proj_python"
    assert skills_py_sel[0].name == "Python"


def test_related_not_promoted_to_direct_in_rank_and_select():
    """
    Verifies that when JD requires Kubernetes, an experience with Docker is classified as
    related_but_unverified by HybridMatcher and does NOT receive direct match promotion.
    """
    from app.services.resume_generation_service import rank_and_select_evidence

    candidate = CandidateEvidence(
        headline="DevOps Specialist",
        experience=[
            ExperienceItem(
                id="exp_docker",
                role="DevOps Engineer",
                company="CloudCo",
                start_date="2020",
                end_date="2021",
                bullets=["Managed Docker containers."],
                technologies=["Docker"],
            ),
            ExperienceItem(
                id="exp_k8s_direct",
                role="Cloud Platform Engineer",
                company="ScaleCo",
                start_date="2022",
                end_date="Present",
                bullets=["Architected Kubernetes clusters."],
                technologies=["Kubernetes"],
            ),
        ],
        skills=[
            SkillItem(name="Docker", category="DevOps"),
            SkillItem(name="Kubernetes", category="DevOps"),
        ],
    )

    # JD requires Kubernetes explicitly
    k8s_jd = "Required: Kubernetes cluster management."
    exp_sel, _, _ = rank_and_select_evidence(
        evidence=candidate,
        target_role="Kubernetes Engineer",
        job_description=k8s_jd,
        max_experience=1,
    )

    # exp_k8s_direct has true direct match, whereas exp_docker only has related tech
    assert exp_sel[0].id == "exp_k8s_direct"


# ===========================================================================
# HYBRID RETRIEVAL FOUNDATION TESTS (10 Required Verification Scenarios)
# ===========================================================================

@pytest.fixture
def sample_hybrid_evidence_items():
    """Synthetic dataset of normalized evidence items for retrieval testing."""
    item1 = EvidenceItem(
        evidenceId="ev_http_fastapi",
        userId="user_hybrid_test",
        sourceType="experience",
        sourceItemId="exp_fastapi",
        title="Senior Backend Engineer at CloudScale",
        description="Built production HTTP microservices and web services using FastAPI and Python handling 100k requests daily.",
        role="Senior Backend Engineer",
        skills=["Python", "FastAPI"],
        technologies=["Python", "FastAPI", "PostgreSQL"],
        responsibilities=["Built production HTTP microservices."],
        achievements=["Handled 100k requests daily."],
        metrics=["100k requests daily"],
        dates="2023 - Present",
        confidence=1.0,
    )
    item2 = EvidenceItem(
        evidenceId="ev_frontend_react",
        userId="user_hybrid_test",
        sourceType="experience",
        sourceItemId="exp_react",
        title="Frontend Specialist at WebCorp",
        description="Built responsive user interfaces and web applications using React and JavaScript.",
        role="Frontend Specialist",
        skills=["JavaScript", "React"],
        technologies=["JavaScript", "React", "CSS"],
        responsibilities=["Built responsive UI."],
        achievements=[],
        metrics=[],
        dates="2021 - 2022",
        confidence=1.0,
    )
    item3 = EvidenceItem(
        evidenceId="ev_devops_k8s",
        userId="user_hybrid_test",
        sourceType="experience",
        sourceItemId="exp_k8s",
        title="Platform Engineer at InfraCo",
        description="Architected Kubernetes clusters and automated container orchestration workflows.",
        role="Platform Engineer",
        skills=["Kubernetes"],
        technologies=["Kubernetes", "Linux"],
        responsibilities=["Architected Kubernetes clusters."],
        achievements=[],
        metrics=[],
        dates="2022 - 2023",
        confidence=1.0,
    )
    return [item1, item2, item3]


# Test 1 — Exact match
@pytest.mark.asyncio
async def test_exact_match_retrieval_signal(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore
    
    retriever = HybridRetriever(store=InMemoryVectorStore())
    candidates = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Senior Backend Engineer",
        query_text="Seeking FastAPI and Python developer.",
        must_have_skills=["Python", "FastAPI"],
        candidate_items=sample_hybrid_evidence_items,
    )

    assert len(candidates) > 0
    top_candidate = candidates[0]
    assert top_candidate.evidence_id == "ev_http_fastapi"
    assert top_candidate.exact_score > 0.5
    assert "Python" in top_candidate.matched_skills or "FastAPI" in top_candidate.matched_skills
    assert "exact_lexical" in top_candidate.retrieval_sources


# Test 2 — Dense semantic match with different wording
@pytest.mark.asyncio
async def test_dense_semantic_match_different_wording(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore
    
    retriever = HybridRetriever(store=InMemoryVectorStore())
    # JD uses "Develop scalable REST APIs" (evidence has "Built production HTTP microservices using FastAPI")
    candidates = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="API Architect",
        query_text="Develop scalable REST APIs for cloud services.",
        candidate_items=sample_hybrid_evidence_items,
        enable_semantic=True,
    )

    fastapi_cand = next((c for c in candidates if c.evidence_id == "ev_http_fastapi"), None)
    assert fastapi_cand is not None
    assert fastapi_cand.semantic_score is not None
    assert fastapi_cand.semantic_score > 0.3
    assert "dense_semantic" in fastapi_cand.retrieval_sources


# Test 3 — Non-equivalence: TypeScript vs JavaScript
def test_non_equivalence_typescript_javascript():
    from app.ai.retrieval import HybridMatcher, find_related_technology
    
    # Candidate has JavaScript only
    cand_techs = {"javascript"}
    related = find_related_technology("TypeScript", cand_techs)
    assert related == "JavaScript"

    # In HybridMatcher, must remain related_but_unverified
    cand = CandidateEvidence(
        skills=[SkillItem(name="JavaScript", category="Language")]
    )
    items = EvidenceService.normalize_candidate_evidence("user_ts_test", cand)
    graph = CareerEvidenceGraph(user_id="user_ts_test", items=items)

    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="TypeScript Developer"),
        must_have_skills=[SkillRequirement(name="TypeScript", category="Language", importance="MustHave")],
    )

    res = HybridMatcher.match_job_requirements(jd, graph)
    ts_match = res.matches[0]
    assert ts_match.match_class == "related_but_unverified"
    assert ts_match.matched_technology == "JavaScript"
    assert res.direct_match_count == 0


# Test 4 — Docker vs Kubernetes non-equivalence
def test_non_equivalence_docker_kubernetes():
    from app.ai.retrieval import HybridMatcher, find_related_technology
    
    cand = CandidateEvidence(
        skills=[SkillItem(name="Kubernetes", category="DevOps")]
    )
    items = EvidenceService.normalize_candidate_evidence("user_k8s_test", cand)
    graph = CareerEvidenceGraph(user_id="user_k8s_test", items=items)

    jd = StructuredJobDescription(
        job_info=JobInfo(role_title="Docker Specialist"),
        must_have_skills=[SkillRequirement(name="Docker", category="DevOps", importance="MustHave")],
    )

    res = HybridMatcher.match_job_requirements(jd, graph)
    docker_match = res.matches[0]
    assert docker_match.match_class == "related_but_unverified"
    assert docker_match.matched_technology == "Kubernetes"
    assert res.direct_match_count == 0


# Test 5 — Hybrid fusion deterministic ranking
@pytest.mark.asyncio
async def test_hybrid_fusion_deterministic_ranking(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore, WEIGHT_EXACT, WEIGHT_SEMANTIC
    
    assert round(WEIGHT_EXACT + WEIGHT_SEMANTIC, 2) == 1.00

    retriever = HybridRetriever(store=InMemoryVectorStore())
    candidates = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Full Stack Engineer",
        query_text="Looking for Python, FastAPI, and React developers.",
        must_have_skills=["Python", "React"],
        candidate_items=sample_hybrid_evidence_items,
    )

    assert len(candidates) == len(sample_hybrid_evidence_items)
    for c in candidates:
        assert 0.0 <= c.fused_score <= 1.0
        if c.semantic_score is not None:
            expected_fused = round((WEIGHT_EXACT * c.exact_score) + (WEIGHT_SEMANTIC * c.semantic_score), 4)
            assert abs(c.fused_score - expected_fused) < 0.001


# Test 6 — Semantic provider failure graceful fallback
@pytest.mark.asyncio
async def test_semantic_provider_failure_fallback(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, MockEmbeddingProvider, InMemoryVectorStore
    
    # Fault injection: provider throws exception
    failing_provider = MockEmbeddingProvider(should_fail=True)
    retriever = HybridRetriever(embedding_provider=failing_provider, store=InMemoryVectorStore())

    # Retrieval must not raise exception, gracefully falling back to exact
    candidates = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Backend Developer",
        query_text="Python and FastAPI",
        must_have_skills=["Python"],
        candidate_items=sample_hybrid_evidence_items,
        enable_semantic=True,
    )

    assert len(candidates) > 0
    top = candidates[0]
    assert top.evidence_id == "ev_http_fastapi"
    assert top.exact_score > 0.0
    assert top.semantic_score is None
    assert top.fused_score == top.exact_score


# Test 7 — User isolation boundary
@pytest.mark.asyncio
async def test_user_isolation_boundary(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore
    
    store = InMemoryVectorStore()
    retriever = HybridRetriever(store=store)

    # Index evidence explicitly owned by User A
    user_a_items = [
        item.model_copy(update={"user_id": "user_A", "evidence_id": f"a_{item.evidence_id}"})
        for item in sample_hybrid_evidence_items
    ]
    await retriever.index_evidence_items(user_id="user_A", items=user_a_items)
    assert store.total_count(user_id="user_A") == 3
    assert store.total_count(user_id="user_B") == 0

    # User B queries: MUST return 0 results from vector store
    candidates_b = await retriever.retrieve_candidates(
        user_id="user_B",
        target_role="Backend Engineer",
        query_text="FastAPI Python",
        candidate_items=[],  # No items for User B
    )
    assert len(candidates_b) == 0


# Test 8 — Stale embedding invalidation
@pytest.mark.asyncio
async def test_stale_embedding_invalidation(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore, compute_evidence_content
    
    store = InMemoryVectorStore()
    retriever = HybridRetriever(store=store)

    # 1. Initial index
    new_indexed = await retriever.index_evidence_items("user_hybrid_test", sample_hybrid_evidence_items)
    assert new_indexed == 3

    # 2. Modify description of item 1
    modified_item = sample_hybrid_evidence_items[0].model_copy(deep=True)
    modified_item.description = "Completely rewritten description with Go and Rust gRPC services."
    modified_item.technologies = ["Go", "Rust", "gRPC"]

    _, current_hash = compute_evidence_content(modified_item)
    assert store.is_stale("user_hybrid_test", modified_item.evidence_id, current_hash) is True

    # 3. Re-index recognizes stale item and updates embedding
    updated_count = await retriever.index_evidence_items("user_hybrid_test", [modified_item])
    assert updated_count == 1
    assert store.is_stale("user_hybrid_test", modified_item.evidence_id, current_hash) is False


# Test 9 — Reusable embeddings caching
@pytest.mark.asyncio
async def test_reusable_embeddings_caching(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore, MockEmbeddingProvider
    
    mock_provider = MockEmbeddingProvider()
    store = InMemoryVectorStore()
    retriever = HybridRetriever(embedding_provider=mock_provider, store=store)

    # First pass: embeds 3 items
    count1 = await retriever.index_evidence_items("user_hybrid_test", sample_hybrid_evidence_items)
    assert count1 == 3
    initial_calls = mock_provider.call_count

    # Second pass with same unchanged items: 0 new embeddings
    count2 = await retriever.index_evidence_items("user_hybrid_test", sample_hybrid_evidence_items)
    assert count2 == 0
    assert mock_provider.call_count == initial_calls  # No unnecessary API calls!


# Test 10 — Evaluation fixture across 5 retrieval scenarios
@pytest.mark.asyncio
async def test_retrieval_evaluation_fixture(sample_hybrid_evidence_items):
    from app.ai.retrieval import HybridRetriever, InMemoryVectorStore
    
    retriever = HybridRetriever(store=InMemoryVectorStore())
    
    # Scenario 1: Exact skill match (React) -> Top is React item
    cand_react = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Frontend Engineer",
        query_text="React specialist",
        must_have_skills=["React"],
        candidate_items=sample_hybrid_evidence_items,
    )
    assert cand_react[0].evidence_id == "ev_frontend_react"

    # Scenario 2: Semantic paraphrase (HTTP microservices -> REST API) -> Top is FastAPI item
    cand_api = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="API Engineer",
        query_text="RESTful HTTP endpoint developer",
        candidate_items=sample_hybrid_evidence_items,
    )
    assert cand_api[0].evidence_id == "ev_http_fastapi"

    # Scenario 3: DevOps container orchestration -> Top is K8s item
    cand_devops = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Cloud Infrastructure Engineer",
        query_text="Container orchestration and cluster architecture",
        candidate_items=sample_hybrid_evidence_items,
    )
    assert cand_devops[0].evidence_id == "ev_devops_k8s"

    # Scenario 4: Weakly related / unrelated query -> Low scores across items
    cand_unrelated = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Graphic Designer",
        query_text="Adobe Photoshop, Figma, Typography, Print Design",
        candidate_items=sample_hybrid_evidence_items,
    )
    assert all(c.exact_score < 0.2 for c in cand_unrelated)

    # Scenario 5: Non-equivalent technology (Docker query on K8s item) -> Exact score 0 for Docker
    cand_docker = await retriever.retrieve_candidates(
        user_id="user_hybrid_test",
        target_role="Docker Specialist",
        query_text="Docker container builds",
        must_have_skills=["Docker"],
        candidate_items=sample_hybrid_evidence_items,
    )
    # K8s item should not get exact score for Docker
    k8s_res = next(c for c in cand_docker if c.evidence_id == "ev_devops_k8s")
    assert "Docker" not in k8s_res.matched_skills


