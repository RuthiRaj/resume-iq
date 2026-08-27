"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useAuth } from "./auth-context";
import { db, storage } from "./firebase";
import {
  collection,
  doc,
  setDoc,
  addDoc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp,
} from "firebase/firestore";
import { ref, uploadBytesResumable, getDownloadURL, deleteObject } from "firebase/storage";
import {
  ProfileData,
  EducationData,
  SkillData,
  ProjectData,
  ExperienceData,
  CertificationData,
  AchievementData,
  DocumentData,
  ResumeSnapshot,
} from "./validations";

export type { ResumeSnapshot };

export interface AnalysisResultData {
  summaryFeedback: string;
  matchingSkills: Array<{ name: string; context: string }>;
  missingSkills: Array<{ name: string; priority: "High" | "Medium" | "Low"; reason: string }>;
  partialSkills: Array<{ name: string; note: string }>;
  metadata?: {
    provider: string;
    model: string;
    analyzedAt: string;
    jobDescriptionHash?: string;
    targetRole?: string;
    targetCompany?: string;
  };
}

export interface ResumeItem {
  id: string;
  title: string;
  targetRole: string;
  targetCompany?: string;
  template: "modern" | "minimal" | "professional" | "ats";
  lastEdited: string;
  score: number;
  tags: string[];
  sections: {
    summary: string;
    experiences: string[];
    projects: string[];
    education: string[];
    skills: string[];
    certifications: string[];
  };
  snapshot?: ResumeSnapshot;
  customHighlights?: Record<string, string[]>;
  atsScore?: number;
  scoreBreakdown?: {
    relevance: number;
    keywords: number;
    metrics: number;
    formatting: number;
  };
  analysisResults?: AnalysisResultData;
  lastAnalyzedAt?: string;
}

export interface RecommendedAction {
  id: string;
  title: string;
  category: "Skills" | "Projects" | "Experience" | "ATS Match";
  impact: "High" | "Medium" | "Low";
  description: string;
  actionUrl: string;
}

const defaultEmptyProfile: ProfileData = {
  fullName: "",
  headline: "",
  email: "",
  phone: "",
  location: "",
  website: "",
  linkedin: "",
  github: "",
  summary: "",
  targetRoles: [],
};

interface CareerContextType {
  profile: ProfileData;
  updateProfile: (data: ProfileData) => Promise<void>;

  education: EducationData[];
  addEducation: (data: Omit<EducationData, "id">) => Promise<void>;
  updateEducation: (id: string, data: Partial<EducationData>) => Promise<void>;
  deleteEducation: (id: string) => Promise<void>;

  skills: SkillData[];
  addSkill: (data: Omit<SkillData, "id">) => Promise<void>;
  updateSkill: (id: string, data: Partial<SkillData>) => Promise<void>;
  deleteSkill: (id: string) => Promise<void>;

  projects: ProjectData[];
  addProject: (data: Omit<ProjectData, "id">) => Promise<void>;
  updateProject: (id: string, data: Partial<ProjectData>) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;

  experience: ExperienceData[];
  addExperience: (data: Omit<ExperienceData, "id">) => Promise<void>;
  updateExperience: (id: string, data: Partial<ExperienceData>) => Promise<void>;
  deleteExperience: (id: string) => Promise<void>;

  certifications: CertificationData[];
  addCertification: (data: Omit<CertificationData, "id">) => Promise<void>;
  updateCertification: (id: string, data: Partial<CertificationData>) => Promise<void>;
  deleteCertification: (id: string) => Promise<void>;

  achievements: AchievementData[];
  addAchievement: (data: Omit<AchievementData, "id">) => Promise<void>;
  updateAchievement: (id: string, data: Partial<AchievementData>) => Promise<void>;
  deleteAchievement: (id: string) => Promise<void>;

  documents: DocumentData[];
  addDocument: (data: Omit<DocumentData, "id">, file?: File) => Promise<void>;
  deleteDocument: (id: string, storagePath?: string) => Promise<void>;

