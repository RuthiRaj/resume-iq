"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useCareer } from "@/lib/store";
import { DocumentData } from "@/lib/validations";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ToastBanner } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import { formatDate } from "@/lib/utils";
import {
  Files,
  UploadCloud,
  FileText,
  Trash2,
  Eye,
  CheckCircle2,
  Sparkles,
  Loader2,
  AlertCircle,
  Edit3,
  Plus,
  X,
  Check,
  Building,
  GraduationCap,
  Wrench,
  FolderGit2,
  Award,
} from "lucide-react";

interface ParsedProfile {
  fullName: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: string;
  linkedin: string;
  github: string;
  summary: string;
  targetRoles: string[];
}

interface ExperienceItem {
  id?: string;
  role: string;
  company: string;
  location?: string;
  startDate?: string;
  endDate?: string;
  bullets: string[];
  technologies?: string[];
}

interface EducationItem {
  degree: string;
  institution: string;
  fieldOfStudy?: string;
}

interface SkillItem {
  name: string;
  category?: string;
  proficiency?: string;
}

interface ProjectItem {
  id?: string;
  title: string;
  role?: string;
  description?: string;
  highlights: string[];
  techStack?: string[];
}

interface CertificationItem {
  title: string;
  issuer?: string;
}

interface ParsedCandidateData {
  profile: ParsedProfile;
  evidence: {
    headline?: string;
    summary?: string;
    experience: ExperienceItem[];
    education: EducationItem[];
    skills: SkillItem[];
    projects: ProjectItem[];
    certifications: CertificationItem[];
  };
}

interface IngestionDraftState {
  ingestionId: string;
  documentName: string;
  fileSizeBytes: number;
  status: "Pending" | "Processing" | "Parsed" | "Completed" | "Failed";
  rawTextSnippet?: string;
  parsedData: ParsedCandidateData;
  fileUrl?: string;
}

type IngestionPhase =
  | "Idle"
  | "Uploading"
  | "Extracting"
  | "Parsing"
  | "ReadyForReview"
  | "Confirming"
  | "SuccessfullyImported"
  | "Failed";

