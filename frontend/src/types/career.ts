export type SkillRelationshipType =
  | "FRAMEWORK_FAMILY"
  | "DATABASE_FAMILY"
  | "LANGUAGE_FAMILY"
  | "CLOUD_PLATFORM_FAMILY"
  | "DEVOPS_ORCHESTRATION"
  | "ML_FRAMEWORK_FAMILY"
  | "CONCEPTUAL_TRANSFER";

export type GapSeverity =
  | "HardExperientialGap"
  | "MissingDomainCertification"
  | "LearnableAdjacentSkill"
  | "CandidateAttestationRequired";

export interface TransferableSkillBridge {
  bridgeId: string;
  requiredSkill: string;
  candidateSkill: string;
  sourceEvidenceId: string;
  sourceEvidenceTitle: string;
  sourceSection: string;
  relationshipType: SkillRelationshipType;
  transferabilityScore: number;
  transferRationale: string;
  sharedCompetencies: string[];
  criticalDifferences: string[];
  attestationPrompt: string;
  status: "TransferablePossibility" | "AttestationRequired" | "UserAttested" | "Dismissed";
}

export interface ActionableLearningPath {
  title: string;
  estimatedWeeks: number;
  keyMilestones: string[];
  authoritativeDocsUrl?: string;
}

export interface ProjectBlueprint {
  projectTitle: string;
  problemStatement: string;
  architectureComponents: string[];
  demonstratedSkills: string[];
  verificationChecklist: string[];
}

export interface GapRemediationStrategy {
  requirementName: string;
  gapType: string;
  severity: GapSeverity;
  remediationGuidance: string;
  learningPaths: ActionableLearningPath[];
  projectBlueprints: ProjectBlueprint[];
}

export interface AnalyzeGapsResponse {
  variantId: string;
  totalRequirements: number;
  matchedCount: number;
  transferableBridgesCount: number;
  hardGapsCount: number;
  transferableBridges: TransferableSkillBridge[];
  hardGapRemediations: GapRemediationStrategy[];
}

export interface CandidateAttestationRequest {
  variantId: string;
  requirementName: string;
  adjacentSkillUsed?: string;
  targetItemId: string;
  targetBulletIndex?: number;
  attestedContext: string;
  attestedActions: string;
  durationOrScale?: string;
  expectedVersion?: number;
  applyToWorkspace: boolean;
}

export interface AttestSkillResponse {
  success: boolean;
  attestationId: string;
  status: string;
  requirementName: string;
  changeRecord: any;
  newVersion: number;
  validation: {
    isValid: boolean;
    status: string;
    unsupportedClaims?: Array<{
      category: string;
      claimText: string;
      reason: string;
    }>;
  };
  message: string;
}

export type MilestoneCategory =
  | "TransferableBridge"
  | "CoreFoundation"
  | "VerifiableProject"
  | "DomainCertification";

export type MilestoneState =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "ARTIFACT_SUBMITTED"
  | "VERIFIED_PROJECT"
  | "ATTESTED";

export type ArtifactType =
  | "GitHubRepository"
  | "DeploymentUrl"
  | "TechnicalWriteup"
  | "AttestationRecord";

export interface TargetImportanceBreakdown {
  mustHaveCount: number;
  preferredCount: number;
}

export interface VerificationArtifact {
  artifactId: string;
  artifactType: ArtifactType;
  url?: string;
  repositoryBranch?: string;
  checklistCompleted: string[];
  submittedAt: string;
  provenanceHash: string;
}

export interface VerificationArtifactInput {
  artifactType?: ArtifactType;
  url?: string;
  repositoryBranch?: string;
  checklistCompleted?: string[];
}

export type RoadmapLifecycle =
  | "ACTIVE"
  | "COMPLETED"
  | "ARCHIVED";

export type ReconciliationStatus =
  | "NOT_GROUNDED"
  | "GROUNDED_BY_WORKSPACE"
  | "GROUNDED_BY_PROMOTED_PROJECT"
  | "RELATED_UNVERIFIED";

