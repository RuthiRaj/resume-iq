"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from "react";
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

export interface EvidenceDimensionsData {
  relevantContext: boolean;
  productionContext: boolean;
  quantifiableImpact: boolean;
  meetsExperienceYears: boolean;
  explicitTechnology: boolean;
}

export interface RequirementMatchData {
  requirementName: string;
  category: string;
  importance: "MustHave" | "Preferred" | "Unspecified";
  matchStatus: "StrongMatch" | "PartialMatch" | "Missing";
  resumeEvidence?: string;
  jobSourceEvidence?: string;
  evidenceSourceSection?: "Experience" | "Project" | "SkillTag" | "Education" | "Certification" | "Summary" | "None";
  evidenceDimensions?: EvidenceDimensionsData;
  matchReason?: string;
  gapReason?: string;
  gapType?: string;
  confidence: "High" | "Medium" | "Low";
}

export interface UnsupportedClaimData {
  category: string;
  claimText: string;
  reason: string;
  promptForUser: string;
}

export interface ValidationResultData {
  isValid: boolean;
  status: "Draft" | "Validated" | "RequiresCandidateInput" | "UserEdited" | "UserApproved" | "Applied" | "ReAnalyzed";
  unsupportedClaims?: UnsupportedClaimData[];
  sanitizedBullet?: string;
}

export interface RemediationSuggestionData {
  id: string;
  requirementName: string;
  importance: "MustHave" | "Preferred" | "Unspecified";
  gapType: string;
  eligibility: "Remediable" | "RequiresCandidateFacts" | "PartiallyRemediable" | "NotRemediable";
  actionType: "ImproveExistingBullet" | "PromptForMissingFacts" | "AddProjectContext" | "ClarifyAdjacentTechnology" | "ExplainHardGap" | "None";
  targetSection: "Experience" | "Project" | "SkillTag" | "Education" | "Certification" | "Summary" | "None";
  sourceEvidenceId: string;
  originalEvidence?: string;
  targetExperienceId?: string;
  targetBulletIndex?: number;
  suggestedBullet?: string;
  missingFactPrompt?: string;
  guidance: string;
  potentialImpact: "High" | "Medium" | "Low";
  status: "Draft" | "Validated" | "RequiresCandidateInput" | "UserEdited" | "UserApproved" | "Applied" | "ReAnalyzed";
  validation?: ValidationResultData;
}

export interface AnalysisResultData {
  summaryFeedback: string;
  matchingSkills: Array<{ name: string; context: string }>;
  missingSkills: Array<{ name: string; priority: "High" | "Medium" | "Low"; reason: string }>;
  partialSkills: Array<{ name: string; note: string }>;
  jobIntelligence?: any;
  requirementMatches?: RequirementMatchData[];
  remediationSuggestions?: RemediationSuggestionData[];
  metadata?: {
    provider: string;
    model: string;
    analyzedAt: string;
    jobDescriptionHash?: string;
    targetRole?: string;
    targetCompany?: string;
  };
}

export interface ChangeRecordData {
  id: string;
  remediationId?: string;
  remediation_id?: string;
  actionType: "ApplyRemediation" | "DirectEdit" | "RevertChange" | "CandidateFactAddition";
  action_type?: "ApplyRemediation" | "DirectEdit" | "RevertChange" | "CandidateFactAddition";
  requirementName: string;
  requirement_name?: string;
  section: "Experience" | "Project" | "SkillTag" | "Education" | "Certification" | "Summary" | "None";
  targetItemId: string;
  target_item_id?: string;
  targetBulletIndex?: number;
  target_bullet_index?: number;
  originalText?: string;
  original_text?: string;
  proposedText?: string;
  proposed_text?: string;
  approvedText: string;
  approved_text?: string;
  status: "Draft" | "Approved" | "Applied" | "Reverted";
  versionIntroduced: number;
  version_introduced?: number;
  versionReverted?: number;
  version_reverted?: number;
  appliedAt: string;
  applied_at?: string;
  revertedAt?: string;
  reverted_at?: string;
  revertedChangeId?: string;
  reverted_change_id?: string;
}

export interface RequirementProgressionData {
  requirementName: string;
  requirement_name?: string;
  category: string;
  importance: "MustHave" | "Preferred" | "Unspecified";
  baselineStatus: "StrongMatch" | "PartialMatch" | "Missing";
  baseline_status?: "StrongMatch" | "PartialMatch" | "Missing";
  currentStatus: "StrongMatch" | "PartialMatch" | "Missing";
  current_status?: "StrongMatch" | "PartialMatch" | "Missing";
  progression: "Resolved" | "Improved" | "Unchanged" | "UnresolvedHardGap";
  verifiedEvidence?: string;
  verified_evidence?: string;
}

