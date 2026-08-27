import {
  AiAnalysisResult,
  SkillMatchItem,
  SkillMissingItem,
  SkillPartialItem,
  ScoreBreakdown,
  AnalysisMetadata,
} from "./schemas";

export interface AiCandidateEvidence {
  headline?: string;
  summary?: string;
  experience: Array<{
    role: string;
    company: string;
    location?: string;
    startDate?: string;
    endDate?: string;
    bullets: string[];
    technologies?: string[];
  }>;
  projects: Array<{
    title: string;
    role?: string;
    description: string;
    highlights: string[];
    techStack: string[];
  }>;
  skills: Array<{
    name: string;
    category: string;
    proficiency: string;
  }>;
  education: Array<{
    degree: string;
    institution: string;
    fieldOfStudy: string;
  }>;
  certifications?: Array<{
    title: string;
    issuer: string;
  }>;
}

export interface AiAnalysisRequest {
  targetRole: string;
  targetCompany?: string;
  jobDescription: string;
  jobDescriptionHash: string;
  candidateEvidence: AiCandidateEvidence;
}

/**
 * Provider-agnostic interface for ATS resume analysis.
 * Future providers (e.g. Groq, Claude, OpenAI) can be added by implementing this interface.
 */
export interface AiAnalyzerProvider {
  readonly name: string;
  analyze(request: AiAnalysisRequest): Promise<AiAnalysisResult>;
}
