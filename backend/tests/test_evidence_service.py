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
from app.services.evidence_service import EvidenceService, extract_metrics_from_text


def test_extract_metrics_from_text():
    """Verifies that verifiable numbers, percentages, and scale metrics are deterministically extracted."""
    text = "Improved system latency by 45% and reduced memory usage to 256MB for 100k daily active users saving $50k monthly."
    metrics = extract_metrics_from_text(text)
    assert any("45%" in m for m in metrics)
    assert any("$50k" in m or "$50" in m for m in metrics)
    assert any("100k" in m for m in metrics)
    assert any("latency" in m.lower() or "reduced" in m.lower() or "improved" in m.lower() for m in metrics)


def test_extract_metrics_from_empty_text():
    assert extract_metrics_from_text("") == []
    assert extract_metrics_from_text("Developed web application with Python.") == []


def test_normalize_candidate_evidence_all_categories():
    """Verifies that all 11 workspace categories are cleanly normalized into EvidenceItem records."""
    candidate = CandidateEvidence(
        headline="Senior Systems Engineer",
        summary="Architecting distributed systems handling 50k RPS.",
        experience=[
            ExperienceItem(
                id="exp_0",
                role="Senior Engineer",
                company="Stripe",
                location="San Francisco, CA",
                start_date="2022",
                end_date="Present",
                bullets=["Built payment ingestion pipeline scaling to 10k QPS."],
                technologies=["Python", "Kafka", "PostgreSQL"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Distributed KV Store",
                role="Author",
                description="Raft-based key-value database.",
                highlights=["Achieved 99.99% fault tolerance."],
                tech_stack=["Go", "gRPC"],
            )
        ],
        skills=[
            SkillItem(name="Python", category="Language", proficiency="Expert"),
            SkillItem(name="Kubernetes", category="DevOps", proficiency="Intermediate"),
        ],
        education=[
            EducationItem(
                degree="B.S.",
                institution="UC Berkeley",
                field_of_study="Computer Science",
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
                title="Hackathon Winner",
                description="Won 1st place among 50 teams.",
            )
        ],
        internships=[
            InternshipItem(
                id="intern_0",
                role="Software Intern",
                company="Google",
                bullets=["Optimized search index queries."],
                technologies=["C++"],
            )
        ],
        publications=[
            PublicationItem(
                id="pub_0",
                title="Distributed Consensus via Raft",
                publisher="ACM",
                publication_date="2024",
            )
        ],
        awards=[
            AwardItem(
                id="award_0",
                title="Dean's Honors List",
                issuer="UC Berkeley",
                date="2022",
            )
        ],
        volunteering=[
            VolunteeringItem(
                id="vol_0",
                role="Open Source Maintainer",
                organization="Apache Software Foundation",
                highlights=["Maintained core library with 500k downloads."],
            )
        ],
    )

    items = EvidenceService.normalize_candidate_evidence("test_user_uid_123", candidate)
    # 1 profile + 1 exp + 1 proj + 2 skills + 1 edu + 1 cert + 1 ach + 1 intern + 1 pub + 1 award + 1 vol = 12 items
    assert len(items) == 12

    # All items must belong strictly to user_id
    assert all(item.user_id == "test_user_uid_123" for item in items)

    # Check Experience Evidence
    exp_evidence = next(i for i in items if i.source_type == "experience")
    assert exp_evidence.source_item_id == "exp_0"
    assert exp_evidence.role == "Senior Engineer"
    assert "Python" in exp_evidence.technologies
    assert exp_evidence.confidence == 1.0

    # Check Project Evidence
    proj_evidence = next(i for i in items if i.source_type == "projects")
    assert proj_evidence.source_item_id == "proj_0"
    assert "Go" in proj_evidence.technologies
    assert any("99.99%" in m for m in proj_evidence.metrics)

    # Check Skills Evidence
    skill_evidence = [i for i in items if i.source_type == "skills"]
    assert len(skill_evidence) == 2
    assert skill_evidence[0].confidence == 0.85

    # Check Education Evidence
    edu_evidence = next(i for i in items if i.source_type == "education")
    assert "UC Berkeley" in edu_evidence.title

    # Check Internship Evidence
    intern_evidence = next(i for i in items if i.source_type == "internships")
    assert intern_evidence.source_item_id == "intern_0"
    assert "C++" in intern_evidence.technologies

    # Check Award Evidence
    award_evidence = next(i for i in items if i.source_type == "awards")
    assert award_evidence.source_item_id == "award_0"

    # Check Volunteering Evidence
    vol_evidence = next(i for i in items if i.source_type == "volunteering")
    assert vol_evidence.source_item_id == "vol_0"
    assert any("500k" in m for m in vol_evidence.metrics)


def test_normalize_empty_candidate_evidence():
    """Verifies that an empty workspace candidate object yields an empty evidence list."""
    empty_candidate = CandidateEvidence()
    items = EvidenceService.normalize_candidate_evidence("empty_user", empty_candidate)
    assert items == []
