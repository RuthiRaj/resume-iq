"""
Deterministic Gap Remediation Blueprints (Phase 5.0)

Generates honest, actionable learning paths and portfolio project blueprints
for structural hard gaps that cannot be bridged by existing verified evidence.
"""

from typing import List, Dict, Optional
from app.schemas.requirement_match import RequirementMatch, GapType
from app.schemas.career_intelligence import (
    GapRemediationStrategy,
    ActionableLearningPath,
    ProjectBlueprint,
    GapSeverity,
)
from app.ai.skills import normalize_skill_name, normalize_skill_category


# Curated Project Blueprints by Domain/Skill
CURATED_PROJECT_BLUEPRINTS: Dict[str, ProjectBlueprint] = {
    "kubernetes": ProjectBlueprint(
        projectTitle="Production Microservices Cluster with Helm & Ingress",
        problemStatement="Deploy and manage a resilient multi-tier microservices application with automated autoscaling and traffic routing.",
        architectureComponents=["Minikube/K3s local cluster", "Helm Charts for service templates", "NGINX Ingress Controller", "HPA (Horizontal Pod Autoscaler)"],
        demonstratedSkills=["Kubernetes", "Container Orchestration", "Helm", "Cluster Ingress", "Resource Limits"],
        verificationChecklist=[
            "Author declarative Deployment and Service manifests",
            "Configure liveness and readiness probes",
            "Implement Horizontal Pod Autoscaling under simulated load",
            "Package configuration into reusable Helm charts",
        ],
    ),
    "aws": ProjectBlueprint(
        projectTitle="Automated Cloud Infrastructure with VPC Peering & S3 Security",
        problemStatement="Provision a secure, multi-tier cloud environment following the AWS Well-Architected Framework.",
        architectureComponents=["Multi-AZ VPC with Public/Private Subnets", "NAT Gateway", "S3 Bucket with KMS Encryption", "IAM Role Least Privilege"],
        demonstratedSkills=["AWS", "VPC Networking", "IAM Security", "S3 Storage", "EC2 Compute"],
        verificationChecklist=[
            "Configure custom CIDR blocks and routing tables",
            "Enforce strict S3 bucket policies with AES-256 KMS encryption",
            "Establish IAM role-based execution without hardcoded credentials",
        ],
    ),
    "graphql": ProjectBlueprint(
        projectTitle="Federated GraphQL Gateway with DataLoader Batching",
        problemStatement="Build an efficient GraphQL API layer resolving data from multiple backend microservices with sub-50ms latency.",
        architectureComponents=["GraphQL Schema SDL", "Apollo Server / Strawberry Gateway", "DataLoader batch caching", "JWT Context Authentication"],
        demonstratedSkills=["GraphQL", "API Design", "DataLoader", "Schema Federation", "N+1 Query Prevention"],
        verificationChecklist=[
            "Design strictly typed GraphQL queries and mutations",
            "Implement DataLoader to solve N+1 database queries",
            "Secure schema fields using field-level authorization",
        ],
    ),
    "apache kafka": ProjectBlueprint(
        projectTitle="High-Throughput Real-Time Event Streaming Pipeline",
        problemStatement="Process and route 10,000+ telemetry events per second across partitioned message topics.",
        architectureComponents=["Kafka Broker Cluster (KRaft)", "Producer Service with Retries & Idempotence", "Consumer Groups with Offset Management", "Dead-Letter Topic"],
        demonstratedSkills=["Apache Kafka", "Event-Driven Architecture", "Partition Routing", "Consumer Offsets"],
        verificationChecklist=[
            "Configure multi-partition topics with custom replication factors",
            "Implement consumer group error handling and dead-letter queues",
            "Verify exactly-once processing semantics using transactional producers",
        ],
    ),
    "system design": ProjectBlueprint(
        projectTitle="Distributed URL Shortener with Global Caching & Analytics",
        problemStatement="Design and benchmark a distributed system handling 1B+ monthly requests with high availability and low latency.",
        architectureComponents=["Base62 Encoding Service", "Distributed Snowflake ID Generator", "Redis LRU Cache", "PostgreSQL Sharded Storage"],
        demonstratedSkills=["System Design", "Distributed Systems", "Caching Strategies", "Database Sharding"],
        verificationChecklist=[
            "Calculate capacity estimations (QPS, storage, bandwidth)",
            "Design schema and partition keys for horizontal scale",
            "Implement cache-aside pattern with Redis",
        ],
    ),
    "docker": ProjectBlueprint(
        projectTitle="Optimized Multi-Stage Container Packaging Pipeline",
        problemStatement="Package a full-stack web service into production-ready, minimal-footprint container images.",
        architectureComponents=["Multi-Stage Dockerfile (Alpine base)", "Non-Root Security Context", "Docker Compose local stack", "Container Healthcheck"],
        demonstratedSkills=["Docker", "Container Security", "Image Optimization", "Docker Compose"],
        verificationChecklist=[
            "Reduce container image size by >=70% using multi-stage builds",
            "Execute application processes under an unprivileged non-root user",
            "Configure local service dependencies in docker-compose.yml",
        ],
    ),
}

