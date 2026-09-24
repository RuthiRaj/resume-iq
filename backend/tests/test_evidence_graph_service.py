import pytest
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.evidence import EvidenceGraphQuery
from app.services.evidence_service import EvidenceService
from app.services.evidence_graph_service import CareerEvidenceGraph


@pytest.fixture
def sample_graph():
    candidate = CandidateEvidence(
        headline="Senior Full Stack Engineer",
        summary="Building high-scale web apps using React and Python.",
        experience=[
            ExperienceItem(
                id="exp_0",
                role="Senior Full Stack Engineer",
                company="Airbnb",
                start_date="2021",
                end_date="Present",
                bullets=["Engineered search interface in React serving 50M users with 99.9% uptime."],
                technologies=["React", "TypeScript", "GraphQL", "Python"],
            ),
            ExperienceItem(
                id="exp_1",
                role="Backend Engineer",
                company="Stripe",
                start_date="2019",
                end_date="2021",
                bullets=["Built distributed billing microservices processing $20M daily."],
                technologies=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            ),
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Cloud Monitoring Dashboard",
                role="Creator",
                description="Real-time dashboard using React and Tailwind CSS.",
                highlights=["Visualized 100k data points in real time."],
                tech_stack=["React", "Tailwind CSS", "WebSockets"],
            ),
            ProjectItem(
                id="proj_1",
                title="Distributed KV Engine",
                role="Author",
                description="Fast in-memory key-value store in Go.",
                highlights=["Benchmarked at 500k ops/sec."],
                tech_stack=["Go", "gRPC"],
            ),
        ],
        skills=[
            SkillItem(name="React", category="Framework", proficiency="Expert"),
            SkillItem(name="Python", category="Language", proficiency="Expert"),
            SkillItem(name="PostgreSQL", category="Database", proficiency="Intermediate"),
            SkillItem(name="Kubernetes", category="DevOps", proficiency="Intermediate"),
        ],
        education=[
            EducationItem(
                degree="B.S.",
                institution="Stanford University",
                field_of_study="Computer Science",
            )
        ],
        certifications=[
            CertificationItem(
                title="AWS Certified Solutions Architect",
                issuer="Amazon Web Services",
            )
        ],
    )

    items = EvidenceService.normalize_candidate_evidence("user_abc_123", candidate)
    return CareerEvidenceGraph(user_id="user_abc_123", items=items)


def test_find_by_skill(sample_graph):
    """Verifies that find_by_skill retrieves all items demonstrating React."""
    react_items = sample_graph.find_by_skill("React")
    assert len(react_items) >= 3  # exp_0 (Airbnb), proj_0 (Dashboard), and skill_0 (React tag)
    titles = [item.title for item in react_items]
    assert any("Airbnb" in t for t in titles)
    assert any("Dashboard" in t for t in titles)


def test_find_by_technology(sample_graph):
    """Verifies that find_by_technology finds items using Python."""
    python_items = sample_graph.find_by_technology("Python")
    assert len(python_items) >= 3  # exp_0, exp_1, skill
    sources = [item.source_type for item in python_items]
    assert "experience" in sources


def test_find_by_role(sample_graph):
    """Verifies searching evidence by role keyword."""
    backend_items = sample_graph.find_by_role("Backend")
    assert len(backend_items) == 1
    assert backend_items[0].source_item_id == "exp_1"
    assert "Stripe" in backend_items[0].title


def test_find_by_source_type(sample_graph):
    """Verifies filtering evidence by source type."""
    projects = sample_graph.find_by_source_type("projects")
    assert len(projects) == 2
    proj_ids = [p.source_item_id for p in projects]
    assert "proj_0" in proj_ids
    assert "proj_1" in proj_ids


def test_find_by_metric_presence(sample_graph):
    """Verifies retrieving only evidence items with quantifiable metrics."""
    metric_items = sample_graph.find_by_metric_presence()
    assert len(metric_items) >= 3  # exp_0 (50M, 99.9%), exp_1 ($20M), proj_0 (100k)
    for item in metric_items:
        assert len(item.metrics) > 0


def test_get_skills_and_technologies_demonstrated(sample_graph):
    """Verifies comprehensive unique list of demonstrated skills and tech."""
    skills = sample_graph.get_skills_demonstrated()
    assert "react" in skills
    assert "python" in skills
    assert "postgresql" in skills
    assert "go" in skills

    techs = sample_graph.get_technologies_demonstrated()
    assert "graphql" in techs
    assert "docker" in techs
    assert "aws" in techs


def test_provenance_retrieval(sample_graph):
    """Verifies provenance tracking for an evidence ID."""
    prov = sample_graph.get_provenance("ev_exp_0")
    assert prov is not None
    assert prov["evidenceId"] == "ev_exp_0"
    assert prov["sourceType"] == "experience"
    assert prov["sourceItemId"] == "exp_0"
    assert "Airbnb" in prov["title"]

    assert sample_graph.get_provenance("non_existent_id") is None


def test_complex_graph_query(sample_graph):
    """Verifies multi-criteria graph querying."""
    query = EvidenceGraphQuery(
        skill="Python",
        sourceType="experience",
        hasMetrics=True,
    )
    result = sample_graph.query(query)
    assert result.total_count >= 1
    for item in result.items:
        assert item.source_type == "experience"
        assert len(item.metrics) > 0


def test_graph_cross_user_isolation():
    """Verifies that an EvidenceGraph rejects items belonging to a different user."""
    candidate = CandidateEvidence(
        experience=[
            ExperienceItem(
                id="exp_other",
                role="Other Role",
                company="Other Co",
                bullets=["Did something"],
                technologies=["Rust"],
            )
        ]
    )
    items_user_x = EvidenceService.normalize_candidate_evidence("user_x", candidate)

    # Graph instantiated for user_y must ignore items from user_x
    graph_user_y = CareerEvidenceGraph(user_id="user_y", items=items_user_x)
    assert len(graph_user_y._items_by_id) == 0
    assert graph_user_y.find_by_skill("Rust") == []
