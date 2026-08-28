import pytest
from app.ai.skills import (
    normalize_skill_name,
    deduplicate_and_normalize_matching_skills,
    deduplicate_and_normalize_missing_skills,
    deduplicate_and_normalize_partial_skills,
)
from app.schemas.common import SkillMatchItem, SkillMissingItem, SkillPartialItem


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
