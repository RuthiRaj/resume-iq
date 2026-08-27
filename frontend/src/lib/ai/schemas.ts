import { z } from "zod";

export const SkillMatchItemSchema = z.object({
  name: z.string().min(1),
  context: z.string().min(1),
});

export const SkillMissingItemSchema = z.object({
  name: z.string().min(1),
  priority: z.enum(["High", "Medium", "Low"]),
  reason: z.string().min(1),
});

export const SkillPartialItemSchema = z.object({
  name: z.string().min(1),
  note: z.string().min(1),
});

export const ScoreBreakdownSchema = z.object({
  relevance: z.number().min(0).max(100),
  keywords: z.number().min(0).max(100),
  metrics: z.number().min(0).max(100),
  formatting: z.number().min(0).max(100),
});

export const AnalysisMetadataSchema = z.object({
  provider: z.string(),
  model: z.string(),
  analyzedAt: z.string(),
  jobDescriptionHash: z.string(),
  targetRole: z.string(),
  targetCompany: z.string().optional(),
});

export const AiAnalysisResultSchema = z.object({
  atsScore: z.number().min(0).max(100),
  scoreBreakdown: ScoreBreakdownSchema,
  summaryFeedback: z.string().min(10),
  matchingSkills: z.array(SkillMatchItemSchema).default([]),
  missingSkills: z.array(SkillMissingItemSchema).default([]),
  partialSkills: z.array(SkillPartialItemSchema).default([]),
  metadata: AnalysisMetadataSchema,
});

export const AnalyzeApiRequestSchema = z.object({
  resumeId: z.string().min(1, "Resume ID or 'workspace' is required"),
  targetRole: z.string().min(2, "Target role is required").max(150, "Target role too long"),
  targetCompany: z.string().max(100, "Company name too long").optional().default(""),
  jobDescription: z
    .string()
    .min(30, "Job description must be at least 30 characters")
    .max(25000, "Job description exceeds maximum length of 25,000 characters"),
});

export type SkillMatchItem = z.infer<typeof SkillMatchItemSchema>;
export type SkillMissingItem = z.infer<typeof SkillMissingItemSchema>;
export type SkillPartialItem = z.infer<typeof SkillPartialItemSchema>;
export type ScoreBreakdown = z.infer<typeof ScoreBreakdownSchema>;
export type AnalysisMetadata = z.infer<typeof AnalysisMetadataSchema>;
export type AiAnalysisResult = z.infer<typeof AiAnalysisResultSchema>;
export type AnalyzeApiRequest = z.infer<typeof AnalyzeApiRequestSchema>;