export interface FitComparisonData {
  variantId: string;
  variant_id?: string;
  targetRole: string;
  target_role?: string;
  targetCompany?: string;
  target_company?: string;
  baselineScore: number;
  baseline_score?: number;
  currentScore: number;
  current_score?: number;
  scoreDelta: number;
  score_delta?: number;
  baselineBreakdown: { relevance: number; keywords: number; metrics: number; formatting: number };
  baseline_breakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  currentBreakdown: { relevance: number; keywords: number; metrics: number; formatting: number };
  current_breakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  requirementProgressions: RequirementProgressionData[];
  requirement_progressions?: RequirementProgressionData[];
  totalGapsResolved: number;
  total_gaps_resolved?: number;
  totalGapsRemaining: number;
  total_gaps_remaining?: number;
}

export interface CandidateEvidenceData {
  headline?: string;
  summary?: string;
  experience?: Array<{
    role: string;
    company: string;
    location?: string;
    startDate?: string;
    endDate?: string;
    isCurrent?: boolean;
    bullets: string[];
    technologies?: string[];
  }>;
  projects?: Array<{
    title: string;
    role?: string;
    startDate?: string;
    endDate?: string;
    description?: string;
    highlights: string[];
    techStack?: string[];
    liveUrl?: string;
    repoUrl?: string;
  }>;
  skills?: Array<{
    name: string;
    category?: string;
    proficiency?: string;
    yearsOfExperience?: number;
  }>;
  education?: Array<{
    institution: string;
    degree?: string;
    fieldOfStudy?: string;
    startDate?: string;
    endDate?: string;
    grade?: string;
    activities?: string;
    courses?: string[];
  }>;
  certifications?: Array<{
    title: string;
    issuer?: string;
    issueDate?: string;
    expiryDate?: string;
    credentialId?: string;
    credentialUrl?: string;
  }>;
}

export interface TargetedResumeVariant {
  variantId: string;
  variant_id?: string;
  masterResumeId: string;
  master_resume_id?: string;
  title: string;
  targetRole: string;
  target_role?: string;
  targetCompany?: string;
  target_company?: string;
  jobDescriptionHash?: string;
  job_description_hash?: string;
  version: number;
  isTargetedVariant?: boolean;
  is_targeted_variant?: boolean;
  baselineScore?: number;
  baseline_score?: number;
  baselineBreakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  baseline_breakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  baselineMatches?: RequirementMatchData[];
  baseline_matches?: RequirementMatchData[];
  currentScore?: number;
  current_score?: number;
  currentBreakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  current_breakdown?: { relevance: number; keywords: number; metrics: number; formatting: number };
  currentMatches?: RequirementMatchData[];
  current_matches?: RequirementMatchData[];
  scoreDelta?: number;
  score_delta?: number;
  snapshot: CandidateEvidenceData;
  changeLedger?: ChangeRecordData[];
  change_ledger?: ChangeRecordData[];
  createdAt?: string;
  created_at?: string;
  updatedAt?: string;
  updated_at?: string;
}

export type ChangeRecord = ChangeRecordData;
export type RequirementProgression = RequirementProgressionData;
export type FitComparisonResponse = FitComparisonData;

