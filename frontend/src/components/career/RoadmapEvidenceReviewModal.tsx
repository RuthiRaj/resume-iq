"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  FolderGit2,
  Wrench,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Check,
  Plus,
  Trash2,
  X,
  FileText,
  Layers,
  ArrowRight,
} from "lucide-react";

export interface RoadmapPromotionDraft {
  ingestionId: string;
  documentName: string;
  documentType: string;
  status: "Pending" | "Processing" | "Parsed" | "Completed" | "Failed";
  fileSizeBytes: number;
  parsedData: {
    profile?: {
      fullName?: string;
      headline?: string;
      email?: string;
      phone?: string;
      location?: string;
      website?: string;
      linkedin?: string;
      github?: string;
      summary?: string;
      targetRoles?: string[];
    };
    evidence: {
      projects: Array<{
        id?: string;
        title: string;
        role?: string;
        description?: string;
        highlights: string[];
        techStack?: string[];
      }>;
      skills: Array<{
        name: string;
        category?: string;
        proficiency?: string;
      }>;
      experience?: any[];
      education?: any[];
      certifications?: any[];
    };
  };
  fileUrl?: string;
}

interface RoadmapEvidenceReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  draft: RoadmapPromotionDraft;
  milestoneTitle: string;
  onConfirmSuccess?: () => void;
}

