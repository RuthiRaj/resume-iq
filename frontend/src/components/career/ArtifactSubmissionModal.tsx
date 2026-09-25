"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { RoadmapMilestone, ArtifactType, VerificationArtifactInput } from "@/types/career";
import {
  Code2,
  Globe,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Info,
  ShieldCheck,
} from "lucide-react";

interface ArtifactSubmissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  milestone: RoadmapMilestone;
  expectedVersion: number;
  onSubmit: (artifact: VerificationArtifactInput) => Promise<void>;
  isLoading?: boolean;
}

export function ArtifactSubmissionModal({
  isOpen,
  onClose,
  milestone,
  expectedVersion,
  onSubmit,
  isLoading = false,
}: ArtifactSubmissionModalProps) {
  const [artifactType, setArtifactType] = useState<ArtifactType>("GitHubRepository");
  const [url, setUrl] = useState(milestone.verificationArtifact?.url || "");
  const [repositoryBranch, setRepositoryBranch] = useState(
    milestone.verificationArtifact?.repositoryBranch || "main"
  );
  const [completedItems, setCompletedItems] = useState<string[]>(
    milestone.verificationArtifact?.checklistCompleted || []
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const checklist = milestone.projectBlueprint?.verificationChecklist || [
    "Architecture documentation completed",
    "Core requirements implemented and tested",
    "Code committed to source control",
  ];

  const handleToggleChecklist = (item: string) => {
    if (completedItems.includes(item)) {
      setCompletedItems(completedItems.filter((i) => i !== item));
    } else {
      setCompletedItems([...completedItems, item]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!url.trim()) {
      setErrorMessage("Please provide a valid repository, deployment, or writeup URL.");
      return;
    }

    try {
      new URL(url.trim());
    } catch {
      setErrorMessage("Please enter a well-formed URL (e.g. https://github.com/user/repo).");
      return;
    }

    try {
      await onSubmit({
        artifactType,
        url: url.trim(),
        repositoryBranch: artifactType === "GitHubRepository" ? repositoryBranch.trim() : undefined,
        checklistCompleted: completedItems,
      });
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to submit artifact.");
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !isLoading && onClose()}
      title="Submit Milestone Verification Artifact"
      description={`Submit proof of implementation for: ${milestone.title}`}
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Info Banner */}
        <div className="flex items-start gap-2.5 rounded-btn border border-border bg-page p-3.5 text-small text-secondary">
          <Info className="h-4 w-4 text-accent mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold text-primary">Auditable Evidence Ledger</p>
            <p>
              Submitting an artifact records auditable proof in your roadmap. Once verified, you can
              promote this project into your Master Workspace evidence via candidate review.
            </p>
          </div>
        </div>

        {/* Artifact Type Selection */}
        <div className="space-y-1.5">
          <label className="text-small font-medium text-primary">Artifact Type</label>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setArtifactType("GitHubRepository")}
              className={`flex items-center justify-center gap-1.5 rounded-btn border p-2.5 text-small font-medium transition-all ${
                artifactType === "GitHubRepository"
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border bg-surface text-secondary hover:text-primary hover:bg-page"
              }`}
            >
              <Code2 className="h-4 w-4" />
              <span>GitHub Repo</span>
            </button>
            <button
              type="button"
              onClick={() => setArtifactType("DeploymentUrl")}
              className={`flex items-center justify-center gap-1.5 rounded-btn border p-2.5 text-small font-medium transition-all ${
                artifactType === "DeploymentUrl"
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border bg-surface text-secondary hover:text-primary hover:bg-page"
              }`}
            >
              <Globe className="h-4 w-4" />
              <span>Live Demo</span>
            </button>
            <button
              type="button"
              onClick={() => setArtifactType("TechnicalWriteup")}
              className={`flex items-center justify-center gap-1.5 rounded-btn border p-2.5 text-small font-medium transition-all ${
                artifactType === "TechnicalWriteup"
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border bg-surface text-secondary hover:text-primary hover:bg-page"
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>Writeup / Docs</span>
            </button>
          </div>
        </div>

        {/* URL Input */}
        <div className="space-y-1.5">
          <label className="text-small font-medium text-primary">
            {artifactType === "GitHubRepository"
              ? "Repository URL"
              : artifactType === "DeploymentUrl"
              ? "Live Deployment URL"
              : "Technical Writeup URL"}
          </label>
          <Input
            placeholder={
              artifactType === "GitHubRepository"
                ? "https://github.com/username/project-repo"
                : artifactType === "DeploymentUrl"
                ? "https://my-app.vercel.app"
                : "https://medium.com/@username/project-architecture"
            }
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={isLoading}
            required
          />
        </div>

        {/* Branch Input for GitHub Repos */}
        {artifactType === "GitHubRepository" && (
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Repository Branch</label>
            <Input
              placeholder="main"
              value={repositoryBranch}
              onChange={(e) => setRepositoryBranch(e.target.value)}
              disabled={isLoading}
            />
          </div>
        )}

        {/* Verification Checklist */}
        {checklist.length > 0 && (
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">
              Verification Checklist ({completedItems.length}/{checklist.length})
            </label>
            <div className="space-y-1.5 rounded-card border border-border bg-page p-3 max-h-48 overflow-y-auto">
              {checklist.map((item, idx) => {
                const isChecked = completedItems.includes(item);
                return (
                  <label
                    key={idx}
                    className="flex items-start gap-2 text-small text-secondary hover:text-primary cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => handleToggleChecklist(item)}
                      disabled={isLoading}
                      className="mt-0.5 rounded border-border text-accent focus:ring-accent"
                    />
                    <span className={isChecked ? "text-primary font-medium" : ""}>{item}</span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* Error Alert */}
        {errorMessage && (
          <div className="flex items-center gap-2 rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={isLoading || !url.trim()}
            className="gap-1.5"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Submitting...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="h-4 w-4" />
                <span>Submit Artifact</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
