"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  RoadmapPlan,
  RoadmapMilestone,
  MilestoneState,
  VerificationArtifactInput,
} from "@/types/career";
import {
  getRoadmap,
  updateMilestoneProgress,
  promoteMilestoneToEvidenceDraft,
  reconcileRoadmap,
  refreshRoadmap,
  updateRoadmapLifecycle,
} from "@/lib/career-roadmap-api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorAlert, ToastBanner } from "@/components/common/state-views";
import { RoadmapMilestoneCard } from "@/components/career/RoadmapMilestoneCard";
import { ArtifactSubmissionModal } from "@/components/career/ArtifactSubmissionModal";
import {
  RoadmapEvidenceReviewModal,
  RoadmapPromotionDraft,
} from "@/components/career/RoadmapEvidenceReviewModal";
import { BridgeAttestationModal } from "@/components/career/BridgeAttestationModal";
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Clock,
  Compass,
  Layers,
  Sparkles,
  TrendingUp,
  Award,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  FileCheck2,
  Archive,
  ArchiveRestore,
  Loader2,
  AlertTriangle,
} from "lucide-react";

export default function CareerRoadmapDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const roadmapId = params?.roadmapId as string;

  const [roadmap, setRoadmap] = useState<RoadmapPlan | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReconciling, setIsReconciling] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // In-flight action guard
  const [actionMilestoneId, setActionMilestoneId] = useState<string | null>(null);

  // Artifact Modal State
  const [artifactModalMilestone, setArtifactModalMilestone] = useState<RoadmapMilestone | null>(null);

  // Promotion Review Modal State
  const [reviewDraft, setReviewDraft] = useState<{
    draft: RoadmapPromotionDraft;
    milestoneTitle: string;
  } | null>(null);

  // Attestation Modal State (for TransferableBridge)
  const [attestationModalMilestone, setAttestationModalMilestone] = useState<RoadmapMilestone | null>(null);
  const [authToken, setAuthToken] = useState<string>("");

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchRoadmap = useCallback(async () => {
    if (!user || !roadmapId) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const data = await getRoadmap(idToken, roadmapId);
      setRoadmap(data);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load roadmap details.");
    } finally {
      setIsLoading(false);
    }
  }, [user, roadmapId]);

  useEffect(() => {
    fetchRoadmap();
  }, [fetchRoadmap]);

  const handleUpdateState = async (milestoneId: string, targetState: MilestoneState) => {
    if (!user || !roadmap) return;
    setActionMilestoneId(milestoneId);

    try {
      const idToken = await user.getIdToken();
      const updated = await updateMilestoneProgress(idToken, roadmap.roadmapId, {
        milestoneId,
        targetState,
        expectedVersion: roadmap.version,
      });
      setRoadmap(updated);
      showToast("Milestone progress updated", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to update milestone progress.", "error");
    } finally {
      setActionMilestoneId(null);
    }
  };

  const handleSubmitArtifact = async (artifact: VerificationArtifactInput) => {
    if (!user || !roadmap || !artifactModalMilestone) return;
    setActionMilestoneId(artifactModalMilestone.milestoneId);

    try {
      const idToken = await user.getIdToken();
      const updated = await updateMilestoneProgress(idToken, roadmap.roadmapId, {
        milestoneId: artifactModalMilestone.milestoneId,
        targetState: "ARTIFACT_SUBMITTED",
        expectedVersion: roadmap.version,
        artifact,
      });
      setRoadmap(updated);
      setArtifactModalMilestone(null);
      showToast("Verification artifact submitted", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to submit artifact.", "error");
      throw err;
    } finally {
      setActionMilestoneId(null);
    }
  };

  const handlePromoteProject = async (milestone: RoadmapMilestone) => {
    if (!user || !roadmap) return;
    setActionMilestoneId(milestone.milestoneId);

    try {
      const idToken = await user.getIdToken();
      const draft = await promoteMilestoneToEvidenceDraft(idToken, roadmap.roadmapId, milestone.milestoneId);

      setReviewDraft({
        draft,
        milestoneTitle: milestone.title,
      });
      showToast("Promotion draft created. Review and confirm below.", "info");
    } catch (err: any) {
      if (err.data?.detail && err.data.detail.includes("already been promoted and confirmed")) {
        showToast("This project has already been confirmed into your Master Workspace.", "info");
      } else {
        showToast(err.message || "Failed to create promotion draft.", "error");
      }
    } finally {
      setActionMilestoneId(null);
    }
  };

  const handleReconcile = async () => {
    if (!user || !roadmap) return;
    setIsReconciling(true);

    try {
      const idToken = await user.getIdToken();
      const res = await reconcileRoadmap(idToken, roadmap.roadmapId);
      setRoadmap(res.updatedPlan);
      showToast(
        `Reconciliation complete: ${res.groundedCount} grounded, ${res.notGroundedCount} remaining.`,
        "success"
      );
    } catch (err: any) {
      showToast(err.message || "Failed to reconcile roadmap.", "error");
    } finally {
      setIsReconciling(false);
    }
  };

  const handleRefresh = async () => {
    if (!user || !roadmap) return;
    setIsRefreshing(true);

    try {
      const idToken = await user.getIdToken();
      const res = await refreshRoadmap(idToken, roadmap.roadmapId, {
        expectedVersion: roadmap.version,
      });
      setRoadmap(res.updatedPlan);
      showToast(
        `Roadmap refreshed! Preserved ${res.completedMilestonesPreserved} completed milestones.`,
        "success"
      );
    } catch (err: any) {
      showToast(err.message || "Failed to refresh roadmap.", "error");
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleArchiveRoadmap = async () => {
    if (!user || !roadmap) return;
    setIsArchiving(true);

    try {
      const idToken = await user.getIdToken();
      const updated = await updateRoadmapLifecycle(idToken, roadmap.roadmapId, {
        lifecycle: "ARCHIVED",
        expectedVersion: roadmap.version,
      });
      setRoadmap(updated);
      showToast("Roadmap archived. Progression is now read-only.", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to archive roadmap.", "error");
    } finally {
      setIsArchiving(false);
    }
  };

  if (isLoading) {
    return <LoadingState text="Loading career capability roadmap..." />;
  }

  if (errorMessage || !roadmap) {
    return (
      <div className="space-y-4">
        <Link href="/career/roadmaps">
          <Button variant="ghost" size="sm" className="gap-1.5">
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Roadmaps</span>
          </Button>
        </Link>
        <ErrorAlert message={errorMessage || "Roadmap not found."} />
      </div>
    );
  }

  const isReadOnly = roadmap.lifecycle === "ARCHIVED" || roadmap.lifecycle === "COMPLETED";

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && <ToastBanner message={toast.message} type={toast.type} />}

      {/* Navigation & Header */}
      <div className="space-y-3">
        <Link href="/career/roadmaps">
          <Button variant="ghost" size="sm" className="gap-1.5 text-muted hover:text-primary">
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Roadmaps</span>
          </Button>
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-h2 font-semibold text-primary">{roadmap.title}</h2>
              <Badge variant="outline" className="bg-accent-soft text-accent border-accent/30 font-medium">
                {roadmap.targetRole}
              </Badge>
              {roadmap.targetCompany && (
                <Badge variant="outline" className="bg-surface text-secondary border-border">
                  <Building2 className="h-3 w-3 mr-1" />
                  {roadmap.targetCompany}
                </Badge>
              )}
              {/* Lifecycle Badge */}
              <Badge
                variant="outline"
                className={
                  roadmap.lifecycle === "COMPLETED"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : roadmap.lifecycle === "ARCHIVED"
                    ? "bg-slate-800 text-slate-400 border-slate-700"
                    : "bg-blue-500/10 text-blue-400 border-blue-500/30"
                }
              >
                {roadmap.lifecycle}
              </Badge>
            </div>
            <p className="text-small text-secondary mt-1">
              Deterministic capability progression DAG grounded in your candidate evidence and target role requirements.
            </p>
          </div>

          {/* Top Actions: Reconcile, Refresh, Archive */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={handleReconcile}
              disabled={isReconciling || isRefreshing}
              className="gap-1.5 text-small"
            >
              {isReconciling ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <FileCheck2 className="h-3.5 w-3.5 text-accent" />
              )}
              <span>Reconcile Evidence</span>
            </Button>

            {roadmap.lifecycle !== "ARCHIVED" && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleRefresh}
                disabled={isRefreshing || isReconciling}
                className="gap-1.5 text-small"
              >
                {isRefreshing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5 text-emerald-400" />
                )}
                <span>Refresh Analysis</span>
              </Button>
            )}

            {roadmap.lifecycle !== "ARCHIVED" && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleArchiveRoadmap}
                disabled={isArchiving}
                className="gap-1.5 text-small text-secondary hover:text-primary"
              >
                <Archive className="h-3.5 w-3.5" />
                <span>Archive</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Stale Evidence Banner */}
      {roadmap.isStale && roadmap.lifecycle === "ACTIVE" && (
        <div className="flex items-center justify-between gap-3 rounded-card border border-amber-500/30 bg-amber-500/10 p-3.5 text-small text-amber-300">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>
              <strong>Workspace Evidence Changed:</strong> Your Master Workspace has new evidence since this roadmap was last analyzed.
            </span>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="h-7 text-[11px] border-amber-500/40 text-amber-200 hover:bg-amber-500/20"
          >
            Refresh Now
          </Button>
        </div>
      )}

      {/* Overview Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border-border bg-surface">
          <div className="flex items-center justify-between">
            <span className="text-caption text-muted font-medium uppercase tracking-[0.4px]">Progress</span>
            <TrendingUp className="h-4 w-4 text-accent" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-h2 font-bold text-primary">{roadmap.overallProgressPct}%</span>
            <span className="text-caption text-secondary">
              ({roadmap.completedMilestones}/{roadmap.totalMilestones} done)
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${roadmap.overallProgressPct}%` }}
            />
          </div>
        </Card>

        <Card className="p-4 border-border bg-surface">
          <div className="flex items-center justify-between">
            <span className="text-caption text-muted font-medium uppercase tracking-[0.4px]">Total Milestones</span>
            <Layers className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 text-h2 font-bold text-primary">{roadmap.totalMilestones}</div>
          <span className="text-caption text-muted mt-1 block">Capability steps</span>
        </Card>

        <Card className="p-4 border-border bg-surface">
          <div className="flex items-center justify-between">
            <span className="text-caption text-muted font-medium uppercase tracking-[0.4px]">Estimated Time</span>
            <Clock className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-h2 font-bold text-primary">~{roadmap.estimatedTotalWeeks} wks</div>
          <span className="text-caption text-muted mt-1 block">Paced learning curriculum</span>
        </Card>

        <Card className="p-4 border-border bg-surface">
          <div className="flex items-center justify-between">
            <span className="text-caption text-muted font-medium uppercase tracking-[0.4px]">Requirements</span>
            <Award className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-h2 font-bold text-primary">
              {roadmap.targetImportanceBreakdown?.mustHaveCount || 0}
            </span>
            <span className="text-caption text-secondary">Must Have</span>
            <span className="text-caption text-muted">
              • {roadmap.targetImportanceBreakdown?.preferredCount || 0} Preferred
            </span>
          </div>
          <span className="text-caption text-muted mt-1 block">Grounded target breakdown</span>
        </Card>
      </div>

      {/* Next Recommended Milestone Banner */}
      {roadmap.nextRecommendedMilestoneId && roadmap.overallProgressPct < 100 && !isReadOnly && (
        <div className="flex items-center gap-3 rounded-card border border-accent/40 bg-accent-soft/30 p-4 text-small">
          <Sparkles className="h-5 w-5 text-accent shrink-0" />
          <div className="flex-1">
            <span className="font-semibold text-primary">Next Recommended Step: </span>
            <span className="text-secondary">
              {
                roadmap.milestones.find((m) => m.milestoneId === roadmap.nextRecommendedMilestoneId)
                  ?.title
              }
            </span>
          </div>
        </div>
      )}

      {/* Milestone DAG Progression Sequence */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-h3 font-semibold text-primary">Milestone Capability DAG</h3>
          <span className="text-caption text-muted">{roadmap.milestones.length} Sequential Steps</span>
        </div>

        <div className="space-y-4">
          {roadmap.milestones.map((milestone) => (
            <RoadmapMilestoneCard
              key={milestone.milestoneId}
              milestone={milestone}
              roadmapVersion={roadmap.version}
              roadmapLifecycle={roadmap.lifecycle}
              allMilestones={roadmap.milestones}
              isNextRecommended={milestone.milestoneId === roadmap.nextRecommendedMilestoneId}
              onUpdateState={handleUpdateState}
              onSubmitArtifact={(m) => setArtifactModalMilestone(m)}
              onPromoteProject={handlePromoteProject}
              onOpenAttestation={async (m) => {
                const token = (await user?.getIdToken()) || "";
                setAuthToken(token);
                setAttestationModalMilestone(m);
              }}
              isActionLoading={actionMilestoneId === milestone.milestoneId}
            />
          ))}
        </div>
      </div>

      {/* Artifact Submission Modal */}
      {artifactModalMilestone && (
        <ArtifactSubmissionModal
          isOpen={true}
          onClose={() => setArtifactModalMilestone(null)}
          milestone={artifactModalMilestone}
          expectedVersion={roadmap.version}
          onSubmit={handleSubmitArtifact}
          isLoading={actionMilestoneId === artifactModalMilestone.milestoneId}
        />
      )}

      {/* Roadmap Evidence Promotion Review & Confirmation Modal */}
      {reviewDraft && (
        <RoadmapEvidenceReviewModal
          isOpen={true}
          onClose={() => setReviewDraft(null)}
          draft={reviewDraft.draft}
          milestoneTitle={reviewDraft.milestoneTitle}
          onConfirmSuccess={() => {
            fetchRoadmap();
          }}
        />
      )}

      {/* Bridge Attestation Modal for TransferableBridge milestones */}
      {attestationModalMilestone && attestationModalMilestone.bridgeDetails && (
        <BridgeAttestationModal
          isOpen={true}
          onClose={() => setAttestationModalMilestone(null)}
          bridge={attestationModalMilestone.bridgeDetails}
          variantId={roadmap.sourceVariantId || "variant_main"}
          variantVersion={roadmap.version}
          authToken={authToken}
          onAttestationSuccess={() => {
            setAttestationModalMilestone(null);
            fetchRoadmap();
            showToast("Skill attested successfully", "success");
          }}
        />
      )}
    </div>
  );
}
