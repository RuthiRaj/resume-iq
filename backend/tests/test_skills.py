import pytest
from app.ai.skills import (
    normalize_skill_name,
    normalize_skill_category,
    normalize_and_deduplicate_skill_requirements,
    deduplicate_and_normalize_matching_skills,
    deduplicate_and_normalize_missing_skills,
    deduplicate_and_normalize_partial_skills,
)
from app.schemas.common import SkillMatchItem, SkillMissingItem, SkillPartialItem
from app.schemas.job_description import SkillRequirement


def test_normalize_skill_name_common_variants():
    assert normalize_skill_name("react.js") == "React"
    assert normalize_skill_name("ReactJS") == "React"
    assert normalize_skill_name("react") == "React"
    assert normalize_skill_name("Postgres") == "PostgreSQL"
    assert normalize_skill_name("postgresql") == "PostgreSQL"
    assert normalize_skill_name("NodeJS") == "Node.js"
    assert normalize_skill_name("NextJS") == "Next.js"
    assert normalize_skill_name("k8s") == "Kubernetes"
    assert normalize_skill_name("golang") == "Go"
    assert normalize_skill_name("ts") == "TypeScript"
    assert normalize_skill_name("js") == "JavaScript"


def test_normalize_skill_name_distinct_technologies_preserved():
    # Ensure distinct technologies are NEVER conflated
    assert normalize_skill_name("Java") == "Java"
    assert normalize_skill_name("JavaScript") == "JavaScript"
    assert normalize_skill_name("React Native") == "React Native"
    assert normalize_skill_name("React") == "React"
    assert normalize_skill_name("C") == "C"
    assert normalize_skill_name("C++") == "C++"
    assert normalize_skill_name("AWS") == "AWS"
    assert normalize_skill_name("Azure") == "Microsoft Azure"


def test_normalize_skill_category_canonical_taxonomy():
    # Verify architectural concepts are classified as Domain (NEVER SoftSkill)
    assert normalize_skill_category("System Design", fallback_category="SoftSkill") == "Domain"
    assert normalize_skill_category("Distributed Systems", fallback_category="SoftSkill") == "Domain"
    assert normalize_skill_category("Microservices", fallback_category="SoftSkill") == "Domain"
    assert normalize_skill_category("Observability", fallback_category="SoftSkill") == "Domain"

    # Verify standard tech categories
    assert normalize_skill_category("Python") == "Language"
    assert normalize_skill_category("FastAPI") == "Framework"
    assert normalize_skill_category("PostgreSQL") == "Database"
    assert normalize_skill_category("Redis") == "Database"
    assert normalize_skill_category("Docker") == "DevOps"
    assert normalize_skill_category("Kubernetes") == "DevOps"
    assert normalize_skill_category("AWS") == "Cloud"
    assert normalize_skill_category("Apache Kafka") == "Tool"
    assert normalize_skill_category("Communication") == "SoftSkill"
    assert normalize_skill_category("Mentorship") == "SoftSkill"


def test_normalize_and_deduplicate_skill_requirements():
    raw = [
        SkillRequirement(
            name="system design",
            category="SoftSkill",
            importance="MustHave",
            source_evidence="Experience with system design",
        ),
        SkillRequirement(
            name="System Design",
            category="Domain",
            importance="MustHave",
            source_evidence="Strong fundamentals in system design, distributed systems, and observability.",
        ),
        SkillRequirement(
            name="redis",
            category="Tool",
            importance="Preferred",
            source_evidence="Experience with Redis caching",
        ),
    ]
    deduped = normalize_and_deduplicate_skill_requirements(raw)
    assert len(deduped) == 2

    sys_design = next(s for s in deduped if s.name == "System Design")
    assert sys_design.category == "Domain"
    # Preserves longer source evidence snippet
    assert "observability" in sys_design.source_evidence

    redis_item = next(s for s in deduped if s.name == "Redis")
    assert redis_item.category == "Database"
    assert redis_item.importance == "Preferred"


def test_deduplicate_and_normalize_matching_skills():
    raw = [
        SkillMatchItem(name="ReactJS", context="Built UI with React"),
        SkillMatchItem(name="React", context="Architected enterprise design system in React 18 with high performance"),
        SkillMatchItem(name="Postgres", context="Used PostgreSQL database"),
    ]
    deduped = deduplicate_and_normalize_matching_skills(raw)
    assert len(deduped) == 2
    names = {s.name for s in deduped}
    assert names == {"React", "PostgreSQL"}

    # Verified longer, more descriptive context was preserved for React
    react_item = next(s for s in deduped if s.name == "React")
    assert "enterprise design system" in react_item.context


def test_deduplicate_and_normalize_missing_skills_priority_retention():
    raw = [
        SkillMissingItem(name="k8s", priority="Low", reason="Mentioned in job description"),
        SkillMissingItem(name="Kubernetes", priority="High", reason="Crucial cloud orchestrator requirement"),
        SkillMissingItem(name="Docker", priority="Medium", reason="Containerization required"),
    ]
    deduped = deduplicate_and_normalize_missing_skills(raw)
    assert len(deduped) == 2
    names = {s.name for s in deduped}
    assert names == {"Kubernetes", "Docker"}

    k8s_item = next(s for s in deduped if s.name == "Kubernetes")
    assert k8s_item.priority == "High"
    assert "Crucial" in k8s_item.reason


def test_deduplicate_and_normalize_partial_skills():
    raw = [
        SkillPartialItem(name="Next.js", note="Has React experience"),
        SkillPartialItem(name="nextjs", note="Has deep React 18 experience with server-side rendering patterns"),
    ]
    deduped = deduplicate_and_normalize_partial_skills(raw)
    assert len(deduped) == 1
    assert deduped[0].name == "Next.js"
    assert "server-side rendering" in deduped[0].note
