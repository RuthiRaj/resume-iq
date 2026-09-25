"""
Deterministic Transferability Taxonomy & Adjacency Rules (Phase 5.0)

Provides a 100% deterministic, inspectable graph of technical skill adjacencies.
Strict Invariants:
1. Directional: Rule A -> B does not imply B -> A unless explicitly defined.
2. Non-Equivalence: Adjacency is a transferable possibility, NEVER an automatic match.
3. 0 Runtime LLM calls: 100% in-memory O(1) indexed lookup.
"""

from typing import Dict, List, Optional, Tuple
from app.ai.skills import normalize_skill_name
from app.schemas.career_intelligence import SkillTransferabilityRule, SkillRelationshipType


# Comprehensive Deterministic Adjacency Registry (40+ curated industry rules)
DETERMINISTIC_TRANSFERABILITY_RULES: List[SkillTransferabilityRule] = [
    # =========================================================================
    # 1. FRAMEWORK FAMILY
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="React",
        targetSkill="Next.js",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.85,
        transferRationale="React is the core rendering and component foundation of Next.js. Candidate understands component lifecycle, hooks, and JSX.",
        sharedCompetencies=["JSX", "Component Architecture", "React Hooks", "State Management", "Virtual DOM"],
        criticalDifferences=["Server-Side Rendering (SSR)", "Static Site Generation (SSG)", "App Router Conventions", "Server Components"],
        verificationQuestions=["Have you implemented Server-Side Rendering (SSR) or App Router conventions using Next.js?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Next.js",
        targetSkill="React",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.95,
        transferRationale="Next.js is a meta-framework built entirely on React; Next.js developers are fully proficient in React.",
        sharedCompetencies=["React Hooks", "Component Lifecycle", "State Management", "JSX"],
        criticalDifferences=["Client-only routing (e.g. React Router) vs file-system routing"],
        verificationQuestions=["Have you built standalone client-rendered single-page applications in pure React?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Vue.js",
        targetSkill="React",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.75,
        transferRationale="Both utilize reactive state, component-based architectures, and virtual DOM paradigms.",
        sharedCompetencies=["Component State", "Props Passing", "Virtual DOM", "Single Page Applications"],
        criticalDifferences=["JSX syntax vs template directives", "Hooks/Effects vs Composition API watch/computed"],
        verificationQuestions=["Have you translated reactive component workflows into React JSX and hook patterns?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="React",
        targetSkill="Vue.js",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.75,
        transferRationale="Both utilize reactive state, component-based architectures, and virtual DOM paradigms.",
        sharedCompetencies=["Component State", "Props Passing", "Virtual DOM", "Single Page Applications"],
        criticalDifferences=["Template directives vs JSX syntax", "Composition API watch/computed vs Hooks/Effects"],
        verificationQuestions=["Have you implemented Vue 3 single-file components using the Composition API?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Flask",
        targetSkill="FastAPI",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.85,
        transferRationale="Both are lightweight Python micro-frameworks sharing WSGI/ASGI patterns and routing decorators.",
        sharedCompetencies=["Python Route Decorators", "REST Microservices", "Request Context Handling"],
        criticalDifferences=["Asynchronous I/O (async/await)", "Pydantic request validation", "OpenAPI automatic schemas"],
        verificationQuestions=["Have you built async endpoints and Pydantic validation models using FastAPI?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="FastAPI",
        targetSkill="Flask",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.90,
        transferRationale="FastAPI developers easily navigate synchronous Flask request/response lifecycles.",
        sharedCompetencies=["Python HTTP Routing", "Middleware", "REST API Development"],
        criticalDifferences=["Synchronous WSGI execution vs asynchronous ASGI event loops"],
        verificationQuestions=["Have you handled synchronous WSGI threading or Flask Blueprints in production?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Django",
        targetSkill="FastAPI",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Django developers understand Python backend architecture, ORMs, and RESTful service design.",
        sharedCompetencies=["Python Backend Architecture", "Relational ORM integration", "Authentication"],
        criticalDifferences=["Lightweight micro-framework structure vs Django batteries-included monolith", "Async ASGI runtime"],
        verificationQuestions=["Have you built standalone asynchronous APIs using FastAPI without Django ORM?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Express.js",
        targetSkill="FastAPI",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.70,
        transferRationale="Both emphasize lightweight route handler functions and REST middleware pipelines.",
        sharedCompetencies=["HTTP Route Handlers", "Middleware Pipelines", "JSON Serialization"],
        criticalDifferences=["Python type hints & Pydantic vs Node.js JavaScript/TypeScript event loops"],
        verificationQuestions=["Have you developed backend services in Python utilizing FastAPI async handlers?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Spring Boot",
        targetSkill=".NET",
        relationshipType="FRAMEWORK_FAMILY",
        transferabilityScore=0.75,
        transferRationale="Both represent enterprise OOP backend frameworks with dependency injection, annotations, and robust ORMs.",
        sharedCompetencies=["Dependency Injection (IoC)", "Enterprise MVC Architecture", "ORM Persistence", "REST APIs"],
        criticalDifferences=["C# language runtime (.NET Core CLR) vs Java JVM bytecode and ecosystem tooling"],
        verificationQuestions=["Have you implemented C# Web APIs using ASP.NET Core and Entity Framework?"]
    ),

    # =========================================================================
    # 2. DATABASE FAMILY
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="PostgreSQL",
        targetSkill="MySQL",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.90,
        transferRationale="Both are industry-standard relational SQL engines sharing ACID guarantees, schema DDL, and index tuning.",
        sharedCompetencies=["ANSI SQL", "ACID Transactions", "B-Tree Indexing", "Foreign Keys", "Join Optimization"],
        criticalDifferences=["Storage engines (InnoDB) vs MVCC internals", "Dialect differences (JSONB vs JSON, LIMIT offsets)"],
        verificationQuestions=["Have you tuned query performance and managed migrations on MySQL/InnoDB databases?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="MySQL",
        targetSkill="PostgreSQL",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.85,
        transferRationale="Relational SQL knowledge translates directly to PostgreSQL relational design.",
        sharedCompetencies=["ANSI SQL", "Table Normalization", "Query Optimization", "Indexing Strategies"],
        criticalDifferences=["Advanced data types (JSONB, Arrays)", "CTEs and window functions", "Postgres MVCC vacuuming"],
        verificationQuestions=["Have you utilized PostgreSQL advanced indexing (GIN/GIST) or JSONB query operators?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="MongoDB",
        targetSkill="DynamoDB",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.75,
        transferRationale="Both are NoSQL document/key-value stores requiring non-relational access patterns and JSON document models.",
        sharedCompetencies=["NoSQL Modeling", "Document Partitioning", "JSON Schema Structures"],
        criticalDifferences=["DynamoDB single-table design & partition keys vs Mongo document aggregation pipelines"],
        verificationQuestions=["Have you designed partition/sort keys and GSI access patterns on AWS DynamoDB?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="DynamoDB",
        targetSkill="MongoDB",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.80,
        transferRationale="DynamoDB modeling expertise translates well to MongoDB collections and flexible document hierarchies.",
        sharedCompetencies=["Document-oriented storage", "Horizontal Sharding", "Denormalization Strategies"],
        criticalDifferences=["Mongoose/MongoDB query aggregation framework vs DynamoDB key-based queries"],
        verificationQuestions=["Have you authored complex aggregation pipelines and index strategies in MongoDB?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="PostgreSQL",
        targetSkill="CockroachDB",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.90,
        transferRationale="CockroachDB uses the PostgreSQL wire protocol and SQL dialect with distributed Raft consensus.",
        sharedCompetencies=["PostgreSQL SQL Dialect", "Relational Schema Design", "ACID Semantics"],
        criticalDifferences=["Distributed transaction latency", "Multi-region table locality", "Range partitioning"],
        verificationQuestions=["Have you deployed or managed distributed schema locality on CockroachDB clusters?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Redis",
        targetSkill="Memcached",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.90,
        transferRationale="Both are ultra-low-latency in-memory caching layers with key-value eviction strategies.",
        sharedCompetencies=["In-Memory Caching", "TTL Expiration Policies", "Cache Invalidation Patterns"],
        criticalDifferences=["Multi-threaded memory allocation in Memcached vs rich data structures/pub-sub in Redis"],
        verificationQuestions=["Have you configured Memcached cluster pools and slab allocation policies?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Elasticsearch",
        targetSkill="OpenSearch",
        relationshipType="DATABASE_FAMILY",
        transferabilityScore=0.95,
        transferRationale="OpenSearch is an open-source fork of Elasticsearch sharing identical Lucene indices and DSL queries.",
        sharedCompetencies=["Lucene Inverted Indices", "Elasticsearch Query DSL", "Shard Routing", "Aggregations"],
        criticalDifferences=["OpenSearch Dashboards & security plugins vs Elastic License specific features"],
        verificationQuestions=["Have you managed OpenSearch indexing pipelines and cluster shards in production?"]
    ),

    # =========================================================================
    # 3. LANGUAGE FAMILY
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="Java",
        targetSkill="Kotlin",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.85,
        transferRationale="Kotlin runs on the JVM with 100% bidirectional Java interoperability and shared bytecode semantics.",
        sharedCompetencies=["JVM Runtime", "Object-Oriented Design", "Concurrency & Threading", "Ecosystem Libraries"],
        criticalDifferences=["Kotlin Coroutines vs Java Threads/Virtual Threads", "Null Safety system", "Data classes & extension functions"],
        verificationQuestions=["Have you written production code utilizing Kotlin coroutines and null-safety idioms?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Kotlin",
        targetSkill="Java",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.95,
        transferRationale="Kotlin developers compile to JVM bytecode and regularly interface directly with Java frameworks.",
        sharedCompetencies=["JVM Architecture", "Java Class Libraries", "Maven/Gradle Build Systems"],
        criticalDifferences=["Java verbosity and explicit null-checking patterns"],
        verificationQuestions=["Have you built enterprise services directly in standard Java (Java 17/21)?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="JavaScript",
        targetSkill="TypeScript",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.85,
        transferRationale="TypeScript is a typed superset of JavaScript; runtime execution and standard library are identical.",
        sharedCompetencies=["JavaScript Runtime (Node/Browser)", "Event Loop & Promises", "DOM API", "NPM Ecosystem"],
        criticalDifferences=["Static typing", "Interfaces & Generics", "Type Narrowing & Discriminated Unions"],
        verificationQuestions=["Have you authored strict TypeScript interfaces, generics, and compiler configurations?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="TypeScript",
        targetSkill="JavaScript",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=1.00,
        transferRationale="TypeScript compiles down to JavaScript; every TypeScript developer possesses full JavaScript mastery.",
        sharedCompetencies=["Full JavaScript Language Semantics", "Asynchronous Programming", "ES6+ Modules"],
        criticalDifferences=["None (TypeScript is a pure superset)"],
        verificationQuestions=["Have you developed vanilla JavaScript applications and Node.js runtime scripts?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="C#",
        targetSkill="Java",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Both are strongly typed, class-based, garbage-collected object-oriented languages with similar syntax.",
        sharedCompetencies=["Static OOP Design", "Garbage Collection Semantics", "Generics", "Enterprise Multi-threading"],
        criticalDifferences=["JVM ecosystem (Maven/Gradle/Spring) vs .NET CLR (NuGet/ASP.NET Core)"],
        verificationQuestions=["Have you built Java services using JVM dependency management and frameworks?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Python",
        targetSkill="Go",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.65,
        transferRationale="Python backend developers grasp REST systems and microservice architectures easily in Go.",
        sharedCompetencies=["Backend Architecture", "REST API Development", "JSON Serialization", "CLI Tooling"],
        criticalDifferences=["Static compilation & strict typing", "Goroutines & Channels vs asyncio", "Explicit error return values"],
        verificationQuestions=["Have you written concurrent services in Go using goroutines, channels, and struct interfaces?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="C++",
        targetSkill="Rust",
        relationshipType="LANGUAGE_FAMILY",
        transferabilityScore=0.70,
        transferRationale="Both operate on systems-level memory models without garbage collection, prioritizing zero-cost abstractions.",
        sharedCompetencies=["Manual Memory Models", "Pointers & References", "RAII (Resource Acquisition Is Initialization)", "Zero-Cost Abstractions"],
        criticalDifferences=["Rust Borrow Checker & Lifetime annotations", "Pattern matching & Option/Result error handling"],
        verificationQuestions=["Have you written systems software in Rust obeying borrow-checker lifetime semantics?"]
    ),

    # =========================================================================
    # 4. CLOUD PLATFORM FAMILY
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="AWS",
        targetSkill="Google Cloud",
        relationshipType="CLOUD_PLATFORM_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Cloud architecture patterns (VPC, IAM, Object Storage, Managed Compute, Managed SQL) map directly between AWS and GCP.",
        sharedCompetencies=["Cloud Security & IAM", "VPC Networking", "Object Storage (S3 ↔ GCS)", "Container Compute (ECS ↔ Cloud Run)"],
        criticalDifferences=["GCP Project/Organization hierarchy vs AWS Multi-Account", "GCP BigQuery & Cloud Spanner paradigms"],
        verificationQuestions=["Have you provisioned and managed resources on Google Cloud Platform using IAM and GCP SDKs?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Google Cloud",
        targetSkill="AWS",
        relationshipType="CLOUD_PLATFORM_FAMILY",
        transferabilityScore=0.80,
        transferRationale="GCP architecture experience transfers directly to AWS core primitives (EC2, S3, RDS, Lambda).",
        sharedCompetencies=["Cloud Networking", "Managed Databases", "Serverless Functions", "Cloud Storage"],
        criticalDifferences=["AWS IAM Role policies & JSON trust relationships", "AWS CloudFormation & CloudWatch configuration"],
        verificationQuestions=["Have you architected and configured AWS infrastructure using IAM roles and AWS CLI/CDK?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="AWS",
        targetSkill="Microsoft Azure",
        relationshipType="CLOUD_PLATFORM_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Core cloud infrastructure concepts (Blob Storage, VNets, Azure VMs, App Services) map to AWS primitives.",
        sharedCompetencies=["Cloud Architecture", "Virtual Networks", "Blob/Object Storage", "Managed Databases"],
        criticalDifferences=["Azure Resource Groups and Entra ID (Azure AD) RBAC vs AWS IAM"],
        verificationQuestions=["Have you deployed enterprise applications to Azure using Azure Resource Manager or Entra ID?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Microsoft Azure",
        targetSkill="AWS",
        relationshipType="CLOUD_PLATFORM_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Azure enterprise infrastructure maps closely to AWS compute, networking, and security primitives.",
        sharedCompetencies=["Enterprise Cloud Hosting", "Managed SQL", "Virtual Networks", "Object Storage"],
        criticalDifferences=["AWS IAM JSON syntax, VPC Peering, and AWS Security Groups vs Azure Network Security Groups"],
        verificationQuestions=["Have you provisioned AWS VPCs, Security Groups, and S3 bucket policies in production?"]
    ),

    # =========================================================================
    # 5. DEVOPS & ORCHESTRATION
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="Docker",
        targetSkill="Kubernetes",
        relationshipType="DEVOPS_ORCHESTRATION",
        transferabilityScore=0.65,
        transferRationale="Docker provides the container image and runtime foundation required for Kubernetes pod orchestration. (Adjacent, NOT equivalent).",
        sharedCompetencies=["OCI Container Images", "Dockerfile Layering", "Container Networking Basics", "Environment Variable Injection"],
        criticalDifferences=["Kubernetes Control Plane (etcd, apiserver)", "Pods, Deployments, Services, and Ingress manifests", "Helm charts & HPA autoscaling"],
        verificationQuestions=["Have you authored Kubernetes YAML manifests (Deployments/Services/Ingress) or managed Helm releases?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Kubernetes",
        targetSkill="Docker",
        relationshipType="DEVOPS_ORCHESTRATION",
        transferabilityScore=0.95,
        transferRationale="Kubernetes engineers are fundamentally proficient in container building, tagging, and Docker runtime operations.",
        sharedCompetencies=["Containerization", "Multi-stage Builds", "Container Storage & Networking"],
        criticalDifferences=["Docker Compose local development orchestration"],
        verificationQuestions=["Have you created optimized multi-stage Dockerfiles and Docker Compose local stacks?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Terraform",
        targetSkill="AWS",
        relationshipType="DEVOPS_ORCHESTRATION",
        transferabilityScore=0.80,
        transferRationale="Terraform infrastructure-as-code developers frequently provision and manage core AWS provider resources.",
        sharedCompetencies=["Infrastructure as Code (IaC)", "AWS Provider Resources", "VPC & Subnet Topologies"],
        criticalDifferences=["Direct AWS Console management & native AWS CDK / CloudFormation paradigms"],
        verificationQuestions=["Have you configured and maintained production AWS infrastructure using IaC pipelines?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Jenkins",
        targetSkill="GitHub Actions",
        relationshipType="DEVOPS_ORCHESTRATION",
        transferabilityScore=0.85,
        transferRationale="Both automate build, test, and deployment pipelines using workflow triggers and runner agents.",
        sharedCompetencies=["CI/CD Pipeline Stages", "Artifact Caching", "Secret Management", "Automated Testing Execution"],
        criticalDifferences=["Declarative YAML workflow syntax and reusable composite actions vs Jenkinsfile Groovy scripts"],
        verificationQuestions=["Have you authored GitHub Actions YAML workflows with matrix builds and OIDC authentication?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="CI/CD",
        targetSkill="GitHub Actions",
        relationshipType="DEVOPS_ORCHESTRATION",
        transferabilityScore=0.85,
        transferRationale="Conceptual CI/CD pipeline automation experience translates directly to GitHub Actions workflows.",
        sharedCompetencies=["Automated Linting/Testing", "Continuous Deployment", "Release Tagging", "Environment Secrets"],
        criticalDifferences=["GitHub Actions YAML workflow syntax and marketplace action integration"],
        verificationQuestions=["Have you implemented CI/CD pipelines specifically using GitHub Actions workflows?"]
    ),

    # =========================================================================
    # 6. ML FRAMEWORK FAMILY
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="PyTorch",
        targetSkill="TensorFlow",
        relationshipType="ML_FRAMEWORK_FAMILY",
        transferabilityScore=0.80,
        transferRationale="Both are deep learning frameworks centered on automatic differentiation, tensor operations, and GPU acceleration.",
        sharedCompetencies=["Neural Network Layer Design", "Backpropagation & Optimizers", "Batch Gradient Descent", "Tensor Operations"],
        criticalDifferences=["Keras/TensorFlow graph execution & SavedModel formats vs PyTorch eager execution & state_dict"],
        verificationQuestions=["Have you trained and exported models using TensorFlow 2.x and Keras APIs?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="TensorFlow",
        targetSkill="PyTorch",
        relationshipType="ML_FRAMEWORK_FAMILY",
        transferabilityScore=0.85,
        transferRationale="TensorFlow deep learning expertise maps cleanly to PyTorch Module architectures and training loops.",
        sharedCompetencies=["Tensor Computation", "GPU Accelerators", "Loss Functions", "DataLoader Pipelines"],
        criticalDifferences=["PyTorch custom training loops (loss.backward, optimizer.step) vs model.fit()"],
        verificationQuestions=["Have you implemented custom PyTorch nn.Module architectures and training loops?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Machine Learning",
        targetSkill="Deep Learning",
        relationshipType="ML_FRAMEWORK_FAMILY",
        transferabilityScore=0.70,
        transferRationale="Foundational machine learning (loss optimization, cross-validation, feature extraction) underpins deep neural networks.",
        sharedCompetencies=["Model Evaluation Metrics (Precision/Recall/F1)", "Overfitting Prevention", "Train/Val/Test Splits"],
        criticalDifferences=["Backpropagation in deep architectures, CNNs/Transformers, GPU memory optimization"],
        verificationQuestions=["Have you trained multi-layer neural networks or transformers on GPU hardware?"]
    ),

    # =========================================================================
    # 7. CONCEPTUAL & PROTOCOL TRANSFER
    # =========================================================================
    SkillTransferabilityRule(
        sourceSkill="REST APIs",
        targetSkill="GraphQL",
        relationshipType="CONCEPTUAL_TRANSFER",
        transferabilityScore=0.75,
        transferRationale="REST API architects understand client-server communication, schema validation, and HTTP status handling.",
        sharedCompetencies=["API Contract Design", "HTTP Status & Headers", "Authentication & Rate Limiting", "JSON Payloads"],
        criticalDifferences=["GraphQL Schema Definition Language (SDL)", "Resolvers and N+1 query batching (DataLoader)", "Single POST endpoint query paradigm"],
        verificationQuestions=["Have you designed GraphQL schemas and implemented backend DataLoader resolvers?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="REST APIs",
        targetSkill="gRPC",
        relationshipType="CONCEPTUAL_TRANSFER",
        transferabilityScore=0.75,
        transferRationale="Backend API developers understand remote procedure call semantics, payloads, and service interfaces.",
        sharedCompetencies=["Microservice Communication", "Payload Serialization", "API Versioning"],
        criticalDifferences=["Protocol Buffers (Protobuf) schema compilation", "HTTP/2 multiplexed bidirectional streaming"],
        verificationQuestions=["Have you authored .proto definition files and generated gRPC service handlers?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="RabbitMQ",
        targetSkill="Apache Kafka",
        relationshipType="CONCEPTUAL_TRANSFER",
        transferabilityScore=0.75,
        transferRationale="Both are distributed messaging backbones handling decoupled asynchronous event streaming.",
        sharedCompetencies=["Producer-Consumer Patterns", "Asynchronous Event Processing", "Message Acking & Dead-Letter Queues"],
        criticalDifferences=["Distributed append-only commit logs & consumer group partition offsets vs AMQP broker exchange/queue routing"],
        verificationQuestions=["Have you managed Kafka consumer group partition offsets and topic replication factors?"]
    ),
    SkillTransferabilityRule(
        sourceSkill="Apache Kafka",
        targetSkill="RabbitMQ",
        relationshipType="CONCEPTUAL_TRANSFER",
        transferabilityScore=0.85,
        transferRationale="Kafka event-streaming architects easily navigate AMQP exchange routing and broker queue semantics.",
        sharedCompetencies=["Message Broker Architecture", "Payload Serialization", "Backpressure Management"],
        criticalDifferences=["AMQP Exchange bindings (Direct/Topic/Fanout) vs Kafka topic partitions"],
        verificationQuestions=["Have you configured RabbitMQ topic/direct exchanges and dead-letter queue bindings?"]
    ),
]


class SkillTransferabilityGraph:
    """
    In-memory O(1) indexed transferability graph.
    Answers directional adjacency queries deterministically.
    """
    def __init__(self, rules: Optional[List[SkillTransferabilityRule]] = None):
        self._rules = rules or DETERMINISTIC_TRANSFERABILITY_RULES
        self._by_source: Dict[str, List[SkillTransferabilityRule]] = {}
        self._by_target: Dict[str, List[SkillTransferabilityRule]] = {}
        self._by_pair: Dict[Tuple[str, str], SkillTransferabilityRule] = {}
        self._build_index()

    def _build_index(self) -> None:
        for rule in self._rules:
            src = normalize_skill_name(rule.source_skill).lower()
            tgt = normalize_skill_name(rule.target_skill).lower()

            self._by_source.setdefault(src, []).append(rule)
            self._by_target.setdefault(tgt, []).append(rule)
            self._by_pair[(src, tgt)] = rule

    @property
    def total_rules(self) -> int:
        return len(self._rules)

    def get_all_rules(self) -> List[SkillTransferabilityRule]:
        return list(self._rules)

    def find_bridges_for_target(self, target_skill: str) -> List[SkillTransferabilityRule]:
        """Finds all rules where target_skill can be bridged from an adjacent skill."""
        if not target_skill:
            return []
        norm_tgt = normalize_skill_name(target_skill).lower()
        return self._by_target.get(norm_tgt, [])

    def find_bridges_from_source(self, source_skill: str) -> List[SkillTransferabilityRule]:
        """Finds all adjacent skills that can be bridged FROM source_skill."""
        if not source_skill:
            return []
        norm_src = normalize_skill_name(source_skill).lower()
        return self._by_source.get(norm_src, [])

    def get_exact_rule(self, source_skill: str, target_skill: str) -> Optional[SkillTransferabilityRule]:
        """Returns specific directional rule if one exists."""
        if not source_skill or not target_skill:
            return None
        norm_src = normalize_skill_name(source_skill).lower()
        norm_tgt = normalize_skill_name(target_skill).lower()
        return self._by_pair.get((norm_src, norm_tgt))


# Global Singleton Instance for O(1) Taxonomy Lookups
GLOBAL_TRANSFERABILITY_GRAPH = SkillTransferabilityGraph()


def get_transferability_rule(source_skill: str, target_skill: str) -> Optional[SkillTransferabilityRule]:
    """Helper to query global transferability graph for a specific directional rule."""
    return GLOBAL_TRANSFERABILITY_GRAPH.get_exact_rule(source_skill, target_skill)


def get_all_rules() -> List[SkillTransferabilityRule]:
    """Helper to retrieve all taxonomy rules."""
    return GLOBAL_TRANSFERABILITY_GRAPH.get_all_rules()
