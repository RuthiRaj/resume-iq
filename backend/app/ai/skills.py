import re
from typing import List, Dict
from app.schemas.common import SkillMatchItem, SkillMissingItem, SkillPartialItem

# Conservative dictionary of canonical technology names
CANONICAL_SKILL_MAP: Dict[str, str] = {
    # Frontend & JavaScript ecosystem
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "react.js library": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "next js": "Next.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "angular": "Angular",
    "angularjs": "Angular",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",

    # Backend & Languages
    "python": "Python",
    "python3": "Python",
    "golang": "Go",
    "go lang": "Go",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "dotnet": ".NET",
    ".net": ".NET",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",

    # Databases & Storage
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "redis": "Redis",
    "sqlite": "SQLite",

    # Cloud & DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "Google Cloud",
    "google cloud platform": "Google Cloud",
    "google cloud": "Google Cloud",
    "azure": "Microsoft Azure",
    "microsoft azure": "Microsoft Azure",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful api": "REST APIs",
    "restful apis": "REST APIs",
}

# Priority rank for missing skills deduplication (higher rank wins)
PRIORITY_RANK = {
    "High": 3,
    "Medium": 2,
    "Low": 1,
}


def normalize_skill_name(raw_name: str) -> str:
    """
    Normalizes a skill name conservatively to its canonical industry representation.
    Preserves casing for unknown skills while trimming whitespace and punctuation.
    """
    if not raw_name:
        return ""
    cleaned = raw_name.strip()
    lookup_key = cleaned.lower()
    
    # Check direct canonical dictionary match
    if lookup_key in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[lookup_key]

    # Clean redundant trailing phrases like "Experience", "Framework", "Library"
    simplified_key = re.sub(r"\s+(framework|library|technology|tool|experience)$", "", lookup_key).strip()
    if simplified_key in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[simplified_key]

    return cleaned


def deduplicate_and_normalize_matching_skills(
    skills: List[SkillMatchItem],
) -> List[SkillMatchItem]:
    """Deduplicates matching skills by canonical name while preserving evidence context."""
    seen: Dict[str, SkillMatchItem] = {}
    for item in skills:
        norm_name = normalize_skill_name(item.name)
        if not norm_name:
            continue
        if norm_name not in seen:
            seen[norm_name] = SkillMatchItem(name=norm_name, context=item.context)
        else:
            # If current item has longer or more descriptive context, prioritize it
            if len(item.context) > len(seen[norm_name].context):
                seen[norm_name] = SkillMatchItem(name=norm_name, context=item.context)
    return list(seen.values())


def deduplicate_and_normalize_missing_skills(
    skills: List[SkillMissingItem],
) -> List[SkillMissingItem]:
    """Deduplicates missing skills by canonical name, preserving the highest priority."""
    seen: Dict[str, SkillMissingItem] = {}
    for item in skills:
        norm_name = normalize_skill_name(item.name)
        if not norm_name:
            continue
        if norm_name not in seen:
            seen[norm_name] = SkillMissingItem(
                name=norm_name, priority=item.priority, reason=item.reason
            )
        else:
            existing = seen[norm_name]
            current_rank = PRIORITY_RANK.get(item.priority, 1)
            existing_rank = PRIORITY_RANK.get(existing.priority, 1)
            if current_rank > existing_rank:
                seen[norm_name] = SkillMissingItem(
                    name=norm_name, priority=item.priority, reason=item.reason
                )
    return list(seen.values())


def deduplicate_and_normalize_partial_skills(
    skills: List[SkillPartialItem],
) -> List[SkillPartialItem]:
    """Deduplicates partial skills by canonical name, preserving descriptive guidance notes."""
    seen: Dict[str, SkillPartialItem] = {}
    for item in skills:
        norm_name = normalize_skill_name(item.name)
        if not norm_name:
            continue
        if norm_name not in seen:
            seen[norm_name] = SkillPartialItem(name=norm_name, note=item.note)
        else:
            if len(item.note) > len(seen[norm_name].note):
                seen[norm_name] = SkillPartialItem(name=norm_name, note=item.note)
    return list(seen.values())