export default function DocumentsPage() {
  const { user } = useAuth();
  const { documents, addDocument, deleteDocument, isLoaded } = useCareer();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentData | null>(null);
  const [itemToDelete, setItemToDelete] = useState<{ id: string; name: string } | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Ingestion upload states
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<DocumentData["type"]>("Resume");
  const [phase, setPhase] = useState<IngestionPhase>("Idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Review & Confirmation Draft State
  const [activeDraft, setActiveDraft] = useState<IngestionDraftState | null>(null);
  const [activeTab, setActiveTab] = useState<"profile" | "experience" | "education" | "skills" | "projects" | "certifications">("profile");

  const handleRealUpload = async () => {
    if (!uploadFile) {
      setErrorMessage("Please select a document file (.pdf, .docx, .doc, or .txt) to upload.");
      return;
    }

    setErrorMessage(null);
    setPhase("Uploading");
    setStatusMessage("Uploading binary payload to server...");

    try {
      const idToken = await user?.getIdToken();
      if (!idToken) {
        throw new Error("User session expired. Please re-authenticate.");
      }

      setPhase("Extracting");
      setStatusMessage("Extracting document text on backend server...");

      const formData = new FormData();
      formData.append("file", uploadFile);

      setPhase("Parsing");
      setStatusMessage("Parsing structured career evidence with AI...");

      const res = await fetch("/api/resumes/ingest", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${idToken}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.error || "Document ingestion failed.");
      }

      const data = await res.json();
      const draft: IngestionDraftState = data.draft;

      // Persist the document entry in local career context. This is
      // intentionally NOT awaited-and-thrown into the outer catch: it's a
      // secondary convenience record (so the doc shows in the library
      // list), not part of the core parsing result the user is waiting on.
      // A failure here must never make a successful AI parse look like a
      // failed upload.
      try {
        await addDocument(
          {
            name: draft.documentName,
            type: docType,
            fileSize: `${(draft.fileSizeBytes / 1024).toFixed(0)} KB`,
            uploadDate: new Date().toISOString().split("T")[0],
            parsedStatus: "Parsed",
            content: draft.rawTextSnippet || `Extracted text from ${draft.documentName}`,
          },
          draft.fileUrl
        );
      } catch (docErr) {
        console.warn("Document library record failed to save (parsing still succeeded):", docErr);
      }

      setActiveDraft(draft);
      setPhase("ReadyForReview");
      setIsUploadOpen(false);
      setUploadFile(null);
      showToast("Document uploaded successfully", "success");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to ingest document.");
      showToast(err.message || "Failed to upload document. Please try again.", "error");
      setPhase("Failed");
    }
  };

  const handleConfirmImport = async () => {
    if (!activeDraft) return;

    setPhase("Confirming");
    setStatusMessage("Persisting approved evidence to Master Workspace...");
    setErrorMessage(null);

    try {
      const idToken = await user?.getIdToken();
      if (!idToken) {
        throw new Error("User session expired. Please re-authenticate.");
      }

      const res = await fetch(`/api/resumes/ingest/${activeDraft.ingestionId}/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          parsedData: activeDraft.parsedData,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.error || "Master workspace hydration failed.");
      }

      setPhase("SuccessfullyImported");
      setStatusMessage("Career evidence successfully imported into master workspace!");
      showToast("Career evidence imported to master workspace", "success");
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to confirm ingestion import.");
      showToast(err.message || "Failed to confirm ingestion import.", "error");
      setPhase("ReadyForReview");
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification Banner */}
      {toast && (
        <ToastBanner message={toast.message} type={toast.type} />
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Original Documents & Transcripts</h2>
          <p className="text-small text-secondary">
            Upload raw PDF/DOCX resumes for server-side AI parsing and interactive workspace hydration.
          </p>
        </div>
        <Button onClick={() => { setIsUploadOpen(true); setPhase("Idle"); setErrorMessage(null); }} variant="primary" size="sm" className="gap-1.5 self-start">
          <UploadCloud className="h-4 w-4" />
          <span>Upload Document</span>
        </Button>
      </div>

      {documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          description="Upload an existing resume or academic transcript PDF to automatically extract and review your workspace data."
          actionLabel="Upload Document"
          onAction={() => { setIsUploadOpen(true); setPhase("Idle"); setErrorMessage(null); }}
          icon={Files}
        />
      ) : (
        <div className="space-y-3">
          {documents.map((doc) => (
            <Card key={doc.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-body font-semibold text-primary">{doc.name}</h4>
                      <Badge variant="outline">{doc.type}</Badge>
                      <Badge
                        variant={
                          doc.parsedStatus === "Parsed"
                            ? "success"
                            : doc.parsedStatus === "Processing"
                            ? "warning"
                            : "default"
                        }
                      >
                        {doc.parsedStatus}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-small text-muted">
                      <span>Size: {doc.fileSize}</span>
                      <span>&bull;</span>
                      <span>Uploaded {formatDate(doc.uploadDate)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center">
                  <Button
                    onClick={() => setSelectedDoc(doc)}
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                  >
                    <Eye className="h-3.5 w-3.5" />
                    <span>Preview Snippet</span>
                  </Button>
                  <Button
                    onClick={() =>
                      doc.id &&
                      setItemToDelete({
                        id: doc.id,
                        name: doc.name,
                      })
                    }
                    variant="ghost"
                    size="sm"
                    className="text-status-error hover:bg-status-error-soft"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => phase === "Idle" && setIsUploadOpen(false)}
        title="Upload Resume Document"
        description="Upload a PDF, DOCX, or TXT file for server-side parsing into reviewable draft data."
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Document Type</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentData["type"])}
              className="flex h-9 w-full rounded-input border border-border bg-surface px-3 py-1.5 text-body text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              <option value="Resume">Resume / CV</option>
              <option value="Transcript">Official Academic Transcript</option>
              <option value="Certificate">Certificate of Completion</option>
              <option value="Other">Other Document</option>
            </select>
          </div>

          <div
            className="flex flex-col items-center justify-center rounded-card border-2 border-dashed border-border bg-page p-8 text-center hover:border-accent/40 cursor-pointer transition-colors"
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <UploadCloud className="h-8 w-8 text-accent mb-2" />
            <p className="text-body font-medium text-primary">
              {uploadFile ? uploadFile.name : "Click to select or drop resume PDF/DOCX here"}
            </p>
            <p className="text-small text-muted mt-1">Supports PDF, DOCX, TXT up to 15MB</p>
            <input
              id="file-input"
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setUploadFile(e.target.files[0]);
                }
              }}
            />
          </div>

          {errorMessage && (
            <div className="flex items-center gap-2 rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {["Uploading", "Extracting", "Parsing"].includes(phase) && (
            <div className="space-y-2 rounded-btn border border-accent/20 bg-accent-soft p-4">
              <div className="flex items-center justify-between text-small font-medium text-accent">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{statusMessage}</span>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button
              type="button"
              variant="ghost"
              disabled={["Uploading", "Extracting", "Parsing"].includes(phase)}
              onClick={() => {
                setIsUploadOpen(false);
                setErrorMessage(null);
                setPhase("Idle");
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={["Uploading", "Extracting", "Parsing"].includes(phase) || !uploadFile}
              onClick={handleRealUpload}
              className="gap-1.5"
            >
              <Sparkles className="h-4 w-4" />
              <span>{["Uploading", "Extracting", "Parsing"].includes(phase) ? "Ingesting..." : "Upload & Parse"}</span>
            </Button>
          </div>
        </div>
      </Modal>

      {/* Interactive Review & Confirmation Modal */}
      {activeDraft && (
        <Modal
          isOpen={true}
          onClose={() => { if (phase !== "Confirming") setActiveDraft(null); }}
          title="Review Extracted Resume Evidence"
          description="Review and edit extracted information before importing it into your canonical Master Workspace."
          maxWidth="4xl"
        >
          <div className="space-y-5">
            <div className="flex items-center gap-2 rounded-btn border border-accent/30 bg-accent-soft p-3 text-accent text-small">
              <Sparkles className="h-4 w-4 shrink-0" />
              <span>
                <strong>Staging Area:</strong> AI-parsed resume data is not yet in your master workspace. Review and edit fields below before clicking Confirm.
              </span>
            </div>

            {/* Navigation tabs */}
            <div className="flex items-center gap-1.5 border-b border-border pb-2 overflow-x-auto">
              <Button
                variant={activeTab === "profile" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("profile")}
                className="gap-1.5 text-small"
              >
                <span>Profile</span>
              </Button>
              <Button
                variant={activeTab === "experience" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("experience")}
                className="gap-1.5 text-small"
              >
                <Building className="h-3.5 w-3.5" />
                <span>Experience ({(activeDraft.parsedData?.evidence?.experience || []).length})</span>
              </Button>
              <Button
                variant={activeTab === "education" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("education")}
                className="gap-1.5 text-small"
              >
                <GraduationCap className="h-3.5 w-3.5" />
                <span>Education ({(activeDraft.parsedData?.evidence?.education || []).length})</span>
              </Button>
              <Button
                variant={activeTab === "skills" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("skills")}
                className="gap-1.5 text-small"
              >
                <Wrench className="h-3.5 w-3.5" />
                <span>Skills ({(activeDraft.parsedData?.evidence?.skills || []).length})</span>
              </Button>
              <Button
                variant={activeTab === "projects" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("projects")}
                className="gap-1.5 text-small"
              >
                <FolderGit2 className="h-3.5 w-3.5" />
                <span>Projects ({(activeDraft.parsedData?.evidence?.projects || []).length})</span>
              </Button>
              <Button
                variant={activeTab === "certifications" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("certifications")}
                className="gap-1.5 text-small"
              >
                <Award className="h-3.5 w-3.5" />
                <span>Certs ({(activeDraft.parsedData?.evidence?.certifications || []).length})</span>
              </Button>
            </div>

            {/* Tab 1: Profile */}
            {activeTab === "profile" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-small font-medium text-primary">Full Name</label>
                  <Input
                    value={activeDraft.parsedData.profile.fullName}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, fullName: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-small font-medium text-primary">Headline</label>
                  <Input
                    value={activeDraft.parsedData.profile.headline}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, headline: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-small font-medium text-primary">Email</label>
                  <Input
                    value={activeDraft.parsedData.profile.email}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, email: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-small font-medium text-primary">Phone</label>
                  <Input
                    value={activeDraft.parsedData.profile.phone}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, phone: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-small font-medium text-primary">Location</label>
                  <Input
                    value={activeDraft.parsedData.profile.location}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, location: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-small font-medium text-primary">Personal Website</label>
                  <Input
                    value={activeDraft.parsedData.profile.website}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, website: e.target.value },
                        },
                      })
                    }
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-small font-medium text-primary">Professional Summary</label>
                  <Textarea
                    rows={3}
                    value={activeDraft.parsedData.profile.summary}
                    onChange={(e) =>
                      setActiveDraft({
                        ...activeDraft,
                        parsedData: {
                          ...activeDraft.parsedData,
                          profile: { ...activeDraft.parsedData.profile, summary: e.target.value },
                        },
                      })
                    }
                  />
                </div>
              </div>
            )}

            {/* Tab 2: Experience */}
            {activeTab === "experience" && (
              <div className="space-y-4 max-h-[380px] overflow-y-auto pr-1">
                {activeDraft.parsedData.evidence.experience.map((exp, idx) => (
                  <Card key={idx} className="p-3 border border-border">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-primary">Experience #{idx + 1}</h4>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-error"
                        onClick={() => {
                          const updated = [...activeDraft.parsedData.evidence.experience];
                          updated.splice(idx, 1);
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, experience: updated },
                            },
                          });
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-small">
                      <Input
                        placeholder="Company"
                        value={exp.company}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.experience];
                          updated[idx].company = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, experience: updated },
                            },
                          });
                        }}
                      />
                      <Input
                        placeholder="Role / Title"
                        value={exp.role}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.experience];
                          updated[idx].role = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, experience: updated },
                            },
                          });
                        }}
                      />
                    </div>
                  </Card>
                ))}

                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5"
                  onClick={() => {
                    const updated = [
                      ...activeDraft.parsedData.evidence.experience,
                      { role: "", company: "", bullets: [] },
                    ];
                    setActiveDraft({
                      ...activeDraft,
                      parsedData: {
                        ...activeDraft.parsedData,
                        evidence: { ...activeDraft.parsedData.evidence, experience: updated },
                      },
                    });
                  }}
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add Experience Item</span>
                </Button>
              </div>
            )}

            {/* Tab 3: Education */}
            {activeTab === "education" && (
              <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                {activeDraft.parsedData.evidence.education.map((edu, idx) => (
                  <Card key={idx} className="p-3 border border-border">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-primary">Education #{idx + 1}</h4>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-error"
                        onClick={() => {
                          const updated = [...activeDraft.parsedData.evidence.education];
                          updated.splice(idx, 1);
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, education: updated },
                            },
                          });
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-small">
                      <Input
                        placeholder="Institution"
                        value={edu.institution}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.education];
                          updated[idx].institution = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, education: updated },
                            },
                          });
                        }}
                      />
                      <Input
                        placeholder="Degree"
                        value={edu.degree}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.education];
                          updated[idx].degree = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, education: updated },
                            },
                          });
                        }}
                      />
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Tab 4: Skills */}
            {activeTab === "skills" && (
              <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                <div className="flex flex-wrap gap-2">
                  {activeDraft.parsedData.evidence.skills.map((sk, idx) => (
                    <div key={idx} className="flex items-center gap-1 bg-surface border border-border rounded-full px-3 py-1 text-small">
                      <span>{sk.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          const updated = [...activeDraft.parsedData.evidence.skills];
                          updated.splice(idx, 1);
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, skills: updated },
                            },
                          });
                        }}
                        className="text-muted hover:text-status-error ml-1"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tab 5: Projects */}
            {activeTab === "projects" && (
              <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                {activeDraft.parsedData.evidence.projects.map((proj, idx) => (
                  <Card key={idx} className="p-3 border border-border">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-primary">{proj.title || `Project #${idx + 1}`}</h4>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-error"
                        onClick={() => {
                          const updated = [...activeDraft.parsedData.evidence.projects];
                          updated.splice(idx, 1);
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, projects: updated },
                            },
                          });
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <Input
                      placeholder="Project Title"
                      value={proj.title}
                      onChange={(e) => {
                        const updated = [...activeDraft.parsedData.evidence.projects];
                        updated[idx].title = e.target.value;
                        setActiveDraft({
                          ...activeDraft,
                          parsedData: {
                            ...activeDraft.parsedData,
                            evidence: { ...activeDraft.parsedData.evidence, projects: updated },
                          },
                        });
                      }}
                    />
                  </Card>
                ))}
              </div>
            )}

            {/* Tab 6: Certifications */}
            {activeTab === "certifications" && (
              <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                {activeDraft.parsedData.evidence.certifications.map((cert, idx) => (
                  <Card key={idx} className="p-3 border border-border">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-semibold text-primary">{cert.title || `Certification #${idx + 1}`}</h4>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-status-error"
                        onClick={() => {
                          const updated = [...activeDraft.parsedData.evidence.certifications];
                          updated.splice(idx, 1);
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, certifications: updated },
                            },
                          });
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-small">
                      <Input
                        placeholder="Certification Title"
                        value={cert.title}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.certifications];
                          updated[idx].title = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, certifications: updated },
                            },
                          });
                        }}
                      />
                      <Input
                        placeholder="Issuer Organization"
                        value={cert.issuer || ""}
                        onChange={(e) => {
                          const updated = [...activeDraft.parsedData.evidence.certifications];
                          updated[idx].issuer = e.target.value;
                          setActiveDraft({
                            ...activeDraft,
                            parsedData: {
                              ...activeDraft.parsedData,
                              evidence: { ...activeDraft.parsedData.evidence, certifications: updated },
                            },
                          });
                        }}
                      />
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {errorMessage && (
              <div className="flex items-center gap-2 rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {phase === "SuccessfullyImported" ? (
              <div className="space-y-4 pt-2">
                <div className="flex items-center gap-3 rounded-btn border border-status-success/30 bg-status-success-soft p-4 text-status-success text-small font-medium">
                  <CheckCircle2 className="h-5 w-5 shrink-0" />
                  <div>
                    <p className="font-semibold text-body">Import Successful!</p>
                    <p className="text-caption text-secondary">Career evidence and profile details have been hydrated into your Master Workspace.</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-border/60">
                  <Link href="/workspace/experience">
                    <Button type="button" variant="outline" className="gap-1.5">
                      <FileText className="h-4 w-4" />
                      <span>View Master Workspace</span>
                    </Button>
                  </Link>
                  <Link href="/analyzer">
                    <Button type="button" variant="primary" className="gap-1.5 shadow-subtle">
                      <Sparkles className="h-4 w-4" />
                      <span>Run ATS Audit</span>
                    </Button>
                  </Link>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setActiveDraft(null);
                      setPhase("Idle");
                    }}
                  >
                    Close
                  </Button>
                </div>
              </div>
            ) : (
              /* Modal actions */
              <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
                <Button
                  type="button"
                  variant="ghost"
                  disabled={phase === "Confirming"}
                  onClick={() => setActiveDraft(null)}
                >
                  Discard Draft
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  disabled={phase === "Confirming"}
                  onClick={handleConfirmImport}
                  className="gap-1.5"
                >
                  {phase === "Confirming" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Importing...</span>
                    </>
                  ) : (
                    <>
                      <Check className="h-4 w-4" />
                      <span>Confirm & Import to Master Workspace</span>
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Snippet Preview Modal */}
      {selectedDoc && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedDoc(null)}
          title={`Document: ${selectedDoc.name}`}
          description={`Uploaded on ${selectedDoc.uploadDate} • Status: ${selectedDoc.parsedStatus}`}
          maxWidth="3xl"
        >
          <div className="space-y-4">
            <div className="rounded-btn border border-border bg-page p-6 font-mono text-small text-secondary space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-3 text-primary font-semibold">
                <span>DOCUMENT PREVIEW & EXTRACTION BUFFER</span>
                <Badge variant="success">Parsed 100%</Badge>
              </div>

              <div className="space-y-2 text-primary">
                <p className="font-semibold text-body">{selectedDoc.name}</p>
                <p className="text-secondary">
                  Type: {selectedDoc.type} • Size: {selectedDoc.fileSize}
                </p>
                <div className="text-secondary whitespace-pre-wrap pt-2 font-sans text-small leading-relaxed">
                  {selectedDoc.content || "Document parsed and indexed into master workspace."}
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={() => setSelectedDoc(null)} variant="primary">
                Close Preview
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation Modal */}
      <ConfirmDeleteModal
        isOpen={Boolean(itemToDelete)}
        onClose={() => setItemToDelete(null)}
        onConfirm={async () => {
          if (!itemToDelete) return;
          try {
            await deleteDocument(itemToDelete.id);
            showToast("Document deleted successfully", "success");
          } catch (err: any) {
            showToast("Failed to delete document. Please try again.", "error");
          } finally {
            setItemToDelete(null);
          }
        }}
        title="Delete Document"
        description="Are you sure you want to delete this document from your workspace? Extracted workspace records will not be removed."
        itemName={itemToDelete?.name}
      />
    </div>
  );
}
