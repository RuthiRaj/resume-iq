import crypto from "crypto";
import { AiAnalyzerProvider, AiAnalysisRequest, AiCandidateEvidence } from "./provider";
import { GeminiAnalyzerProvider } from "./gemini-provider";
import { AiAnalysisResult } from "./schemas";
import { ResumeSnapshot, ProfileData, EducationData, SkillData, ProjectData, ExperienceData, CertificationData } from "@/lib/validations";

/**
 * Factory function to retrieve the configured AI Analyzer Provider.
 * Allows effortless addition of new providers (e.g. Groq, Claude) in the future.
 */
export function getAiAnalyzerProvider(): AiAnalyzerProvider {
  const providerType = process.env.AI_ANALYZER_PROVIDER?.toLowerCase() || "gemini";

  switch (providerType) {
    case "gemini":
    default:
      return new GeminiAnalyzerProvider();
  }
}

/**
 * Generates a standard SHA-256 hash of the normalized job description.
 */
export function hashJobDescription(jobDescription: string): string {
  return crypto.createHash("sha256").update(jobDescription.trim()).digest("hex");
}

/**
 * Normalizes resume data (from an immutable snapshot or live entities) into strict candidate evidence.
 */
export function normalizeCandidateEvidence(data: {
  profile?: Partial<ProfileData>;
  experience?: ExperienceData[];
  projects?: ProjectData[];
  skills?: SkillData[];
  education?: EducationData[];
  certifications?: CertificationData[];
  customSummary?: string;
}): AiCandidateEvidence {
  return {
    headline: data.profile?.headline,
    summary: data.customSummary || data.profile?.summary || "",
    experience: (data.experience || []).map((exp) => ({
      role: exp.role,
      company: exp.company,
      location: exp.location,
      startDate: exp.startDate,
      endDate: exp.isCurrent ? "Present" : exp.endDate,
      bullets: exp.bullets || [],
      technologies: exp.technologies || [],
    })),
    projects: (data.projects || []).map((proj) => ({
      title: proj.title,
      role: proj.role,
      description: proj.description,
      highlights: proj.highlights || [],
      techStack: proj.techStack || [],
    })),
    skills: (data.skills || []).map((skill) => ({
      name: skill.name,
      category: skill.category,
      proficiency: skill.proficiency,
    })),
    education: (data.education || []).map((edu) => ({
      degree: edu.degree,
      institution: edu.institution,
      fieldOfStudy: edu.fieldOfStudy,
    })),
    certifications: (data.certifications || []).map((cert) => ({
      title: cert.title,
      issuer: cert.issuer,
    })),
  };
}

/**
 * Main service entry point for executing ATS Resume Analysis.
 */
export async function analyzeResumeService(params: {
  targetRole: string;
  targetCompany?: string;
  jobDescription: string;
  resumeData: {
    profile?: Partial<ProfileData>;
    experience?: ExperienceData[];
    projects?: ProjectData[];
    skills?: SkillData[];
    education?: EducationData[];
    certifications?: CertificationData[];
    customSummary?: string;
  };
}): Promise<AiAnalysisResult> {
  const provider = getAiAnalyzerProvider();
  const jobDescriptionHash = hashJobDescription(params.jobDescription);
  const candidateEvidence = normalizeCandidateEvidence(params.resumeData);

  const request: AiAnalysisRequest = {
    targetRole: params.targetRole,
    targetCompany: params.targetCompany,
    jobDescription: params.jobDescription,
    jobDescriptionHash,
    candidateEvidence,
  };

  return await provider.analyze(request);
}
