import re
from typing import List, Dict, Optional
from app.schemas.common import SkillMatchItem, SkillMissingItem, SkillPartialItem
from app.schemas.job_description import SkillRequirement

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
    "go": "Go",
    "go lang": "Go",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "rust": "Rust",
    "ruby": "Ruby",
    "sql": "SQL",
    "dotnet": ".NET",
    ".net": ".NET",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "express": "Express.js",
    "express.js": "Express.js",

    # Databases & Storage
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "redis": "Redis",
    "sqlite": "SQLite",
    "dynamodb": "DynamoDB",
    "elasticsearch": "Elasticsearch",

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
    "github actions": "GitHub Actions",
    "jenkins": "Jenkins",

    # Tools, Protocols & Message Brokers
    "kafka": "Apache Kafka",
    "apache kafka": "Apache Kafka",
    "rabbitmq": "RabbitMQ",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "restful api": "REST APIs",
    "restful apis": "REST APIs",
    "git": "Git",

    # Architecture, Systems & Engineering Domains
    "system design": "System Design",
    "distributed systems": "Distributed Systems",
    "microservices": "Microservices",
    "observability": "Observability",
    "high availability": "High Availability",
    "api design": "API Design",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "computer vision": "Computer Vision",

    # Soft Skills & Collaboration
    "communication": "Communication",
    "leadership": "Leadership",
    "mentorship": "Mentorship",
    "collaboration": "Collaboration",
    "teamwork": "Teamwork",
    "agile": "Agile",
}

# Canonical Taxonomy Map for known skills
CANONICAL_SKILL_CATEGORY: Dict[str, str] = {
    # Languages
    "Python": "Language",
    "Go": "Language",
    "TypeScript": "Language",
    "JavaScript": "Language",
    "Java": "Language",
    "C++": "Language",
    "C#": "Language",
    "Rust": "Language",
    "Ruby": "Language",
    "SQL": "Language",

    # Frameworks
    "React": "Framework",
    "Next.js": "Framework",
    "Vue.js": "Framework",
    "Angular": "Framework",
    "FastAPI": "Framework",
    "Django": "Framework",
    "Flask": "Framework",
    "Spring Boot": "Framework",
    ".NET": "Framework",
    "Express.js": "Framework",
    "Tailwind CSS": "Framework",

    # Databases
    "PostgreSQL": "Database",
    "MongoDB": "Database",
    "MySQL": "Database",
    "Redis": "Database",
    "SQLite": "Database",
    "DynamoDB": "Database",
    "Elasticsearch": "Database",

    # Cloud
    "AWS": "Cloud",
    "Google Cloud": "Cloud",
    "Microsoft Azure": "Cloud",

    # DevOps
    "Docker": "DevOps",
    "Kubernetes": "DevOps",
    "Terraform": "DevOps",
    "CI/CD": "DevOps",
    "GitHub Actions": "DevOps",
    "Jenkins": "DevOps",

    # Tools
    "Apache Kafka": "Tool",
    "RabbitMQ": "Tool",
    "Git": "Tool",
    "GraphQL": "Tool",
    "gRPC": "Tool",

    # Domains & Architecture
    "System Design": "Domain",
    "Distributed Systems": "Domain",
    "Microservices": "Domain",
    "REST APIs": "Domain",
    "Observability": "Domain",
    "High Availability": "Domain",
    "API Design": "Domain",
    "Machine Learning": "Domain",
    "Deep Learning": "Domain",
    "NLP": "Domain",
    "Computer Vision": "Domain",

    # Soft Skills
    "Communication": "SoftSkill",
    "Leadership": "SoftSkill",
    "Mentorship": "SoftSkill",
    "Collaboration": "SoftSkill",
    "Teamwork": "SoftSkill",
    "Agile": "SoftSkill",
}

# Priority rank for missing skills deduplication (higher rank wins)
PRIORITY_RANK = {
    "High": 3,
    "Medium": 2,
    "Low": 1,
}

VALID_CATEGORIES = {
    "Language",
    "Framework",
    "Database",
    "Cloud",
    "DevOps",
    "Tool",
    "SoftSkill",
    "Domain",
    "Other",
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
    simplified_key = re.sub(
        r"\s+(framework|library|technology|tool|experience)$", "", lookup_key
    ).strip()
    if simplified_key in CANONICAL_SKILL_MAP:
        return CANONICAL_SKILL_MAP[simplified_key]

    return cleaned


def normalize_skill_category(skill_name: str, fallback_category: str = "Other") -> str:
    """
    Deterministically normalizes the category of a skill using canonical industry mappings.
    If the skill is not in the canonical taxonomy, validates and respects the fallback category
    or safely falls back to 'Other'.
    """
    canonical_name = normalize_skill_name(skill_name)
    if canonical_name in CANONICAL_SKILL_CATEGORY:
        return CANONICAL_SKILL_CATEGORY[canonical_name]

    if fallback_category in VALID_CATEGORIES:
        # Prevent technical keywords from being mistakenly labeled as SoftSkill
        if fallback_category == "SoftSkill" and canonical_name.lower() in CANONICAL_SKILL_MAP:
            return "Domain"
        return fallback_category

    return "Other"


def normalize_and_deduplicate_skill_requirements(
    skills: List[SkillRequirement],
) -> List[SkillRequirement]:
    """Deduplicates and canonicalizes structured JD skill requirements."""
    seen: Dict[str, SkillRequirement] = {}
    for item in skills:
        norm_name = normalize_skill_name(item.name)
        if not norm_name:
            continue
        norm_category = normalize_skill_category(norm_name, item.category)
        clean_evidence = (item.source_evidence or "").strip()

        if norm_name not in seen:
            seen[norm_name] = SkillRequirement(
                name=norm_name,
                category=norm_category,
                importance=item.importance,
                source_evidence=clean_evidence,
            )
        else:
            # If current item has longer or more descriptive source evidence, prioritize it
            if clean_evidence and len(clean_evidence) > len(seen[norm_name].source_evidence or ""):
                seen[norm_name] = SkillRequirement(
                    name=norm_name,
                    category=norm_category,
                    importance=item.importance,
                    source_evidence=clean_evidence,
                )
    return list(seen.values())


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
