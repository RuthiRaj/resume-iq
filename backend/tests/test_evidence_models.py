import pytest
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
    AchievementItem,
    InternshipItem,
    PublicationItem,
    AwardItem,
    VolunteeringItem,
)
from app.schemas.evidence import (
    EvidenceItem,
    EvidenceRelationship,
    EvidenceGraphQuery,
    EvidenceQueryResult,
)


def test_candidate_evidence_backward_compatibility():
    """Verifies that old candidate JSON payloads without the new collections load cleanly."""
    legacy_payload = {
        "headline": "Full Stack Engineer",
        "summary": "Building scalable web services.",
        "experience": [
            {
                "id": "exp_0",
                "role": "Software Engineer",
                "company": "Tech Corp",
                "bullets": ["Built API endpoints handling 5k req/s"],
                "technologies": ["Python", "FastAPI"],
            }
        ],
        "projects": [],
        "skills": [{"name": "Python", "category": "Language", "proficiency": "Expert"}],
        "education": [],
        "certifications": [],
        "achievements": [],
    }

    evidence = CandidateEvidence.model_validate(legacy_payload)
    assert evidence.headline == "Full Stack Engineer"
    assert len(evidence.experience) == 1
    # New categories must default to empty lists
    assert evidence.internships == []
    assert evidence.publications == []
    assert evidence.awards == []
    assert evidence.volunteering == []


def test_candidate_evidence_with_new_categories():
    """Verifies that extended workspace categories serialize and deserialize correctly."""
    payload = {
        "headline": "AI Researcher",
        "summary": "Conducting deep learning research.",
        "internships": [
            {
                "id": "intern_0",
                "role": "Research Intern",
                "company": "Deep Labs",
                "bullets": ["Trained transformer models"],
                "technologies": ["PyTorch", "CUDA"],
            }
        ],
        "publications": [
            {
                "id": "pub_0",
                "title": "Scaling Law for Transformers",
                "publisher": "NeurIPS",
                "publicationDate": "2025",
            }
        ],
        "awards": [
            {
                "id": "award_0",
                "title": "Best Paper Award",
                "issuer": "NeurIPS",
                "date": "2025",
            }
        ],
        "volunteering": [
            {
                "id": "vol_0",
                "role": "Mentor",
                "organization": "Open Source Initiative",
                "highlights": ["Mentored 15 junior engineers"],
            }
        ],
    }

    evidence = CandidateEvidence.model_validate(payload)
    assert len(evidence.internships) == 1
    assert evidence.internships[0].company == "Deep Labs"
    assert len(evidence.publications) == 1
    assert evidence.publications[0].title == "Scaling Law for Transformers"
    assert len(evidence.awards) == 1
    assert evidence.awards[0].title == "Best Paper Award"
    assert len(evidence.volunteering) == 1
    assert evidence.volunteering[0].role == "Mentor"


def test_evidence_item_schema_and_serialization():
    """Verifies EvidenceItem field validation and alias serialization."""
    item = EvidenceItem(
        evidenceId="ev_exp_0",
        userId="user_12345",
        sourceType="experience",
        sourceItemId="exp_0",
        title="Software Engineer at Stripe",
        description="Engineered payment pipeline.",
        skills=["Python", "FastAPI"],
        technologies=["Python", "FastAPI", "PostgreSQL"],
        responsibilities=["Engineered payment pipeline."],
        achievements=["Processed $10M daily volume with 99.99% uptime."],
        metrics=["$10M", "99.99%"],
        dates="2023 - Present",
        role="Software Engineer",
        domain="Engineering",
        verificationStatus="verified",
        confidence=1.0,
    )

    dumped = item.model_dump(by_alias=True)
    assert dumped["evidenceId"] == "ev_exp_0"
    assert dumped["userId"] == "user_12345"
    assert dumped["sourceType"] == "experience"
    assert dumped["sourceItemId"] == "exp_0"
    assert "$10M" in dumped["metrics"]
    assert dumped["verificationStatus"] == "verified"
    assert dumped["confidence"] == 1.0


def test_evidence_relationship_schema():
    """Verifies EvidenceRelationship model serialization."""
    rel = EvidenceRelationship(
        sourceEvidenceId="ev_exp_0",
        targetId="Python",
        targetType="Skill",
        relationshipType="demonstrates_skill",
        metadata={"depth": "production"},
    )

    dumped = rel.model_dump(by_alias=True)
    assert dumped["sourceEvidenceId"] == "ev_exp_0"
    assert dumped["targetId"] == "Python"
    assert dumped["relationshipType"] == "demonstrates_skill"


def test_evidence_graph_query_and_result():
    """Verifies EvidenceGraphQuery and EvidenceQueryResult validation."""
    query = EvidenceGraphQuery(
        skill="FastAPI",
        sourceType="experience",
        hasMetrics=True,
        minConfidence=0.9,
    )
    assert query.skill == "FastAPI"
    assert query.source_type == "experience"
    assert query.has_metrics is True
    assert query.min_confidence == 0.9

    result = EvidenceQueryResult(
        items=[],
        totalCount=0,
        skillsMatched=["FastAPI"],
        technologiesMatched=["Python", "FastAPI"],
    )
    assert result.total_count == 0
    assert "FastAPI" in result.skills_matched