export function RoadmapEvidenceReviewModal({
  isOpen,
  onClose,
  draft,
  milestoneTitle,
  onConfirmSuccess,
}: RoadmapEvidenceReviewModalProps) {
  const { user } = useAuth();
  const [activeDraft, setActiveDraft] = useState<RoadmapPromotionDraft>(draft);
  const [activeTab, setActiveTab] = useState<"project" | "skills">("project");
  const [isConfirming, setIsConfirming] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [newHighlight, setNewHighlight] = useState("");
  const [newSkill, setNewSkill] = useState("");

  const project = activeDraft.parsedData.evidence.projects[0] || {
    title: milestoneTitle,
    description: "",
    highlights: [],
    techStack: [],
  };

  const handleUpdateProject = (field: string, value: any) => {
    const updatedProjects = [...activeDraft.parsedData.evidence.projects];
    if (updatedProjects.length === 0) {
      updatedProjects.push({
        title: milestoneTitle,
        description: "",
        highlights: [],
        techStack: [],
        [field]: value,
      });
    } else {
      updatedProjects[0] = { ...updatedProjects[0], [field]: value };
    }

    setActiveDraft({
      ...activeDraft,
      parsedData: {
        ...activeDraft.parsedData,
        evidence: {
          ...activeDraft.parsedData.evidence,
          projects: updatedProjects,
        },
      },
    });
  };

  const handleAddHighlight = () => {
    if (!newHighlight.trim()) return;
    const currentHighlights = project.highlights || [];
    handleUpdateProject("highlights", [...currentHighlights, newHighlight.trim()]);
    setNewHighlight("");
  };

  const handleRemoveHighlight = (idx: number) => {
    const currentHighlights = [...(project.highlights || [])];
    currentHighlights.splice(idx, 1);
    handleUpdateProject("highlights", currentHighlights);
  };

  const handleAddSkill = () => {
    if (!newSkill.trim()) return;
    const currentSkills = activeDraft.parsedData.evidence.skills || [];
    if (!currentSkills.some((s) => s.name.toLowerCase() === newSkill.trim().toLowerCase())) {
      setActiveDraft({
        ...activeDraft,
        parsedData: {
          ...activeDraft.parsedData,
          evidence: {
            ...activeDraft.parsedData.evidence,
            skills: [...currentSkills, { name: newSkill.trim(), category: "Roadmap Verified" }],
          },
        },
      });
    }
    setNewSkill("");
  };

  const handleRemoveSkill = (idx: number) => {
    const currentSkills = [...(activeDraft.parsedData.evidence.skills || [])];
    currentSkills.splice(idx, 1);
    setActiveDraft({
      ...activeDraft,
      parsedData: {
        ...activeDraft.parsedData,
        evidence: {
          ...activeDraft.parsedData.evidence,
          skills: currentSkills,
        },
      },
    });
  };

  const handleConfirm = async () => {
    setIsConfirming(true);
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

      setIsSuccess(true);
      if (onConfirmSuccess) onConfirmSuccess();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to confirm evidence import.");
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !isConfirming && onClose()}
      title="Review Roadmap Project Evidence"
      description="Review and adjust project claims before explicitly importing into your Master Workspace."
      maxWidth="3xl"
    >
      <div className="space-y-5">
        {/* Provenance Header Banner */}
        <div className="flex items-start gap-3 rounded-card border border-accent/30 bg-accent-soft p-4 text-small">
          <Sparkles className="h-5 w-5 text-accent mt-0.5 shrink-0" />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-primary">Origin: Career Roadmap Project</span>
              <Badge variant="outline" className="bg-surface text-accent border-accent/40 font-mono text-[11px]">
                Roadmap Staging
              </Badge>
            </div>
            <p className="text-secondary text-caption">
              Target Milestone: <strong className="text-primary">{milestoneTitle}</strong>.
              Review your project description, highlights, and demonstrated skills below.
            </p>
          </div>
        </div>

        {isSuccess ? (
          <div className="space-y-4 py-3">
            <div className="flex items-center gap-3 rounded-btn border border-status-success/30 bg-status-success-soft p-4 text-status-success">
              <CheckCircle2 className="h-6 w-6 shrink-0" />
              <div>
                <p className="font-semibold text-body">Evidence Successfully Confirmed!</p>
                <p className="text-caption text-secondary">
                  Your project and associated verified skills have been imported into your Master Workspace.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-border/60">
              <Link href="/workspace/projects">
                <Button type="button" variant="outline" className="gap-1.5">
                  <FolderGit2 className="h-4 w-4" />
                  <span>View in Workspace Projects</span>
                </Button>
              </Link>
              <Link href="/analyzer">
                <Button type="button" variant="primary" className="gap-1.5">
                  <Sparkles className="h-4 w-4" />
                  <span>Run ATS Audit</span>
                </Button>
              </Link>
              <Button type="button" variant="ghost" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="flex items-center gap-2 border-b border-border pb-2">
              <Button
                variant={activeTab === "project" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("project")}
                className="gap-1.5 text-small"
              >
                <FolderGit2 className="h-3.5 w-3.5" />
                <span>Project Blueprint ({activeDraft.parsedData.evidence.projects.length})</span>
              </Button>
              <Button
                variant={activeTab === "skills" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("skills")}
                className="gap-1.5 text-small"
              >
                <Wrench className="h-3.5 w-3.5" />
                <span>Demonstrated Skills ({(activeDraft.parsedData.evidence.skills || []).length})</span>
              </Button>
            </div>

            {/* Tab: Project Details */}
            {activeTab === "project" && (
              <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
                <div className="space-y-1.5">
                  <label className="text-small font-medium text-primary">Project Title</label>
                  <Input
                    value={project.title}
                    onChange={(e) => handleUpdateProject("title", e.target.value)}
                    placeholder="Project Title"
                    disabled={isConfirming}
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-small font-medium text-primary">Problem Statement & Description</label>
                  <Textarea
                    rows={3}
                    value={project.description || ""}
                    onChange={(e) => handleUpdateProject("description", e.target.value)}
                    placeholder="Describe the problem, approach, and outcomes..."
                    disabled={isConfirming}
                  />
                </div>

                {/* Highlights */}
                <div className="space-y-2">
                  <label className="text-small font-medium text-primary">
                    Architecture Highlights & Key Features
                  </label>
                  <div className="space-y-2">
                    {(project.highlights || []).map((highlight, idx) => (
                      <div key={idx} className="flex items-start gap-2 bg-page border border-border rounded-btn p-2.5">
                        <span className="text-small text-secondary flex-1 leading-relaxed">{highlight}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={isConfirming}
                          className="h-6 w-6 p-0 text-status-error hover:bg-status-error-soft shrink-0"
                          onClick={() => handleRemoveHighlight(idx)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ))}

                    <div className="flex gap-2">
                      <Input
                        placeholder="Add another highlight or architecture component..."
                        value={newHighlight}
                        onChange={(e) => setNewHighlight(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            handleAddHighlight();
                          }
                        }}
                        disabled={isConfirming}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleAddHighlight}
                        disabled={isConfirming || !newHighlight.trim()}
                        className="gap-1 shrink-0"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add</span>
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tab: Demonstrated Skills */}
            {activeTab === "skills" && (
              <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
                <p className="text-small text-secondary">
                  The following skills will be added to your Master Workspace skills inventory once confirmed:
                </p>

                <div className="flex flex-wrap gap-2">
                  {(activeDraft.parsedData.evidence.skills || []).map((sk, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-1.5 bg-surface border border-border rounded-full px-3 py-1 text-small text-primary"
                    >
                      <span>{sk.name}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveSkill(idx)}
                        disabled={isConfirming}
                        className="text-muted hover:text-status-error ml-1 transition-colors"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                <div className="flex gap-2 pt-2 border-t border-border">
                  <Input
                    placeholder="Add verified skill (e.g. FastAPI, Docker)..."
                    value={newSkill}
                    onChange={(e) => setNewSkill(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddSkill();
                      }
                    }}
                    disabled={isConfirming}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleAddSkill}
                    disabled={isConfirming || !newSkill.trim()}
                    className="gap-1 shrink-0"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Add Skill</span>
                  </Button>
                </div>
              </div>
            )}

            {/* Error Message */}
            {errorMessage && (
              <div className="flex items-center gap-2 rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
              <Button
                type="button"
                variant="ghost"
                disabled={isConfirming}
                onClick={onClose}
              >
                Discard Draft
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={isConfirming || !project.title?.trim()}
                onClick={handleConfirm}
                className="gap-1.5"
              >
                {isConfirming ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Importing to Workspace...</span>
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    <span>Confirm & Import to Master Workspace</span>
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
