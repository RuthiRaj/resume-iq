"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  RoadmapMilestone,
  MilestoneState,
  VerificationArtifactInput,
} from "@/types/career";
import {
  BookOpen,
  CheckCircle2,
  Clock,
  Code2,
  ExternalLink,
  FolderGit2,
  GitBranch,
  Globe,
  Layers,
  Loader2,
  Play,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Award,
  ArrowRight,
  FileCheck,
  Check,
} from "lucide-react";

interface RoadmapMilestoneCardProps {
  milestone: RoadmapMilestone;
  roadmapVersion: number;
  allMilestones: RoadmapMilestone[];
  isNextRecommended?: boolean;
  onUpdateState: (milestoneId: string, targetState: MilestoneState) => Promise<void>;
  onSubmitArtifact: (milestone: RoadmapMilestone) => void;
  onPromoteProject: (milestone: RoadmapMilestone) => Promise<void>;
  onOpenAttestation?: (milestone: RoadmapMilestone) => void;
  isActionLoading?: boolean;
}

export function RoadmapMilestoneCard({
  milestone,
  roadmapVersion,
  allMilestones,
  isNextRecommended = false,
  onUpdateState,
  onSubmitArtifact,
  onPromoteProject,
  onOpenAttestation,
  isActionLoading = false,
}: RoadmapMilestoneCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Check whether prerequisite milestones are fulfilled
  const prereqMilestones = allMilestones.filter((m) =>
    milestone.prerequisiteMilestoneIds.includes(m.milestoneId)
  );
  const arePrereqsSatisfied = prereqMilestones.every(
    (m) => m.state === "VERIFIED_PROJECT" || m.state === "ATTESTED"
  );

  const getCategoryBadgeVariant = (category: string) => {
    switch (category) {
      case "TransferableBridge":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "VerifiableProject":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "CoreFoundation":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
      case "DomainCertification":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const getStateBadge = (state: MilestoneState) => {
    switch (state) {
      case "NOT_STARTED":
        return (
          <Badge variant="outline" className="bg-slate-800/80 text-slate-400 border-slate-700 text-caption">
            Not Started
          </Badge>
        );
      case "IN_PROGRESS":
        return (
          <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/30 text-caption">
            In Progress
          </Badge>
        );
      case "ARTIFACT_SUBMITTED":
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-caption">
            Artifact Submitted
          </Badge>
        );
      case "VERIFIED_PROJECT":
        return (
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-caption">
            Verified Project
          </Badge>
        );
      case "ATTESTED":
        return (
          <Badge variant="outline" className="bg-purple-500/10 text-purple-400 border-purple-500/30 text-caption">
            Attested & Synced
          </Badge>
        );
    }
  };

  return (
    <Card
      className={`border transition-all duration-200 ${
        isNextRecommended
          ? "border-accent shadow-md bg-accent-soft/20"
          : milestone.state === "VERIFIED_PROJECT" || milestone.state === "ATTESTED"
          ? "border-emerald-500/30 bg-surface/80"
          : "border-border bg-surface"
      }`}
    >
      <CardHeader className="p-4 pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-start gap-3">
            {/* Step Number Badge */}
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-small font-semibold ${
                milestone.state === "VERIFIED_PROJECT" || milestone.state === "ATTESTED"
                  ? "bg-emerald-500 text-white"
                  : milestone.state === "IN_PROGRESS"
                  ? "bg-blue-500 text-white"
                  : isNextRecommended
                  ? "bg-accent text-white"
                  : "bg-surface border border-border text-secondary"
              }`}
            >
              {milestone.state === "VERIFIED_PROJECT" || milestone.state === "ATTESTED" ? (
                <Check className="h-4 w-4" />
              ) : (
                milestone.orderIndex + 1
              )}
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-body font-semibold text-primary">{milestone.title}</CardTitle>
                <Badge variant="outline" className={`text-[11px] ${getCategoryBadgeVariant(milestone.category)}`}>
                  {milestone.category}
                </Badge>
                {milestone.importance === "MustHave" && (
                  <Badge variant="outline" className="text-[10px] bg-red-500/10 text-red-400 border-red-500/30">
                    Must Have
                  </Badge>
                )}
                {isNextRecommended && (
                  <Badge variant="outline" className="text-[10px] bg-accent-soft text-accent border-accent/40 font-medium">
                    Next Recommended
                  </Badge>
                )}
              </div>
              <p className="text-caption text-secondary mt-0.5">
                Target Capability: <strong className="text-primary">{milestone.targetCapability}</strong> ({milestone.requirementName})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-center">
            <span className="inline-flex items-center gap-1 text-caption text-muted">
              <Clock className="h-3.5 w-3.5" />
              <span>{milestone.estimatedWeeks} wks</span>
            </span>
            {getStateBadge(milestone.state)}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-1 space-y-4">
        {/* Rationale */}
        <p className="text-small text-secondary leading-relaxed bg-page p-3 rounded-btn border border-border/60">
          {milestone.rationale}
        </p>

        {/* Prerequisites Banner if any */}
        {prereqMilestones.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-caption">
            <span className="text-muted font-medium">Prerequisites:</span>
            {prereqMilestones.map((pm) => (
              <Badge
                key={pm.milestoneId}
                variant="outline"
                className={`text-[11px] ${
                  pm.state === "VERIFIED_PROJECT" || pm.state === "ATTESTED"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                }`}
              >
                {pm.title} ({pm.state === "VERIFIED_PROJECT" || pm.state === "ATTESTED" ? "Done" : "Pending"})
              </Badge>
            ))}
          </div>
        )}

        {/* Actionable Learning Curriculum if present */}
        {milestone.learningPath && (
          <div className="space-y-2 rounded-card border border-border bg-page p-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-small font-semibold text-primary">
                <BookOpen className="h-4 w-4 text-emerald-400" />
                <span>{milestone.learningPath.title}</span>
              </div>
              <span className="text-caption text-muted">{milestone.learningPath.estimatedWeeks} Weeks Estimated</span>
            </div>

            {milestone.learningPath.keyMilestones.length > 0 && (
              <ul className="space-y-1 text-caption text-secondary pt-1">
                {milestone.learningPath.keyMilestones.map((km, kIdx) => (
                  <li key={kIdx} className="flex items-start gap-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 mt-0.5 shrink-0" />
                    <span>{km}</span>
                  </li>
                ))}
              </ul>
            )}

            {milestone.learningPath.authoritativeDocsUrl && (
              <a
                href={milestone.learningPath.authoritativeDocsUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-caption text-accent hover:underline pt-1"
              >
                <span>Official Documentation & Learning Resource</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        )}

        {/* Verifiable Project Blueprint if present */}
        {milestone.projectBlueprint && (
          <div className="space-y-2.5 rounded-card border border-border bg-page p-3.5">
            <div className="flex items-center gap-2 text-small font-semibold text-primary">
              <Code2 className="h-4 w-4 text-accent" />
              <span>Project Blueprint: {milestone.projectBlueprint.projectTitle}</span>
            </div>
            <p className="text-caption text-secondary">{milestone.projectBlueprint.problemStatement}</p>

            {milestone.projectBlueprint.architectureComponents.length > 0 && (
              <div className="space-y-1 pt-1">
                <span className="text-caption text-muted font-medium">Architecture Components:</span>
                <div className="flex flex-wrap gap-1.5">
                  {milestone.projectBlueprint.architectureComponents.map((comp, cIdx) => (
                    <Badge key={cIdx} variant="outline" className="text-[11px] bg-surface text-secondary border-border">
                      {comp}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {milestone.projectBlueprint.demonstratedSkills.length > 0 && (
              <div className="space-y-1 pt-1">
                <span className="text-caption text-muted font-medium">Demonstrated Skills:</span>
                <div className="flex flex-wrap gap-1.5">
                  {milestone.projectBlueprint.demonstratedSkills.map((sk, sIdx) => (
                    <Badge key={sIdx} variant="outline" className="text-[11px] bg-accent-soft/40 text-accent border-accent/30">
                      {sk}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Verification Artifact Banner if present */}
        {milestone.verificationArtifact && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-btn border border-border bg-surface p-3 text-caption">
            <div className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              <div>
                <span className="font-semibold text-primary">
                  {milestone.verificationArtifact.artifactType}:{" "}
                </span>
                {milestone.verificationArtifact.url ? (
                  <a
                    href={milestone.verificationArtifact.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent hover:underline inline-flex items-center gap-1"
                  >
                    <span>{milestone.verificationArtifact.url}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="text-secondary">Submitted</span>
                )}
                {milestone.verificationArtifact.repositoryBranch && (
                  <span className="text-muted ml-2">({milestone.verificationArtifact.repositoryBranch})</span>
                )}
              </div>
            </div>
            <span className="text-muted">
              Checklist: {milestone.verificationArtifact.checklistCompleted.length} items
            </span>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-border/60">
          {/* Action: NOT_STARTED -> Start Milestone */}
          {milestone.state === "NOT_STARTED" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActionLoading}
              onClick={() => onUpdateState(milestone.milestoneId, "IN_PROGRESS")}
              className="gap-1.5 text-small"
            >
              {isActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 text-accent" />}
              <span>Start Milestone</span>
            </Button>
          )}

          {/* Action: IN_PROGRESS -> Submit Artifact or Attestation */}
          {milestone.state === "IN_PROGRESS" && (
            <>
              {milestone.category === "TransferableBridge" ? (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={isActionLoading}
                  onClick={() => onOpenAttestation && onOpenAttestation(milestone)}
                  className="gap-1.5 text-small"
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Attest Transferred Skill</span>
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="primary"
                  disabled={isActionLoading}
                  onClick={() => onSubmitArtifact(milestone)}
                  className="gap-1.5 text-small"
                >
                  <FolderGit2 className="h-3.5 w-3.5" />
                  <span>Submit Verification Artifact</span>
                </Button>
              )}
            </>
          )}

          {/* Action: ARTIFACT_SUBMITTED -> Mark VERIFIED_PROJECT */}
          {milestone.state === "ARTIFACT_SUBMITTED" && (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={isActionLoading}
                onClick={() => onSubmitArtifact(milestone)}
                className="gap-1.5 text-small"
              >
                <span>Edit Artifact</span>
              </Button>
              <Button
                size="sm"
                variant="primary"
                disabled={isActionLoading}
                onClick={() => onUpdateState(milestone.milestoneId, "VERIFIED_PROJECT")}
                className="gap-1.5 text-small"
              >
                {isActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5" />}
                <span>Verify Project</span>
              </Button>
            </div>
          )}

          {/* Action: VERIFIED_PROJECT -> Promote to Evidence Draft */}
          {milestone.state === "VERIFIED_PROJECT" && (
            <Button
              size="sm"
              variant="primary"
              disabled={isActionLoading}
              onClick={() => onPromoteProject(milestone)}
              className="gap-1.5 text-small bg-emerald-600 hover:bg-emerald-500 text-white shadow-subtle"
            >
              {isActionLoading ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Creating Promotion Draft...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Promote to Evidence Draft</span>
                </>
              )}
            </Button>
          )}

          {/* State: ATTESTED */}
          {milestone.state === "ATTESTED" && (
            <div className="flex items-center gap-1.5 text-caption text-purple-400 font-medium">
              <CheckCircle2 className="h-4 w-4" />
              <span>Skill Attested & Hydrated in Workspace</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
