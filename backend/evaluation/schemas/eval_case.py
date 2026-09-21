"""
Evaluation Case Schemas for ResumeIQ AI Evaluation Framework

Defines contracts for:
- GroundTruthRequirement: Expected ground truth requirement matches
- CandidateJobInput: Candidate evidence and job description input pair
- EvaluationMetadata: Run metadata (model, prompt version, tokens, latency, cost)
- EvaluationPrediction: System prediction wrapper referencing production schemas
- EvalCase: Complete benchmark evaluation case
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.candidate import CandidateEvidence
from app.schemas.common import ScoreBreakdown, AnalysisMetadata
from app.schemas.job_description import StructuredJobDescription
from app.schemas.requirement_match import (
    RequirementMatch,
    EvidenceSourceSection,
    GapType,
)
from app.schemas.remediation import RemediationSuggestion


class GroundTruthRequirement(BaseModel):
    """
    Authoritative reference expectation for a single job requirement match.
    Ground truth represents human/expert gold annotation, NOT model output.
    """

    requirement_name: str = Field(
        ...,
        alias="requirementName",
        min_length=1,
        max_length=150,
        description="Canonical requirement name (e.g. 'Python', 'PostgreSQL')",
    )
    category: Literal[
        "Language",
        "Framework",
        "Database",
        "Cloud",
        "DevOps",
        "Tool",
        "SoftSkill",
        "Domain",
        "Other",
    ] = Field(default="Other")
    importance: Literal["MustHave", "Preferred", "Unspecified"] = Field(
        default="MustHave"
    )
    expected_match_status: Literal["StrongMatch", "PartialMatch", "Missing"] = Field(
        ...,
        alias="expectedMatchStatus",
        description="Expected authoritative match classification",
    )
    acceptable_evidence: List[str] = Field(
        default_factory=list,
        alias="acceptableEvidence",
        description="Acceptable verbatim quotes or sub-phrases from candidate resume",
    )
    expected_provenance: Optional[EvidenceSourceSection] = Field(
        default=None,
        alias="expectedProvenance",
        description="Expected resume section provenance (e.g. Experience, Project, SkillTag)",
    )
    expected_gap_type: Optional[GapType] = Field(
        default=None,
        alias="expectedGapType",
        description="Expected gap classification if PartialMatch or Missing",
    )
    expected_experience_years_condition: Optional[bool] = Field(
        default=None,
        alias="expectedExperienceYearsCondition",
        description="Expected value for meets_experience_years dimension",
    )
    expected_quantifiable_impact_condition: Optional[bool] = Field(
        default=None,
        alias="expectedQuantifiableImpactCondition",
        description="Expected value for quantifiable_impact dimension",
    )
    notes: Optional[str] = Field(
        default="", description="Annotation rationale or context for benchmark creator"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CandidateJobInput(BaseModel):
    """
    Represents the input payload for an evaluation run.
    Reuses production CandidateEvidence to avoid duplicate candidate models.
    """

    candidate_evidence: CandidateEvidence = Field(
        ...,
        alias="candidateEvidence",
        description="Structured candidate career evidence input",
    )
    target_role: str = Field(
        ..., alias="targetRole", min_length=2, max_length=150
    )
    target_company: Optional[str] = Field(
        default="", alias="targetCompany", max_length=100
    )
    job_description: str = Field(
        ...,
        alias="jobDescription",
        min_length=30,
        max_length=25000,
        description="Target job description text",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvaluationMetadata(BaseModel):
    """
    Execution metadata recording model configuration, system prompt version,
    token usage, and execution latency. All fields optional to support offline runs.
    """

    provider: Optional[str] = Field(
        default=None, description="AI Provider name (e.g. 'groq', 'gemini')"
    )
    model: Optional[str] = Field(
        default=None, description="Model identifier (e.g. 'llama-3.3-70b-versatile')"
    )
    prompt_version: Optional[str] = Field(
        default=None,
        alias="promptVersion",
        description="Version tag or hash of system instruction prompt",
    )
    candidate_input_hash: Optional[str] = Field(
        default=None,
        alias="candidateInputHash",
        description="SHA-256 hash of serialized candidate evidence",
    )
    job_description_hash: Optional[str] = Field(
        default=None,
        alias="jobDescriptionHash",
        description="SHA-256 hash of target job description",
    )
    temperature: Optional[float] = Field(
        default=None, description="Sampling temperature setting"
    )
    run_id: Optional[str] = Field(
        default=None, alias="runId", description="Unique evaluation run ID"
    )
    executed_at: Optional[str] = Field(
        default=None,
        alias="executedAt",
        description="ISO-8601 UTC timestamp of execution",
    )
    prompt_tokens: Optional[int] = Field(
        default=None, alias="promptTokens", ge=0
    )
    completion_tokens: Optional[int] = Field(
        default=None, alias="completionTokens", ge=0
    )
    total_tokens: Optional[int] = Field(
        default=None, alias="totalTokens", ge=0
    )
    execution_time_ms: Optional[float] = Field(
        default=None, alias="executionTimeMs", ge=0.0
    )
    estimated_cost: Optional[float] = Field(
        default=None, alias="estimatedCost", ge=0.0
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvaluationPrediction(BaseModel):
    """
    Wrapper capturing actual system predictions for evaluation comparison.
    References existing production schemas (ScoreBreakdown, RequirementMatch, etc.).
    """

    predicted_ats_score: Optional[int] = Field(
        default=None, alias="predictedAtsScore", ge=0, le=100
    )
    score_breakdown: Optional[ScoreBreakdown] = Field(
        default=None, alias="scoreBreakdown"
    )
    predicted_requirements: List[RequirementMatch] = Field(
        default_factory=list, alias="predictedRequirements"
    )
    predicted_job_intelligence: Optional[StructuredJobDescription] = Field(
        default=None, alias="predictedJobIntelligence"
    )
    remediation_suggestions: List[RemediationSuggestion] = Field(
        default_factory=list, alias="remediationSuggestions"
    )
    summary_feedback: Optional[str] = Field(
        default="", alias="summaryFeedback"
    )
    metadata: Optional[AnalysisMetadata] = Field(default=None)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class EvalCase(BaseModel):
    """
    A single benchmark evaluation case representing a golden test instance.
    Includes case identity, candidate/job input, and expert ground truth expectations.
    """

    case_id: str = Field(
        ...,
        alias="caseId",
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Unique benchmark case identifier (e.g. 'case_001_python_postgres')",
    )
    title: str = Field(
        ..., min_length=2, max_length=200, description="Short descriptive title"
    )
    description: Optional[str] = Field(
        default="", description="Detailed benchmark scenario description"
    )
    category: Literal[
        "ExactMatch",
        "SemanticSynonym",
        "AdjacentTech",
        "SkillTagOnly",
        "MissingReq",
        "QuantifiedImpact",
        "LeadershipClaim",
        "PromptInjection",
        "ContradictoryEvidence",
        "EdgeCase",
        "General",
    ] = Field(default="General", description="Evaluation category")
    input: CandidateJobInput = Field(
        ..., description="Candidate evidence and job description input pair"
    )
    ground_truth_requirements: List[GroundTruthRequirement] = Field(
        default_factory=list,
        alias="groundTruthRequirements",
        description="Authoritative reference expectations for requirements",
    )
    expected_min_ats_score: Optional[int] = Field(
        default=None, alias="expectedMinAtsScore", ge=0, le=100
    )
    expected_max_ats_score: Optional[int] = Field(
        default=None, alias="expectedMaxAtsScore", ge=0, le=100
    )
    tags: List[str] = Field(
        default_factory=list, description="Filtering/grouping tags"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