export interface MilestoneReconciliation {
  status: ReconciliationStatus;
  matchedEvidenceId?: string;
  matchedEvidenceTitle?: string;
  matchedEvidenceSection?: string;
  reconciliationNotes: string;
  promotedProjectId?: string;
  reconciledAt: string;
}

export interface RoadmapMilestone {
  milestoneId: string;
  orderIndex: number;
  title: string;
  category: MilestoneCategory;
  requirementName: string;
  importance: "MustHave" | "Preferred" | "Unspecified";
  targetCapability: string;
  prerequisiteEvidenceIds: string[];
  prerequisiteMilestoneIds: string[];
  sourceBridgeId?: string;
  rationale: string;
  estimatedWeeks: number;
  learningPath?: ActionableLearningPath;
  projectBlueprint?: ProjectBlueprint;
  bridgeDetails?: TransferableSkillBridge;
  state: MilestoneState;
  verificationArtifact?: VerificationArtifact;
  promotedProjectId?: string;
  workspaceEvidenceIds?: string[];
  reconciliation?: MilestoneReconciliation;
  startedAt?: string;
  completedAt?: string;
}

export interface RoadmapProvenance {
  sourceVariantId?: string;
  sourceAnalysisScore?: number;
  generatedAt: string;
  generatorVersion: string;
  provenanceHash: string;
}

export interface RoadmapSnapshotRecord {
  snapshotId: string;
  version: number;
  workspaceEvidenceHash: string;
  targetRole: string;
  targetCompany?: string;
  milestoneCount: number;
  completedMilestones: number;
  overallProgressPct: number;
  createdAt: string;
  lifecycle: RoadmapLifecycle;
}

export interface RoadmapPlan {
  roadmapId: string;
  userId: string;
  title: string;
  targetRole: string;
  targetCompany?: string;
  targetLevel?: string;
  sourceVariantId?: string;
  version: number;
  lifecycle: RoadmapLifecycle;
  workspaceEvidenceHash?: string;
  isStale?: boolean;
  reconciledAt?: string;
  totalMilestones: number;
  completedMilestones: number;
  overallProgressPct: number;
  estimatedTotalWeeks: number;
  targetImportanceBreakdown: TargetImportanceBreakdown;
  nextRecommendedMilestoneId?: string;
  milestones: RoadmapMilestone[];
  historySnapshots?: RoadmapSnapshotRecord[];
  provenance?: RoadmapProvenance;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateRoadmapRequest {
  variantId?: string;
  targetRole?: string;
  targetCompany?: string;
  jobDescription?: string;
}

export interface UpdateMilestoneProgressRequest {
  milestoneId: string;
  targetState: MilestoneState;
  expectedVersion: number;
  artifact?: VerificationArtifactInput;
  attestation?: CandidateAttestationRequest;
}

export interface ReconcileRoadmapResponse {
  roadmapId: string;
  reconciledAt: string;
  isStale: boolean;
  groundedCount: number;
  unverifiedCount: number;
  notGroundedCount: number;
  lifecycle: RoadmapLifecycle;
  updatedPlan: RoadmapPlan;
}

export interface RefreshRoadmapRequest {
  expectedVersion: number;
}

export interface RefreshRoadmapResponse {
  roadmapId: string;
  refreshedAt: string;
  previousVersion: number;
  newVersion: number;
  isStale: boolean;
  completedMilestonesPreserved: number;
  remainingMilestonesReconciled: number;
  lifecycle: RoadmapLifecycle;
  updatedPlan: RoadmapPlan;
}

export interface UpdateRoadmapLifecycleRequest {
  lifecycle: RoadmapLifecycle;
  expectedVersion: number;
}

export interface ListRoadmapsResponse {
  total: number;
  roadmaps: RoadmapPlan[];
}

export interface DeleteRoadmapResponse {
  success: boolean;
  roadmapId: string;
  message: string;
}
