"""
Evaluation Schemas for ResumeIQ Phase 4.0.5 AI Evaluation Framework

Defines strict, deterministic, Pydantic v2 contracts for:
- EvaluationTaskType: Classification of the AI evaluation task (including abstention & confidence)
- EvaluationCase: Input payload, expectations, and metadata for a benchmark case
- EvaluationResult: Granular, explainable outcome of evaluating a single case
- CategoryMetrics: Aggregated metrics across task categories
- EvaluationSuiteReport: Complete benchmark evaluation run report
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal, Set
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.candidate import CandidateEvidence
from app.schemas.evidence import EvidenceItem, VerificationStatus
from app.schemas.decision import DecisionType, ConfidenceBreakdown, AIAbstentionDecision


EvaluationTaskType = Literal[
    "retrieval",
    "grounding",
    "planning",
    "security",
    "determinism",
    "abstention",
]

ExpectedMatchClass = Literal[
    "direct_match",
    "semantic_match",
    "related_but_unverified",
    "missing",
    "user_confirmation_required",
]


class EvaluationCase(BaseModel):
    """
    Complete specification for a single synthetic AI evaluation case.
    Must be deterministic, serializable, and free of real personal data.
    """
    case_id: str = Field(..., alias="caseId", description="Unique case identifier e.g. CASE_001")
    description: str = Field(..., description="Human-readable description of what this case verifies")
    task_type: EvaluationTaskType = Field(..., alias="taskType", description="Category of evaluation")
    
    # Input Fixtures
    workspace_fixture: CandidateEvidence = Field(
        ...,
        alias="workspaceFixture",
        description="Candidate workspace evidence fixture",
    )
    job_description_fixture: Dict[str, Any] = Field(
        default_factory=dict,
        alias="jobDescriptionFixture",
        description="Job requirements fixture (targetRole, jobDescription, mustHaveSkills, etc.)",
    )
    
    # Authoritative Gold Expectations
    expected_evidence: List[str] = Field(
        default_factory=list,
        alias="expectedEvidence",
        description="Evidence item IDs or titles that MUST be retrieved/selected",
    )
    expected_graded_relevance: Optional[Dict[str, int]] = Field(
        default=None,
        alias="expectedGradedRelevance",
        description="Mapping of evidence item ID to expected graded relevance level (0=Irrelevant, 1=Peripheral, 2=Supporting, 3=Core/Exact)",
    )
    expected_non_matches: List[str] = Field(
        default_factory=list,
        alias="expectedNonMatches",
        description="Evidence item IDs, technologies, or claims that must NOT match or be selected",
    )
    expected_match_classes: Dict[str, str] = Field(
        default_factory=dict,
        alias="expectedMatchClasses",
        description="Mapping of requirement/skill to expected MatchClass",
    )
    expected_gaps: List[str] = Field(
        default_factory=list,
        alias="expectedGaps",
        description="Skills or requirements that must trigger as missing/hard gaps",
    )
    expected_prohibited_claims: List[str] = Field(
        default_factory=list,
        alias="expectedProhibitedClaims",
        description="Directives/prohibited claim instructions that must be generated",
    )
    expected_provenance: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="expectedProvenance",
        description="Expected provenance metadata (sourceType, sourceItemId, document link)",
    )
    
    # Synthetic Generation Payload (for testing grounding against adversarial / hallucinated LLM responses)
    synthetic_generation_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="syntheticGenerationPayload",
        description="Simulated LLM response used to test deterministic claim validation without external APIs",
    )
    
    # Security / Auth Context Fixture
    auth_context: Optional[Dict[str, str]] = Field(
        default=None,
        alias="authContext",
        description="Security context (e.g. evaluating user ID vs resource owner ID)",
    )

    # Phase 4.0.5 Decision / Abstention Expectations
    expected_decision: Optional[DecisionType] = Field(
        default=None,
        alias="expectedDecision",
        description="Expected authoritative decision: ACCEPT, REVIEW, or ABSTAIN",
    )
    expected_decision_reasons: List[str] = Field(
        default_factory=list,
        alias="expectedDecisionReasons",
        description="Expected reason substrings that must appear in decision reasoning",
    )
    expected_review_prompts: List[str] = Field(
        default_factory=list,
        alias="expectedReviewPrompts",
        description="Expected candidate review prompts for REVIEW decisions",
    )
    expected_min_confidence: Optional[float] = Field(
        default=None,
        alias="expectedMinConfidence",
        description="Lower bound for expected overall confidence score",
    )
    expected_max_confidence: Optional[float] = Field(
        default=None,
        alias="expectedMaxConfidence",
        description="Upper bound for expected overall confidence score",
    )
    has_conflicting_evidence: bool = Field(
        default=False,
        alias="hasConflictingEvidence",
        description="Whether workspace fixture contains mutually conflicting evidence",
    )
    is_prompt_injection_detected: bool = Field(
        default=False,
        alias="isPromptInjectionDetected",
        description="Whether adversarial prompt manipulation is embedded in test inputs",
    )
    
    evaluation_tags: List[str] = Field(
        default_factory=list,
        alias="evaluationTags",
        description="Tags for filtering (e.g. ['exact_match', 'security', 'abstention', 'regression'])",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvaluationResult(BaseModel):
    """
    Granular, explainable result of evaluating a single EvaluationCase.
    Never uses an opaque pass/fail flag; provides full metric breakdown and failure reasons.
    """
    case_id: str = Field(..., alias="caseId")
    task_type: EvaluationTaskType = Field(..., alias="taskType")
    passed: bool = Field(..., description="Whether the case satisfied all gold expectations")
    score: float = Field(default=1.0, ge=0.0, le=1.0, description="Normalized case score [0.0, 1.0]")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Fine-grained metric values for this case")
    expected: Dict[str, Any] = Field(default_factory=dict, description="Expected gold values")
    actual: Dict[str, Any] = Field(default_factory=dict, description="Actual evaluated system outputs")
    failures: List[str] = Field(default_factory=list, description="List of specific expectation failures")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or soft mismatches")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic payload for debugging")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CategorySummary(BaseModel):
    """Summary metrics for a specific evaluation category."""
    task_type: EvaluationTaskType = Field(..., alias="taskType")
    total_cases: int = Field(default=0, alias="totalCases")
    passed_cases: int = Field(default=0, alias="passedCases")
    failed_cases: int = Field(default=0, alias="failedCases")
    pass_rate: float = Field(default=0.0, alias="passRate")
    aggregated_metrics: Dict[str, float] = Field(default_factory=dict, alias="aggregatedMetrics")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvaluationSuiteReport(BaseModel):
    """
    Complete benchmark evaluation run report.
    Fully versioned and reproducible.
    """
    dataset_version: str = Field(default="4.0.5", alias="datasetVersion")
    evaluator_version: str = Field(default="4.0.5", alias="evaluatorVersion")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of evaluation run",
    )
    total_cases: int = Field(..., alias="totalCases")
    passed_cases: int = Field(..., alias="passedCases")
    failed_cases: int = Field(..., alias="failedCases")
    overall_pass_rate: float = Field(..., alias="overallPassRate")
    category_summaries: Dict[str, CategorySummary] = Field(
        default_factory=dict,
        alias="categorySummaries",
    )
    results: List[EvaluationResult] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