  resumes: ResumeItem[];
  addResume: (resume: Omit<ResumeItem, "id">) => Promise<string>;
  updateResume: (id: string, data: Partial<ResumeItem>) => Promise<void>;
  deleteResume: (id: string) => Promise<void>;
  duplicateResume: (id: string) => Promise<void>;
  saveAtsAnalysis: (
    resumeId: string,
    analysis: {
      atsScore: number;
      scoreBreakdown: { relevance: number; keywords: number; metrics: number; formatting: number };
      targetRole?: string;
      targetCompany?: string;
      analysisResults?: AnalysisResultData;
    }
  ) => Promise<void>;

  actions: RecommendedAction[];
  dismissAction: (id: string) => Promise<void>;

  seedSampleData: () => Promise<void>;
  isLoaded: boolean;
}

const CareerContext = createContext<CareerContextType | null>(null);

export function CareerProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  const [profile, setProfile] = useState<ProfileData>(defaultEmptyProfile);
  const [education, setEducation] = useState<EducationData[]>([]);
  const [skills, setSkills] = useState<SkillData[]>([]);
  const [projects, setProjects] = useState<ProjectData[]>([]);
  const [experience, setExperience] = useState<ExperienceData[]>([]);
  const [certifications, setCertifications] = useState<CertificationData[]>([]);
  const [achievements, setAchievements] = useState<AchievementData[]>([]);
  const [documents, setDocuments] = useState<DocumentData[]>([]);
  const [resumes, setResumes] = useState<ResumeItem[]>([]);
  const [actions, setActions] = useState<RecommendedAction[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Set up real-time Firestore listeners for all collections scoped to user.uid
  useEffect(() => {
    if (!user) {
      setProfile(defaultEmptyProfile);
      setEducation([]);
      setSkills([]);
      setProjects([]);
      setExperience([]);
      setCertifications([]);
      setAchievements([]);
      setDocuments([]);
      setResumes([]);
      setActions([]);
      setIsLoaded(true);
      return;
    }

    const uid = user.uid;

    // 1. Profile listener
    const unsubProfile = onSnapshot(doc(db, "users", uid, "profile", "main"), (snap) => {
      if (snap.exists()) {
        setProfile(snap.data() as ProfileData);
      } else {
        setProfile({
          ...defaultEmptyProfile,
          email: user.email || "",
          fullName: user.displayName || "",
        });
      }
    });

    // 2. Education listener
    const unsubEducation = onSnapshot(collection(db, "users", uid, "education"), (snap) => {
      const list: EducationData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as EducationData));
      setEducation(list);
    });

    // 3. Skills listener
    const unsubSkills = onSnapshot(collection(db, "users", uid, "skills"), (snap) => {
      const list: SkillData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as SkillData));
      setSkills(list);
    });

    // 4. Projects listener
    const unsubProjects = onSnapshot(collection(db, "users", uid, "projects"), (snap) => {
      const list: ProjectData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ProjectData));
      setProjects(list);
    });

    // 5. Experience listener
    const unsubExperience = onSnapshot(collection(db, "users", uid, "experience"), (snap) => {
      const list: ExperienceData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ExperienceData));
      setExperience(list);
    });

    // 6. Certifications listener
    const unsubCertifications = onSnapshot(collection(db, "users", uid, "certifications"), (snap) => {
      const list: CertificationData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as CertificationData));
      setCertifications(list);
    });

    // 7. Achievements listener
    const unsubAchievements = onSnapshot(collection(db, "users", uid, "achievements"), (snap) => {
      const list: AchievementData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as AchievementData));
      setAchievements(list);
    });

    // 8. Documents listener
    const unsubDocuments = onSnapshot(collection(db, "users", uid, "documents"), (snap) => {
      const list: DocumentData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as DocumentData));
      setDocuments(list);
    });

    // 9. Resumes listener
    const unsubResumes = onSnapshot(collection(db, "users", uid, "resumes"), (snap) => {
      const list: ResumeItem[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ResumeItem));
      setResumes(list);
    });

    // 10. Actions listener
    const unsubActions = onSnapshot(collection(db, "users", uid, "actions"), (snap) => {
      const list: RecommendedAction[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as RecommendedAction));
      setActions(list);
      setIsLoaded(true);
    });

    return () => {
      unsubProfile();
      unsubEducation();
      unsubSkills();
      unsubProjects();
      unsubExperience();
      unsubCertifications();
      unsubAchievements();
      unsubDocuments();
      unsubResumes();
      unsubActions();
    };
  }, [user]);

  // Firestore CRUD Operations
  const updateProfile = async (data: ProfileData) => {
    if (!user) return;
    await setDoc(doc(db, "users", user.uid, "profile", "main"), data, { merge: true });
  };

  const addEducation = async (data: Omit<EducationData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "education"), data);
  };

  const updateEducation = async (id: string, data: Partial<EducationData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "education", id), data);
  };

  const deleteEducation = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "education", id));
  };

  const addSkill = async (data: Omit<SkillData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "skills"), data);
  };

  const updateSkill = async (id: string, data: Partial<SkillData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "skills", id), data);
  };

  const deleteSkill = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "skills", id));
  };

  const addProject = async (data: Omit<ProjectData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "projects"), data);
  };

  const updateProject = async (id: string, data: Partial<ProjectData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "projects", id), data);
  };

  const deleteProject = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "projects", id));
  };

  const addExperience = async (data: Omit<ExperienceData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "experience"), data);
  };

  const updateExperience = async (id: string, data: Partial<ExperienceData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "experience", id), data);
  };

  const deleteExperience = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "experience", id));
  };

  const addCertification = async (data: Omit<CertificationData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "certifications"), data);
  };

  const updateCertification = async (id: string, data: Partial<CertificationData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "certifications", id), data);
  };

  const deleteCertification = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "certifications", id));
  };

  const addAchievement = async (data: Omit<AchievementData, "id">) => {
    if (!user) return;
    await addDoc(collection(db, "users", user.uid, "achievements"), data);
  };

  const updateAchievement = async (id: string, data: Partial<AchievementData>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "achievements", id), data);
  };

  const deleteAchievement = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "achievements", id));
  };

  const addDocument = async (data: Omit<DocumentData, "id">, file?: File) => {
    if (!user) return;
    let fileUrl = "";
    let storagePath = "";

    if (file) {
      const sanitizedName = `${Date.now()}_${file.name.replace(/[^a-zA-Z0-9.-]/g, "_")}`;
      storagePath = `users/${user.uid}/documents/${sanitizedName}`;
      const fileRef = ref(storage, storagePath);
      await uploadBytesResumable(fileRef, file);
      try {
        fileUrl = await getDownloadURL(fileRef);
      } catch {
        // Storage URL placeholder if storage is still initializing
        fileUrl = "";
      }
    }

    await addDoc(collection(db, "users", user.uid, "documents"), {
      ...data,
      fileUrl,
      storagePath,
      createdAt: new Date().toISOString(),
    });
  };

  const deleteDocument = async (id: string, storagePath?: string) => {
    if (!user) return;
    if (storagePath) {
      try {
        const fileRef = ref(storage, storagePath);
        await deleteObject(fileRef);
      } catch {
        // ignore storage deletion errors
      }
    }
    await deleteDoc(doc(db, "users", user.uid, "documents", id));
  };

  const addResume = async (resume: Omit<ResumeItem, "id">): Promise<string> => {
    if (!user) throw new Error("Unauthenticated");
    const docRef = await addDoc(collection(db, "users", user.uid, "resumes"), {
      ...resume,
      createdAt: new Date().toISOString(),
    });
    return docRef.id;
  };

  const updateResume = async (id: string, data: Partial<ResumeItem>) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "resumes", id), {
      ...data,
      lastEdited: new Date().toISOString().split("T")[0],
    });
  };

  const deleteResume = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "resumes", id));
  };

  const duplicateResume = async (id: string) => {
    if (!user) return;
    const source = resumes.find((r) => r.id === id);
    if (!source) return;
    const { id: _, ...rest } = source;
    await addDoc(collection(db, "users", user.uid, "resumes"), {
      ...rest,
      title: `${source.title} (Copy)`,
      lastEdited: new Date().toISOString().split("T")[0],
    });
  };

  const saveAtsAnalysis = async (
    resumeId: string,
    analysis: {
      atsScore: number;
      scoreBreakdown: { relevance: number; keywords: number; metrics: number; formatting: number };
      targetRole?: string;
      targetCompany?: string;
      analysisResults?: AnalysisResultData;
    }
  ) => {
    if (!user) return;
    await updateDoc(doc(db, "users", user.uid, "resumes", resumeId), {
      score: analysis.atsScore,
      atsScore: analysis.atsScore,
      scoreBreakdown: analysis.scoreBreakdown,
      lastAnalyzedAt: new Date().toISOString(),
      ...(analysis.targetRole ? { targetRole: analysis.targetRole } : {}),
      ...(analysis.targetCompany ? { targetCompany: analysis.targetCompany } : {}),
      ...(analysis.analysisResults ? { analysisResults: analysis.analysisResults } : {}),
    });
  };

  const dismissAction = async (id: string) => {
    if (!user) return;
    await deleteDoc(doc(db, "users", user.uid, "actions", id));
  };

  // Seed sample data explicitly on demand for demos/testing
  const seedSampleData = async () => {
    if (!user) return;
    const uid = user.uid;

    // 1. Profile
    await setDoc(
      doc(db, "users", uid, "profile", "main"),
      {
        fullName: profile.fullName || user.displayName || "Alex Morgan",
        headline: "Full Stack Engineer & AI Systems Specialist",
        email: user.email || "alex.morgan@example.com",
        phone: "+1 (555) 382-9104",
        location: "San Francisco, CA (Open to Remote)",
        website: "https://alexmorgan.dev",
        linkedin: "https://linkedin.com/in/alexmorgan-dev",
        github: "https://github.com/alexmorgan-dev",
        summary:
          "Full-stack software engineer with 3+ years of experience architecting high-throughput distributed systems, modern React/Next.js client applications, and LLM-powered workflows.",
        targetRoles: ["Senior Frontend Engineer", "Full Stack AI Engineer", "Software Architect"],
      },
      { merge: true }
    );

    // 2. Education
    await addDoc(collection(db, "users", uid, "education"), {
      institution: "University of California, Berkeley",
      degree: "B.S. in Computer Science & Data Intelligence",
      fieldOfStudy: "Computer Science",
      startDate: "2020-08",
      endDate: "2024-05",
      grade: "3.88 / 4.0 GPA (Dean's Honor List)",
      activities: "Lead Chair @ ACM Student Chapter",
      courses: ["Distributed Systems", "Human-Computer Interaction", "Modern Web Architectures"],
    });

    // 3. Skills
    const seedSkills = [
      { name: "TypeScript", category: "Languages", proficiency: "Expert", yearsOfExperience: 4 },
      { name: "React 19 / Next.js", category: "Frameworks & Libraries", proficiency: "Expert", yearsOfExperience: 4 },
      { name: "Node.js & Express", category: "Frameworks & Libraries", proficiency: "Advanced", yearsOfExperience: 3 },
      { name: "Tailwind CSS", category: "Frameworks & Libraries", proficiency: "Expert", yearsOfExperience: 4 },
      { name: "PostgreSQL & Prisma", category: "Databases & Tools", proficiency: "Advanced", yearsOfExperience: 3 },
      { name: "AWS (ECS, Lambda, S3)", category: "Cloud & DevOps", proficiency: "Advanced", yearsOfExperience: 3 },
      { name: "Docker", category: "Cloud & DevOps", proficiency: "Intermediate", yearsOfExperience: 2 },
    ];
    for (const sk of seedSkills) {
      await addDoc(collection(db, "users", uid, "skills"), sk);
    }

    // 4. Projects
    await addDoc(collection(db, "users", uid, "projects"), {
      title: "ResumeIQ Career Intelligence Engine",
      role: "Lead Architect & UI Designer",
      startDate: "2025-01",
      endDate: "2025-04",
      description: "Multi-tenant career workspace and AI resume personalization platform with real-time ATS scoring.",
      highlights: [
        "Engineered responsive modular workspace using Next.js App Router, Tailwind CSS, and headless Radix UI components.",
        "Built client-side ATS tokenization matrix evaluating keyword semantic density against target job descriptions in <150ms.",
      ],
      techStack: ["Next.js", "TypeScript", "Tailwind CSS", "Recharts", "Zod"],
      liveUrl: "https://resumeiq.dev",
      repoUrl: "https://github.com/example/resumeiq",
    });

    // 5. Experience
    await addDoc(collection(db, "users", uid, "experience"), {
      company: "Apex Scale Technologies",
      role: "Senior Software Engineer — Frontend Systems",
      location: "San Francisco, CA",
      startDate: "2024-06",
      endDate: "Present",
      isCurrent: true,
      bullets: [
        "Spearheaded redesign of core analytics suite used by 180,000+ monthly active users, improving Core Web Vitals.",
        "Authored enterprise design system component library with 45+ accessible tokens.",
      ],
      technologies: ["Next.js", "TypeScript", "Tailwind CSS", "GraphQL"],
    });

    // 6. Certifications
    await addDoc(collection(db, "users", uid, "certifications"), {
      title: "AWS Certified Solutions Architect — Associate (SAA-C03)",
      issuer: "Amazon Web Services (AWS)",
      issueDate: "2024-04",
      expiryDate: "2027-04",
      credentialId: "AWS-SAA-8829104",
      credentialUrl: "https://aws.amazon.com/verification/AWS-SAA-8829104",
    });

    // 7. Achievements
    await addDoc(collection(db, "users", uid, "achievements"), {
      title: "1st Place Winner — Global AI Hackathon (Enterprise Track)",
      issuer: "TechCrunch Disrupt 2024",
      date: "2024-10",
      description: "Built an autonomous multi-agent code refactoring assistant within 48 hours.",
      url: "https://techcrunch.com/hackathon-winners-2024",
    });

    // 8. Default Tailored Resume
    await addDoc(collection(db, "users", uid, "resumes"), {
      title: "Senior Full Stack AI Engineer — Stripe Target",
      targetRole: "Senior Full Stack Engineer",
      targetCompany: "Stripe",
      template: "modern",
      lastEdited: new Date().toISOString().split("T")[0],
      score: 94,
      atsScore: 94,
      scoreBreakdown: { relevance: 96, keywords: 92, metrics: 95, formatting: 98 },
      tags: ["High Match", "Tailored", "Stripe"],
      sections: {
        summary:
          "Full-stack software engineer with 3+ years experience architecting high-throughput distributed systems, modern React/Next.js client applications, and LLM workflows.",
        experiences: [],
        projects: [],
        education: [],
        skills: [],
        certifications: [],
      },
    });

    // 9. Recommended Actions
    await addDoc(collection(db, "users", uid, "actions"), {
      title: "Quantify impact metric in Apex Scale Experience",
      category: "Experience",
      impact: "High",
      description: "Adding specific metrics (e.g. latency or velocity %) increases ATS relevance score.",
      actionUrl: "/workspace/experience",
    });
  };

  return (
    <CareerContext.Provider
      value={{
        profile,
        updateProfile,
        education,
        addEducation,
        updateEducation,
        deleteEducation,
        skills,
        addSkill,
        updateSkill,
        deleteSkill,
        projects,
        addProject,
        updateProject,
        deleteProject,
        experience,
        addExperience,
        updateExperience,
        deleteExperience,
        certifications,
        addCertification,
        updateCertification,
        deleteCertification,
        achievements,
        addAchievement,
        updateAchievement,
        deleteAchievement,
        documents,
        addDocument,
        deleteDocument,
        resumes,
        addResume,
        updateResume,
        deleteResume,
        duplicateResume,
        saveAtsAnalysis,
        actions,
        dismissAction,
        seedSampleData,
        isLoaded,
      }}
    >
      {children}
    </CareerContext.Provider>
  );
}

export function useCareer() {
  const context = useContext(CareerContext);
  if (!context) {
    throw new Error("useCareer must be used within a CareerProvider");
  }
  return context;
}
