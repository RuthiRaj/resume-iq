import { ResumeItem } from "./store";
import { ProfileData, EducationData, SkillData, ProjectData, ExperienceData, CertificationData } from "./validations";

/**
 * Parses raw Firestore REST JSON values into native JavaScript values.
 */
export function decodeFirestoreValue(val: any): any {
  if (!val || typeof val !== "object") return val;
  if ("stringValue" in val) return val.stringValue;
  if ("booleanValue" in val) return val.booleanValue;
  if ("integerValue" in val) return parseInt(val.integerValue, 10);
  if ("doubleValue" in val) return parseFloat(val.doubleValue);
  if ("timestampValue" in val) return val.timestampValue;
  if ("nullValue" in val) return null;
  if ("arrayValue" in val) {
    return (val.arrayValue.values || []).map(decodeFirestoreValue);
  }
  if ("mapValue" in val) {
    const res: Record<string, any> = {};
    const fields = val.mapValue.fields || {};
    for (const key of Object.keys(fields)) {
      res[key] = decodeFirestoreValue(fields[key]);
    }
    return res;
  }
  return val;
}

export function decodeFirestoreDocument(doc: any): Record<string, any> {
  if (!doc || !doc.fields) return {};
  const res: Record<string, any> = {};
  for (const key of Object.keys(doc.fields)) {
    res[key] = decodeFirestoreValue(doc.fields[key]);
  }
  // Include document ID from name if available
  if (doc.name) {
    const parts = doc.name.split("/");
    res.id = parts[parts.length - 1];
  }
  return res;
}

/**
 * Converts native JavaScript values into Firestore REST JSON typed fields.
 */
export function encodeFirestoreValue(val: any): any {
  if (val === null || val === undefined) return { nullValue: null };
  if (typeof val === "boolean") return { booleanValue: val };
  if (typeof val === "number") {
    if (Number.isInteger(val)) return { integerValue: val.toString() };
    return { doubleValue: val };
  }
  if (typeof val === "string") return { stringValue: val };
  if (Array.isArray(val)) {
    return {
      arrayValue: {
        values: val.map(encodeFirestoreValue),
      },
    };
  }
  if (typeof val === "object") {
    const fields: Record<string, any> = {};
    for (const key of Object.keys(val)) {
      fields[key] = encodeFirestoreValue(val[key]);
    }
    return { mapValue: { fields } };
  }
  return { stringValue: String(val) };
}

/**
 * Loads a user-owned resume from Firestore via REST API with the authenticated user's ID token.
 */
export async function loadUserResumeFromServer(
  uid: string,
  resumeId: string,
  idToken: string
): Promise<ResumeItem | null> {
  const projectId =
    process.env.FIREBASE_PROJECT_ID ||
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
    "resumeiq-3cfe6";

  const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users/${uid}/resumes/${resumeId}`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    const err = new Error(
      errorBody?.error?.message || `Failed to fetch resume from Firestore (${response.status})`
    );
    (err as any).statusCode = response.status === 403 ? 403 : 500;
    throw err;
  }

  const rawDoc = await response.json();
  const parsed = decodeFirestoreDocument(rawDoc);
  return {
    id: resumeId,
    ...parsed,
  } as ResumeItem;
}

/**
 * Loads the user's canonical Master Career Profile from Firestore.
 */
export async function loadMasterCareerProfileFromServer(
  uid: string,
  idToken: string
): Promise<{
  profile: Partial<ProfileData>;
  education: EducationData[];
  skills: SkillData[];
  projects: ProjectData[];
  experience: ExperienceData[];
  certifications: CertificationData[];
}> {
  const projectId =
    process.env.FIREBASE_PROJECT_ID ||
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
    "resumeiq-3cfe6";

  const fetchCollection = async (collectionName: string) => {
    const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users/${uid}/${collectionName}`;
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.documents || []).map(decodeFirestoreDocument);
  };

  const fetchDocument = async (subpath: string) => {
    const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users/${uid}/${subpath}`;
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    if (!res.ok) return {};
    const data = await res.json();
    return decodeFirestoreDocument(data);
  };

  const [profileDoc, experienceDocs, projectDocs, skillDocs, educationDocs, certDocs] =
    await Promise.all([
      fetchDocument("profile/main"),
      fetchCollection("experience"),
      fetchCollection("projects"),
      fetchCollection("skills"),
      fetchCollection("education"),
      fetchCollection("certifications"),
    ]);

  return {
    profile: profileDoc as Partial<ProfileData>,
    experience: experienceDocs as ExperienceData[],
    projects: projectDocs as ProjectData[],
    skills: skillDocs as SkillData[],
    education: educationDocs as EducationData[],
    certifications: certDocs as CertificationData[],
  };
}

/**
 * Persists the analysis result and metadata to the resume document in Firestore.
 */
export async function persistAnalysisResultToServer(
  uid: string,
  resumeId: string,
  idToken: string,
  analysisData: {
    atsScore: number;
    scoreBreakdown: any;
    summaryFeedback: string;
    matchingSkills: any[];
    missingSkills: any[];
    partialSkills: any[];
    metadata: any;
  }
): Promise<void> {
  const projectId =
    process.env.FIREBASE_PROJECT_ID ||
    process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
    "resumeiq-3cfe6";

  const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/users/${uid}/resumes/${resumeId}?updateMask.fieldPaths=score&updateMask.fieldPaths=atsScore&updateMask.fieldPaths=scoreBreakdown&updateMask.fieldPaths=lastAnalyzedAt&updateMask.fieldPaths=analysisResults&updateMask.fieldPaths=targetRole&updateMask.fieldPaths=targetCompany`;

  const fields = {
    score: encodeFirestoreValue(analysisData.atsScore),
    atsScore: encodeFirestoreValue(analysisData.atsScore),
    scoreBreakdown: encodeFirestoreValue(analysisData.scoreBreakdown),
    lastAnalyzedAt: encodeFirestoreValue(analysisData.metadata.analyzedAt),
    targetRole: encodeFirestoreValue(analysisData.metadata.targetRole),
    targetCompany: encodeFirestoreValue(analysisData.metadata.targetCompany || ""),
    analysisResults: encodeFirestoreValue({
      summaryFeedback: analysisData.summaryFeedback,
      matchingSkills: analysisData.matchingSkills,
      missingSkills: analysisData.missingSkills,
      partialSkills: analysisData.partialSkills,
      metadata: analysisData.metadata,
    }),
  };

  const response = await fetch(url, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ fields }),
  });

  if (!response.ok) {
    console.error("Failed to persist analysis to Firestore:", await response.text());
  }
}