export interface ExportTargetedResumeResponse {
  variantId: string;
  variant_id?: string;
  title: string;
  targetRole: string;
  target_role?: string;
  targetCompany?: string;
  target_company?: string;
  version: number;
  format: string;
  content: string;
  exportedAt: string;
  exported_at?: string;
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
  isTargetedVariant?: boolean;
  masterResumeId?: string;
  jobDescriptionHash?: string;
  version?: number;
  baselineScore?: number;
  currentScore?: number;
  scoreDelta?: number;
  changeLedger?: ChangeRecordData[];
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

function isCollectionEqual<T>(a: T, b: T): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return JSON.stringify(a) === JSON.stringify(b);
}

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

  // Keep refs for callbacks needing fresh state without re-creating identity
  const resumesRef = useRef<ResumeItem[]>(resumes);
  useEffect(() => {
    resumesRef.current = resumes;
  }, [resumes]);

  const profileRef = useRef<ProfileData>(profile);
  useEffect(() => {
    profileRef.current = profile;
  }, [profile]);

  const userRef = useRef(user);
  useEffect(() => {
    userRef.current = user;
  }, [user]);

  // Set up real-time Firestore listeners scoped strictly to user.uid
  useEffect(() => {
    const uid = user?.uid;
    if (!uid) {
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

    // Track initial load of all 10 collections before marking loaded
    const initialLoadedSet = new Set<string>();
    const markLoaded = (name: string) => {
      initialLoadedSet.add(name);
      if (initialLoadedSet.size >= 10) {
        setIsLoaded(true);
      }
    };

    // 1. Profile listener
    const unsubProfile = onSnapshot(doc(db, "users", uid, "profile", "main"), (snap) => {
      if (snap.exists()) {
        const data = snap.data() as ProfileData;
        setProfile((prev) => (isCollectionEqual(prev, data) ? prev : data));
      } else {
        const fallback: ProfileData = {
          ...defaultEmptyProfile,
          email: userRef.current?.email || "",
          fullName: userRef.current?.displayName || "",
        };
        setProfile((prev) => (isCollectionEqual(prev, fallback) ? prev : fallback));
      }
      markLoaded("profile");
    });

    // 2. Education listener
    const unsubEducation = onSnapshot(collection(db, "users", uid, "education"), (snap) => {
      const list: EducationData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as EducationData));
      setEducation((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("education");
    });

    // 3. Skills listener
    const unsubSkills = onSnapshot(collection(db, "users", uid, "skills"), (snap) => {
      const list: SkillData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as SkillData));
      setSkills((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("skills");
    });

    // 4. Projects listener
    const unsubProjects = onSnapshot(collection(db, "users", uid, "projects"), (snap) => {
      const list: ProjectData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ProjectData));
      setProjects((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("projects");
    });

    // 5. Experience listener
    const unsubExperience = onSnapshot(collection(db, "users", uid, "experience"), (snap) => {
      const list: ExperienceData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ExperienceData));
      setExperience((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("experience");
    });

    // 6. Certifications listener
    const unsubCertifications = onSnapshot(collection(db, "users", uid, "certifications"), (snap) => {
      const list: CertificationData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as CertificationData));
      setCertifications((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("certifications");
    });

    // 7. Achievements listener
    const unsubAchievements = onSnapshot(collection(db, "users", uid, "achievements"), (snap) => {
      const list: AchievementData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as AchievementData));
      setAchievements((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("achievements");
    });

    // 8. Documents listener
    const unsubDocuments = onSnapshot(collection(db, "users", uid, "documents"), (snap) => {
      const list: DocumentData[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as DocumentData));
      setDocuments((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("documents");
    });

    // 9. Resumes listener
    const unsubResumes = onSnapshot(collection(db, "users", uid, "resumes"), (snap) => {
      const list: ResumeItem[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as ResumeItem));
      setResumes((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("resumes");
    });

    // 10. Actions listener
    const unsubActions = onSnapshot(collection(db, "users", uid, "actions"), (snap) => {
      const list: RecommendedAction[] = [];
      snap.forEach((d) => list.push({ id: d.id, ...d.data() } as RecommendedAction));
      setActions((prev) => (isCollectionEqual(prev, list) ? prev : list));
      markLoaded("actions");
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
  }, [user?.uid]);

  // Profile persistence via backend API proxy
  const updateProfile = useCallback(
    async (data: ProfileData) => {
      const user = userRef.current;
      if (!user) return;
      const idToken = await user.getIdToken();
      const res = await fetch("/api/profile", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Failed to update profile.");
      }

      setProfile(data);
    },
    []
  );

  const addEducation = useCallback(
    async (data: Omit<EducationData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "education"), data);
    },
    []
  );

  const updateEducation = useCallback(
    async (id: string, data: Partial<EducationData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "education", id), data);
    },
    []
  );

  const deleteEducation = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "education", id));
    },
    []
  );

  const addSkill = useCallback(
    async (data: Omit<SkillData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "skills"), data);
    },
    []
  );

  const updateSkill = useCallback(
    async (id: string, data: Partial<SkillData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "skills", id), data);
    },
    []
  );

  const deleteSkill = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "skills", id));
    },
    []
  );

  const addProject = useCallback(
    async (data: Omit<ProjectData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "projects"), data);
    },
    []
  );

  const updateProject = useCallback(
    async (id: string, data: Partial<ProjectData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "projects", id), data);
    },
    []
  );

  const deleteProject = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "projects", id));
    },
    []
  );

  const addExperience = useCallback(
    async (data: Omit<ExperienceData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "experience"), data);
    },
    []
  );

  const updateExperience = useCallback(
    async (id: string, data: Partial<ExperienceData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "experience", id), data);
    },
    []
  );

  const deleteExperience = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "experience", id));
    },
    []
  );

  const addCertification = useCallback(
    async (data: Omit<CertificationData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "certifications"), data);
    },
    []
  );

  const updateCertification = useCallback(
    async (id: string, data: Partial<CertificationData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "certifications", id), data);
    },
    []
  );

  const deleteCertification = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "certifications", id));
    },
    []
  );

  const addAchievement = useCallback(
    async (data: Omit<AchievementData, "id">) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await addDoc(collection(db, "users", uid, "achievements"), data);
    },
    []
  );

  const updateAchievement = useCallback(
    async (id: string, data: Partial<AchievementData>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "achievements", id), data);
    },
    []
  );

  const deleteAchievement = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "achievements", id));
    },
    []
  );

  const addDocument = useCallback(
    async (data: Omit<DocumentData, "id">, file?: File) => {
      const currentUser = userRef.current;
      if (!currentUser?.uid) return;
      let fileUrl = "";
      let storagePath = "";

      if (file) {
        const sanitizedName = `${Date.now()}_${file.name.replace(/[^a-zA-Z0-9.-]/g, "_")}`;
        storagePath = `users/${currentUser.uid}/documents/${sanitizedName}`;
        const fileRef = ref(storage, storagePath);
        await uploadBytesResumable(fileRef, file);
        try {
          fileUrl = await getDownloadURL(fileRef);
        } catch {
          // Storage URL placeholder if storage is still initializing
          fileUrl = "";
        }
      }

      await addDoc(collection(db, "users", currentUser.uid, "documents"), {
        ...data,
        fileUrl,
        storagePath,
        createdAt: new Date().toISOString(),
      });
    },
    []
  );

  const deleteDocument = useCallback(
    async (id: string, storagePath?: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      if (storagePath) {
        try {
          const fileRef = ref(storage, storagePath);
          await deleteObject(fileRef);
        } catch {
          // ignore storage deletion errors
        }
      }
      await deleteDoc(doc(db, "users", uid, "documents", id));
    },
    []
  );

  const addResume = useCallback(
    async (resume: Omit<ResumeItem, "id">): Promise<string> => {
      const uid = userRef.current?.uid;
      if (!uid) throw new Error("Unauthenticated");
      const docRef = await addDoc(collection(db, "users", uid, "resumes"), {
        ...resume,
        createdAt: new Date().toISOString(),
      });
      return docRef.id;
    },
    []
  );

  const updateResume = useCallback(
    async (id: string, data: Partial<ResumeItem>) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "resumes", id), {
        ...data,
        lastEdited: new Date().toISOString().split("T")[0],
      });
    },
    []
  );

  const deleteResume = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "resumes", id));
    },
    []
  );

  const duplicateResume = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      const source = resumesRef.current.find((r) => r.id === id);
      if (!source) return;
      const { id: _, ...rest } = source;
      await addDoc(collection(db, "users", uid, "resumes"), {
        ...rest,
        title: `${source.title} (Copy)`,
        lastEdited: new Date().toISOString().split("T")[0],
      });
    },
    []
  );

  const saveAtsAnalysis = useCallback(
    async (
      resumeId: string,
      analysis: {
        atsScore: number;
        scoreBreakdown: { relevance: number; keywords: number; metrics: number; formatting: number };
        targetRole?: string;
        targetCompany?: string;
        analysisResults?: AnalysisResultData;
      }
    ) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await updateDoc(doc(db, "users", uid, "resumes", resumeId), {
        score: analysis.atsScore,
        atsScore: analysis.atsScore,
        scoreBreakdown: analysis.scoreBreakdown,
        lastAnalyzedAt: new Date().toISOString(),
        ...(analysis.targetRole ? { targetRole: analysis.targetRole } : {}),
        ...(analysis.targetCompany ? { targetCompany: analysis.targetCompany } : {}),
        ...(analysis.analysisResults ? { analysisResults: analysis.analysisResults } : {}),
      });
    },
    []
  );

  const dismissAction = useCallback(
    async (id: string) => {
      const uid = userRef.current?.uid;
      if (!uid) return;
      await deleteDoc(doc(db, "users", uid, "actions", id));
    },
    []
  );

  // Seed sample data explicitly on demand for demos/testing
  const seedSampleData = useCallback(async () => {
    const currentUser = userRef.current;
    if (!currentUser?.uid) return;
    const uid = currentUser.uid;

    // 1. Profile
    await setDoc(
      doc(db, "users", uid, "profile", "main"),
      {
        fullName: profileRef.current.fullName || currentUser.displayName || "Alex Morgan",
        headline: "Full Stack Engineer & AI Systems Specialist",
        email: currentUser.email || "alex.morgan@example.com",
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
  }, []);

  const value = useMemo<CareerContextType>(
    () => ({
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
    }),
    [
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
    ]
  );

  return (
    <CareerContext.Provider value={value}>
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