# Curated Learning Paths by Skill
CURATED_LEARNING_PATHS: Dict[str, ActionableLearningPath] = {
    "kubernetes": ActionableLearningPath(
        title="Kubernetes Core Architecture & Pod Management",
        estimatedWeeks=3,
        keyMilestones=[
            "Week 1: Pods, ReplicaSets, Deployments, and Declarative YAML",
            "Week 2: Cluster Networking, Services (ClusterIP/NodePort), and Ingress",
            "Week 3: ConfigMaps, Secrets, Volumes, and Helm Packaging",
        ],
        authoritativeDocsUrl="https://kubernetes.io/docs/tutorials/",
    ),
    "aws": ActionableLearningPath(
        title="AWS Cloud Practitioner to Solutions Architect Fundamentals",
        estimatedWeeks=4,
        keyMilestones=[
            "Week 1: IAM Policies, Roles, and Multi-Factor Security",
            "Week 2: VPC Networking, Subnets, Route Tables, and Security Groups",
            "Week 3: EC2, ECS, Lambda Serverless, and Auto-Scaling Groups",
            "Week 4: S3 Lifecycle Policies, RDS Multi-AZ, and DynamoDB",
        ],
        authoritativeDocsUrl="https://aws.amazon.com/getting-started/",
    ),
    "graphql": ActionableLearningPath(
        title="Production GraphQL API Design & Federation",
        estimatedWeeks=2,
        keyMilestones=[
            "Week 1: Schema Definition Language, Resolvers, and Query ASTs",
            "Week 2: Mutations, Real-Time WebSockets, and DataLoader Batch Optimization",
        ],
        authoritativeDocsUrl="https://graphql.org/learn/",
    ),
    "apache kafka": ActionableLearningPath(
        title="Distributed Event Streaming with Apache Kafka",
        estimatedWeeks=3,
        keyMilestones=[
            "Week 1: Topics, Partitions, Brokers, and Message Serialization",
            "Week 2: Producers, Consumer Groups, and Offset Commit Semantics",
            "Week 3: Stream Processing & Fault Tolerance with Dead-Letter Queues",
        ],
        authoritativeDocsUrl="https://kafka.apache.org/documentation/",
    ),
}


class GapRemediationEngine:
    """
    Constructs deterministic, honest gap remediation strategies.
    Recommendations are never confused with candidate experience.
    """

    @classmethod
    def generate_remediation_strategy(cls, requirement: RequirementMatch) -> GapRemediationStrategy:
        """Builds a structured remediation blueprint for an unverified requirement."""
        req_name = requirement.requirement_name
        norm_name = normalize_skill_name(req_name).lower()
        category = normalize_skill_category(req_name)

        # Classify Gap Severity
        severity: GapSeverity = "HardExperientialGap"
        if category in ("Cloud", "DevOps", "Database"):
            severity = "HardExperientialGap"
        elif category == "Certification":
            severity = "MissingDomainCertification"
        else:
            severity = "LearnableAdjacentSkill"

        guidance = (
            f"'{req_name}' is a required capability with no verified evidence in your candidate profile. "
            f"Rather than hallucinating experience, we recommend demonstrating competence through the project blueprint below."
        )

        # Retrieve curated blueprints or generate deterministic fallback
        learning_paths: List[ActionableLearningPath] = []
        if norm_name in CURATED_LEARNING_PATHS:
            learning_paths.append(CURATED_LEARNING_PATHS[norm_name])
        else:
            learning_paths.append(
                ActionableLearningPath(
                    title=f"{req_name} Core Fundamentals & Architecture",
                    estimatedWeeks=2,
                    keyMilestones=[
                        f"Milestone 1: Study core concepts and official documentation for {req_name}",
                        f"Milestone 2: Build a functional proof-of-concept integrating {req_name}",
                        f"Milestone 3: Benchmark and document system behavior in a public repository",
                    ],
                )
            )

        project_blueprints: List[ProjectBlueprint] = []
        if norm_name in CURATED_PROJECT_BLUEPRINTS:
            project_blueprints.append(CURATED_PROJECT_BLUEPRINTS[norm_name])
        else:
            project_blueprints.append(
                ProjectBlueprint(
                    projectTitle=f"Production-Ready {req_name} Integration & Benchmark",
                    problemStatement=f"Implement a verified software component demonstrating end-to-end proficiency with {req_name}.",
                    architectureComponents=[f"{req_name} Core Service", "Automated Test Suite", "CI/CD Pipeline", "Documentation"],
                    demonstratedSkills=[req_name],
                    verificationChecklist=[
                        f"Author modular code adhering to {req_name} best practices",
                        "Include unit and integration test coverage",
                        "Publish clear architectural README explaining trade-offs",
                    ],
                )
            )

        return GapRemediationStrategy(
            requirementName=req_name,
            gapType=requirement.evidence_dimensions.meets_experience_years and "MissingEvidence" or "InsufficientContext",
            severity=severity,
            remediationGuidance=guidance,
            learningPaths=learning_paths,
            projectBlueprints=project_blueprints,
        )
