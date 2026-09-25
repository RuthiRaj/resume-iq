"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { RoadmapPlan } from "@/types/career";
import { listRoadmaps, generateRoadmap, deleteRoadmap } from "@/lib/career-roadmap-api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Modal } from "@/components/ui/modal";
import { LoadingState, EmptyState, ToastBanner } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import { formatDate } from "@/lib/utils";
import {
  Compass,
  Plus,
  ArrowRight,
  Sparkles,
  Clock,
  CheckCircle2,
  Trash2,
  Building2,
  Layers,
  AlertCircle,
  Loader2,
  TrendingUp,
} from "lucide-react";

export default function CareerRoadmapsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [roadmaps, setRoadmaps] = useState<RoadmapPlan[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Generate Roadmap Modal State
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [targetRole, setTargetRole] = useState("");
  const [targetCompany, setTargetCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Delete Roadmap State
  const [itemToDelete, setItemToDelete] = useState<{ id: string; title: string } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchRoadmaps = useCallback(async () => {
    if (!user) return;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const data = await listRoadmaps(idToken);
      setRoadmaps(data.roadmaps || []);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load career roadmaps.");
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchRoadmaps();
  }, [fetchRoadmaps]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetRole.trim()) {
      setGenerateError("Please enter a target role.");
      return;
    }

    setIsGenerating(true);
    setGenerateError(null);

    try {
      const idToken = await user?.getIdToken();
      if (!idToken) throw new Error("User session expired. Please sign in again.");

      const newRoadmap = await generateRoadmap(idToken, {
        targetRole: targetRole.trim(),
        targetCompany: targetCompany.trim() || undefined,
        jobDescription: jobDescription.trim() || undefined,
      });

      setIsGenerateOpen(false);
      showToast("Career roadmap generated successfully", "success");
      router.push(`/career/roadmaps/${newRoadmap.roadmapId}`);
    } catch (err: any) {
      setGenerateError(err.message || "Failed to generate roadmap.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDelete = async () => {
    if (!itemToDelete) return;

    try {
      const idToken = await user?.getIdToken();
      if (!idToken) throw new Error("User session expired.");

      await deleteRoadmap(idToken, itemToDelete.id);
      setRoadmaps((prev) => prev.filter((r) => r.roadmapId !== itemToDelete.id));
      showToast("Career roadmap deleted", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to delete roadmap.", "error");
    } finally {
      setItemToDelete(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && <ToastBanner message={toast.message} type={toast.type} />}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Career Roadmaps</h2>
          <p className="text-small text-secondary">
            Deterministic capability progression plans grounded in your master workspace evidence and target career gaps.
          </p>
        </div>

        <Button
          onClick={() => {
            setIsGenerateOpen(true);
            setGenerateError(null);
          }}
          variant="primary"
          size="sm"
          className="gap-1.5 self-start"
        >
          <Plus className="h-4 w-4" />
          <span>New Roadmap</span>
        </Button>
      </div>

      {isLoading ? (
        <LoadingState text="Loading your career roadmaps..." />
      ) : errorMessage ? (
        <div className="rounded-btn border border-status-error/30 bg-status-error-soft p-4 text-status-error text-small flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <Button size="sm" variant="outline" onClick={fetchRoadmaps}>
            Retry
          </Button>
        </div>
      ) : roadmaps.length === 0 ? (
        <EmptyState
          title="No Career Roadmaps Yet"
          description="Synthesize your first deterministic roadmap to chart an actionable, milestone-driven path from your current evidence to your target dream role."
          actionLabel="Generate Career Roadmap"
          onAction={() => setIsGenerateOpen(true)}
          icon={Compass}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {roadmaps.map((rm) => {
            const isCompleted = rm.lifecycle === "COMPLETED";
            const isArchived = rm.lifecycle === "ARCHIVED";
            return (
              <Card key={rm.roadmapId} className="flex flex-col justify-between hover:border-accent/40 transition-all">
                <CardHeader className="p-5 pb-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge variant="outline" className="bg-accent-soft text-accent border-accent/30 font-medium">
                        {rm.targetRole}
                      </Badge>
                      {rm.lifecycle && (
                        <Badge
                          variant="outline"
                          className={
                            isCompleted
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 font-medium text-[10px]"
                              : isArchived
                              ? "bg-muted/10 text-muted border-muted/30 font-medium text-[10px]"
                              : "bg-blue-500/10 text-blue-400 border-blue-500/30 font-medium text-[10px]"
                          }
                        >
                          {rm.lifecycle}
                        </Badge>
                      )}
                      {rm.isStale && (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/30 font-medium text-[10px]">
                          STALE
                        </Badge>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-muted hover:text-status-error"
                      onClick={() => setItemToDelete({ id: rm.roadmapId, title: rm.title })}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  <CardTitle className="text-body font-semibold text-primary line-clamp-2">
                    {rm.title}
                  </CardTitle>
                  {rm.targetCompany && (
                    <div className="flex items-center gap-1.5 text-caption text-secondary">
                      <Building2 className="h-3.5 w-3.5 text-muted" />
                      <span>{rm.targetCompany}</span>
                    </div>
                  )}
                </CardHeader>

              <CardContent className="p-5 pt-0 space-y-4">
                {/* Progress Bar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-caption text-secondary">
                    <span>Progress</span>
                    <span className="font-semibold text-primary">{rm.overallProgressPct}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                    <div
                      className="h-full rounded-full bg-accent transition-all duration-500"
                      style={{ width: `${rm.overallProgressPct}%` }}
                    />
                  </div>
                </div>

                {/* Metadata Row */}
                <div className="grid grid-cols-2 gap-2 text-caption text-muted pt-1 border-t border-border/60">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    <span>
                      {rm.completedMilestones}/{rm.totalMilestones} Milestones
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 justify-end">
                    <Clock className="h-3.5 w-3.5 text-muted" />
                    <span>~{rm.estimatedTotalWeeks} Weeks</span>
                  </div>
                </div>

                {/* Open Button */}
                <Link href={`/career/roadmaps/${rm.roadmapId}`} className="block pt-1">
                  <Button variant="outline" size="sm" className="w-full gap-1.5">
                    <span>View Roadmap</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </CardContent>
            </Card>
          );
        })}
        </div>
      )}

      {/* Generate Roadmap Modal */}
      <Modal
        isOpen={isGenerateOpen}
        onClose={() => !isGenerating && setIsGenerateOpen(false)}
        title="Synthesize Career Capability Roadmap"
        description="Deterministically build a milestone progression DAG grounded in your workspace evidence and target role requirements."
        maxWidth="lg"
      >
        <form onSubmit={handleGenerate} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">
              Target Role <span className="text-status-error">*</span>
            </label>
            <Input
              placeholder="e.g. Senior Machine Learning Engineer"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              disabled={isGenerating}
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Target Company (Optional)</label>
            <Input
              placeholder="e.g. Google, Stripe, OpenAI"
              value={targetCompany}
              onChange={(e) => setTargetCompany(e.target.value)}
              disabled={isGenerating}
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Job Description / Requirements (Optional)</label>
            <Textarea
              rows={4}
              placeholder="Paste target job description to extract bespoke technical and experiential requirements..."
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              disabled={isGenerating}
            />
          </div>

          {generateError && (
            <div className="flex items-center gap-2 rounded-btn border border-status-error/30 bg-status-error-soft p-3 text-status-error text-small">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{generateError}</span>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button
              type="button"
              variant="ghost"
              disabled={isGenerating}
              onClick={() => setIsGenerateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isGenerating || !targetRole.trim()}
              className="gap-1.5"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Synthesizing Roadmap...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Synthesize Roadmap</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Confirm Delete Modal */}
      <ConfirmDeleteModal
        isOpen={Boolean(itemToDelete)}
        onClose={() => setItemToDelete(null)}
        onConfirm={handleDelete}
        title="Delete Career Roadmap"
        description="Are you sure you want to delete this roadmap? Existing Master Workspace evidence and completed project records will remain unaffected."
        itemName={itemToDelete?.title}
      />
    </div>
  );
}
