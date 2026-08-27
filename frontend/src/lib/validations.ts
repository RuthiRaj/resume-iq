import { z } from "zod";

export const ProfileSchema = z.object({
  fullName: z.string().min(2, "Full name is required"),
  headline: z.string().min(3, "Professional headline is required"),
  email: z.string().email("Invalid email address"),
  phone: z.string().min(7, "Valid phone number is required"),
  location: z.string().min(2, "Location is required"),
  website: z.string().url("Invalid URL").or(z.literal("")).optional(),
  linkedin: z.string().url("Invalid LinkedIn URL").or(z.literal("")).optional(),
  github: z.string().url("Invalid GitHub URL").or(z.literal("")).optional(),
  summary: z.string().min(20, "Summary should be at least 20 characters"),
  targetRoles: z.array(z.string()).min(1, "At least one target role is required"),
});

export const EducationSchema = z.object({
  id: z.string().optional(),
  institution: z.string().min(2, "Institution name is required"),
  degree: z.string().min(2, "Degree is required"),
  fieldOfStudy: z.string().min(2, "Field of study is required"),
  startDate: z.string().min(4, "Start date is required"),
  endDate: z.string().min(4, "End date or expected date is required"),
  grade: z.string().optional(),
  activities: z.string().optional(),
  courses: z.array(z.string()).optional(),
});

export const SkillSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1, "Skill name is required"),
  category: z.enum(["Languages", "Frameworks & Libraries", "Cloud & DevOps", "Databases & Tools", "Methodologies & Soft Skills"]),
  proficiency: z.enum(["Beginner", "Intermediate", "Advanced", "Expert"]),
  yearsOfExperience: z.number().min(0).max(50).optional(),
});

export const ProjectSchema = z.object({
  id: z.string().optional(),
  title: z.string().min(2, "Project title is required"),
  role: z.string().min(2, "Your role is required"),
  startDate: z.string().min(4, "Start date is required"),
  endDate: z.string().min(4, "End date is required"),
  description: z.string().min(10, "Description is required"),
  highlights: z.array(z.string()).min(1, "At least one bullet point is required"),
  techStack: z.array(z.string()).min(1, "At least one technology tag is required"),
  liveUrl: z.string().url("Invalid URL").or(z.literal("")).optional(),
  repoUrl: z.string().url("Invalid URL").or(z.literal("")).optional(),
});

export const ExperienceSchema = z.object({
  id: z.string().optional(),
  company: z.string().min(2, "Company name is required"),
  role: z.string().min(2, "Job title/role is required"),
  location: z.string().min(2, "Location is required"),
  startDate: z.string().min(4, "Start date is required"),
  endDate: z.string().min(4, "End date or 'Present' is required"),
  isCurrent: z.boolean().default(false),
  bullets: z.array(z.string()).min(1, "At least one bullet point is required"),
  technologies: z.array(z.string()).optional(),
});

export const CertificationSchema = z.object({
  id: z.string().optional(),
  title: z.string().min(2, "Certification name is required"),
  issuer: z.string().min(2, "Issuing organization is required"),
  issueDate: z.string().min(4, "Issue date is required"),
  expiryDate: z.string().optional(),
  credentialId: z.string().optional(),
  credentialUrl: z.string().url("Invalid URL").or(z.literal("")).optional(),
});

export const AchievementSchema = z.object({
  id: z.string().optional(),
  title: z.string().min(2, "Title is required"),
  issuer: z.string().min(2, "Organization/Event is required"),
  date: z.string().min(4, "Date is required"),
  description: z.string().min(10, "Description is required"),
  url: z.string().url("Invalid URL").or(z.literal("")).optional(),
});

export const DocumentSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1, "File name is required"),
  type: z.enum(["Resume", "Transcript", "Certificate", "Recommendation", "Other"]),
  fileSize: z.string(),
  uploadDate: z.string(),
  parsedStatus: z.enum(["Parsed", "Processing", "Failed", "Pending"]),
  content: z.string().optional(),
});

export const AnalyzerInputSchema = z.object({
  resumeId: z.string().min(1, "Select a resume or workspace profile"),
  jobTitle: z.string().min(2, "Target job title is required"),
  company: z.string().optional(),
  jobDescription: z.string().min(30, "Job description must be at least 30 characters"),
});

export const AuthLoginSchema = z.object({
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
  rememberMe: z.boolean().optional(),
});

export const AuthRegisterSchema = z.object({
  fullName: z.string().min(2, "Full name is required"),
  email: z.string().email("Please enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string().min(8, "Confirm password is required"),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

export const AuthResetSchema = z.object({
  email: z.string().email("Please enter a valid email"),
});

export const ResumeSnapshotSchema = z.object({
  profile: ProfileSchema,
  education: z.array(EducationSchema).default([]),
  skills: z.array(SkillSchema).default([]),
  projects: z.array(ProjectSchema).default([]),
  experience: z.array(ExperienceSchema).default([]),
  certifications: z.array(CertificationSchema).default([]),
  customSummary: z.string().optional(),
});

export type ProfileData = z.infer<typeof ProfileSchema>;
export type EducationData = z.infer<typeof EducationSchema>;
export type SkillData = z.infer<typeof SkillSchema>;
export type ProjectData = z.infer<typeof ProjectSchema>;
export type ExperienceData = z.infer<typeof ExperienceSchema>;
export type CertificationData = z.infer<typeof CertificationSchema>;
export type AchievementData = z.infer<typeof AchievementSchema>;
export type DocumentData = z.infer<typeof DocumentSchema>;
export type AnalyzerInputData = z.infer<typeof AnalyzerInputSchema>;
export type ResumeSnapshot = z.infer<typeof ResumeSnapshotSchema>;
