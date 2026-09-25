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
