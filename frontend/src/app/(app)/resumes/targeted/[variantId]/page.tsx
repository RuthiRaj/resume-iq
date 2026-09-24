"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  TargetedResumeVariant,
  ChangeRecord,
  FitComparisonResponse,
  ExportTargetedResumeResponse,
} from "@/lib/store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Modal } from "@/components/ui/modal";
import { LoadingState, EmptyState, ErrorAlert, ToastBanner } from "@/components/common/state-views";
import { formatDate } from "@/lib/utils";
import {
  AlertTriangle,
  ArrowLeft,
  Award,
  BookOpen,
  Briefcase,
  Building2,
  Calendar,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Download,
  ExternalLink,
  FileCheck,
  FileCode,
  FileText,
  GraduationCap,
  History,
  Layers,
  ListChecks,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Undo2,
  Wand2,
  X,
  XCircle,
  Zap,
} from "lucide-react";

export interface AiEditProposal {
  originalText: string;
  proposedText: string;
  diff: string;
  validation: {
    isValid: boolean;
    status: string;
    unsupportedClaims?: Array<{ claimText: string; claimType: string; reason?: string }>;
  };
  requiresConfirmation: boolean;
  userAttestedFacts: string[];
  targetItemId: string;
  targetBulletIndex?: number;
  version: number;
}

export default function TargetedResumeWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const variantId = params?.variantId as string;

  const [variant, setVariant] = useState<TargetedResumeVariant | null>(null);
  const [fitComparison, setFitComparison] = useState<FitComparisonResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"snapshot" | "ledger" | "comparison">("snapshot");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Manual Edit Modal State
  const [isManualEditModalOpen, setIsManualEditModalOpen] = useState(false);
  const [manualEditSection, setManualEditSection] = useState<"Summary" | "Experience" | "Project">("Experience");
  const [manualEditTargetItemId, setManualEditTargetItemId] = useState<string>("");
  const [manualEditTargetBulletIndex, setManualEditTargetBulletIndex] = useState<number | undefined>(undefined);
  const [manualEditText, setManualEditText] = useState("");
  const [isSavingManualEdit, setIsSavingManualEdit] = useState(false);
  const [manualEditError, setManualEditError] = useState<string | null>(null);

  // AI Edit Modal & Proposal State
  const [isAiEditModalOpen, setIsAiEditModalOpen] = useState(false);
  const [aiEditSection, setAiEditSection] = useState<"Summary" | "Experience" | "Project">("Experience");
  const [aiEditTargetItemId, setAiEditTargetItemId] = useState<string>("");
  const [aiEditTargetBulletIndex, setAiEditTargetBulletIndex] = useState<number | undefined>(undefined);
  const [aiEditOriginalText, setAiEditOriginalText] = useState("");
  const [aiEditInstruction, setAiEditInstruction] = useState("");
  const [isGeneratingProposal, setIsGeneratingProposal] = useState(false);
  const [aiProposal, setAiProposal] = useState<AiEditProposal | null>(null);
  const [confirmAttestation, setConfirmAttestation] = useState(false);
  const [isApplyingProposal, setIsApplyingProposal] = useState(false);
  const [aiEditError, setAiEditError] = useState<string | null>(null);

  // Apply Direct Change Modal State
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [applyRequirementName, setApplyRequirementName] = useState("");
  const [applySection, setApplySection] = useState<"Experience" | "Project" | "Summary">("Experience");
  const [applyTargetItemId, setApplyTargetItemId] = useState<string>("");
  const [applyTargetBulletIndex, setApplyTargetBulletIndex] = useState(0);
  const [applyApprovedBullet, setApplyApprovedBullet] = useState("");
  const [applyRemediationId, setApplyRemediationId] = useState("");
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);

  // Revert Confirmation Dialog State
  const [revertingChange, setRevertingChange] = useState<ChangeRecord | null>(null);
  const [isReverting, setIsReverting] = useState(false);
  const [revertError, setRevertError] = useState<string | null>(null);

  // Export Modal State
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<"markdown" | "plain_text" | "json" | "pdf">("pdf");
  const [exportData, setExportData] = useState<ExportTargetedResumeResponse | null>(null);
  const [isExportLoading, setIsExportLoading] = useState(false);
  const [exportCopied, setExportCopied] = useState(false);
  const [isPdfDownloading, setIsPdfDownloading] = useState(false);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewError, setPdfPreviewError] = useState<string | null>(null);
  const [isPdfLoading, setIsPdfLoading] = useState(false);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Fetch variant from backend
  const fetchVariant = useCallback(async (showRefreshing = false) => {
    if (!user || !variantId) return;
    if (showRefreshing) setIsRefreshing(true);
    else setIsLoading(true);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || "Failed to load targeted variant.");
      }

      setVariant(data);
    } catch (err: any) {
      setErrorMessage(err.message || "Could not load targeted variant.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [user, variantId]);

  // Fetch fit comparison from backend
  const fetchFitComparison = useCallback(async () => {
    if (!user || !variantId) return;
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/fit-comparison`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setFitComparison(data);
      }
    } catch (err) {
      console.warn("Could not load fit comparison:", err);
    }
  }, [user, variantId]);

  useEffect(() => {
    fetchVariant();
    fetchFitComparison();
  }, [fetchVariant, fetchFitComparison]);

  // Clean up PDF object URL on unmount or format change
  const cleanupPdfPreview = useCallback(() => {
    if (pdfPreviewUrl) {
      URL.revokeObjectURL(pdfPreviewUrl);
      setPdfPreviewUrl(null);
    }
  }, [pdfPreviewUrl]);

  // Handle Export Fetch & PDF Preview Generation
  const handleOpenExport = async (format: "markdown" | "plain_text" | "json" | "pdf" = exportFormat) => {
    if (!user || !variantId) return;
    setExportFormat(format);
    setIsExportModalOpen(true);
    setExportCopied(false);

    if (format === "pdf") {
      setIsExportLoading(false);
      if (!pdfPreviewUrl) {
        setIsPdfLoading(true);
        setPdfPreviewError(null);
        try {
          const idToken = await user.getIdToken();
          const res = await fetch(`/api/variants/${variantId}/export/pdf?template=ats`, {
            headers: { Authorization: `Bearer ${idToken}` },
          });

          if (!res.ok) {
            throw new Error("Failed to generate PDF preview from server.");
          }

          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          setPdfPreviewUrl(url);
        } catch (err: any) {
          setPdfPreviewError(err.message || "Could not load PDF preview.");
        } finally {
          setIsPdfLoading(false);
        }
      }
      return;
    }

    setIsExportLoading(true);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/export?format=${format}`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || "Failed to export variant.");
      }
      setExportData(data);
    } catch (err: any) {
      console.error("Export error:", err);
    } finally {
      setIsExportLoading(false);
    }
  };

  // --- 1. Manual Edit Handlers ---
  const openManualEditModal = (
    section: "Summary" | "Experience" | "Project",
    itemId: string,
    bulletIndex?: number,
    currentText = ""
  ) => {
    setManualEditSection(section);
    setManualEditTargetItemId(itemId);
    setManualEditTargetBulletIndex(bulletIndex);
    setManualEditText(currentText);
    setManualEditError(null);
    setIsManualEditModalOpen(true);
  };

  const handleSaveManualEdit = async () => {
    if (!user || !variantId) return;
    if (!manualEditText.trim()) {
      setManualEditError("Content cannot be empty.");
      return;
    }

    setIsSavingManualEdit(true);
    setManualEditError(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/apply-change`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          requirementName: "Manual Edit",
          section: manualEditSection,
          targetItemId: manualEditTargetItemId,
          targetBulletIndex: manualEditTargetBulletIndex,
          approvedBullet: manualEditText.trim(),
          actionType: "ManualEdit",
          expectedVersion: variant?.version,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error("Concurrency conflict: this resume variant was modified elsewhere. Please sync and retry.");
        }
        throw new Error(data.detail || data.error || "Failed to save manual edit.");
      }

      setIsManualEditModalOpen(false);
      showToast(`Manual edit saved! Version updated to v${data.newVersion}.`, "success");
      await fetchVariant(true);
      await fetchFitComparison();
    } catch (err: any) {
      setManualEditError(err.message || "Failed to save manual edit.");
    } finally {
      setIsSavingManualEdit(false);
    }
  };

  // --- 2. AI Edit & Proposal Handlers ---
  const openAiEditModal = (
    section: "Summary" | "Experience" | "Project",
    itemId: string,
    bulletIndex?: number,
    currentText = ""
  ) => {
    setAiEditSection(section);
    setAiEditTargetItemId(itemId);
    setAiEditTargetBulletIndex(bulletIndex);
    setAiEditOriginalText(currentText);
    setAiEditInstruction("");
    setAiProposal(null);
    setConfirmAttestation(false);
    setAiEditError(null);
    setIsAiEditModalOpen(true);
  };

  const handleGenerateAiProposal = async () => {
    if (!user || !variantId) return;
    if (!aiEditInstruction.trim()) {
      setAiEditError("Please enter an instruction for the AI editor.");
      return;
    }

    setIsGeneratingProposal(true);
    setAiEditError(null);
    setAiProposal(null);
    setConfirmAttestation(false);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/ai-edit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          instruction: aiEditInstruction.trim(),
          targetItemId: aiEditTargetItemId,
          targetBulletIndex: aiEditTargetBulletIndex,
          expectedVersion: variant?.version,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error("Version conflict: the resume was modified in another session. Please refresh.");
        }
        if (res.status === 504) {
          throw new Error("AI request timed out. Please try a simpler instruction.");
        }
        throw new Error(data.detail || data.error || "Failed to generate AI edit proposal.");
      }

      setAiProposal(data);
    } catch (err: any) {
      setAiEditError(err.message || "Failed to generate AI proposal.");
    } finally {
      setIsGeneratingProposal(false);
    }
  };

  const handleAcceptAiProposal = async () => {
    if (!user || !variantId || !aiProposal) return;

    if (aiProposal.requiresConfirmation && !confirmAttestation) {
      setAiEditError("Please confirm that the newly introduced facts are true and user-attested before applying.");
      return;
    }

    setIsApplyingProposal(true);
    setAiEditError(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/apply-change`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          requirementName: aiProposal.requiresConfirmation ? "User-Attested AI Customization" : "AI Tailored Edit",
          section: aiEditSection,
          targetItemId: aiEditTargetItemId,
          targetBulletIndex: aiEditTargetBulletIndex,
          approvedBullet: aiProposal.proposedText,
          actionType: aiProposal.requiresConfirmation ? "UserAttested" : "ApplyRemediation",
          confirmUserAttested: aiProposal.requiresConfirmation,
          expectedVersion: variant?.version,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error("Conflict: target resume bullet or version has been updated. Please sync and retry.");
        }
        throw new Error(data.detail || data.error || "Failed to apply AI proposal.");
      }

      setIsAiEditModalOpen(false);
      setAiProposal(null);
      showToast(`AI proposal accepted and applied! Variant is now at v${data.newVersion}.`, "success");
      await fetchVariant(true);
      await fetchFitComparison();
    } catch (err: any) {
      setAiEditError(err.message || "Failed to apply proposal.");
    } finally {
      setIsApplyingProposal(false);
    }
  };

  // --- 3. Direct Remediation Apply Handlers ---
  const openApplyModal = (
    section: "Experience" | "Project" | "Summary" = "Experience",
    targetItemId?: string,
    targetBulletIdx?: number
  ) => {
    setApplyRequirementName("");
    setApplyApprovedBullet("");
    setApplySection(section);
    const available =
      section === "Experience"
        ? variant?.snapshot?.experience || []
        : variant?.snapshot?.projects || [];
    const defaultId =
      targetItemId ||
      (available[0] as any)?.id ||
      (section === "Experience" ? "exp_0" : section === "Project" ? "proj_0" : "summary");
    setApplyTargetItemId(defaultId);
    setApplyTargetBulletIndex(
      typeof targetBulletIdx === "number" ? targetBulletIdx : 0
    );
    setApplyError(null);
    setIsApplyModalOpen(true);
  };

  const handleSectionChange = (section: "Experience" | "Project" | "Summary") => {
    setApplySection(section);
    const available =
      section === "Experience"
        ? variant?.snapshot?.experience || []
        : variant?.snapshot?.projects || [];
    const defaultId =
      (available[0] as any)?.id ||
      (section === "Experience" ? "exp_0" : section === "Project" ? "proj_0" : "summary");
    setApplyTargetItemId(defaultId);
    setApplyTargetBulletIndex(0);
  };

  const handleApplyChangeSubmit = async () => {
    if (!user || !variantId) return;
    if (!applyApprovedBullet.trim()) {
      setApplyError("Approved bullet text cannot be empty.");
      return;
    }
    if (applyApprovedBullet.trim().length > 2000) {
      setApplyError("Approved bullet text exceeds maximum length of 2,000 characters.");
      return;
    }

    setIsApplying(true);
    setApplyError(null);

    try {
      const idToken = await user.getIdToken();
      const targetId =
        applyTargetItemId ||
        (applySection === "Experience" ? "exp_0" : applySection === "Project" ? "proj_0" : "summary");

      const res = await fetch(`/api/variants/${variantId}/apply-change`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          requirementName: applyRequirementName.trim() || "Target Requirement",
          section: applySection,
          targetItemId: targetId,
          targetBulletIndex: Math.max(0, applyTargetBulletIndex),
          approvedBullet: applyApprovedBullet.trim(),
          remediationId: applyRemediationId.trim() || undefined,
          expectedVersion: variant?.version,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error(data.detail || "Conflict: target resume bullet or version has been altered. Please refresh and re-check before applying.");
        }
        throw new Error(data.detail || data.error || "Failed to apply change.");
      }

      setIsApplyModalOpen(false);
      setApplyApprovedBullet("");
      setApplyRequirementName("");
      showToast(`Change applied! Variant incremented to v${data.newVersion}.`, "success");
      await fetchVariant(true);
      await fetchFitComparison();
    } catch (err: any) {
      setApplyError(err.message || "Failed to apply change.");
    } finally {
      setIsApplying(false);
    }
  };

  // --- 4. Revert Change Handler ---
  const handleRevertConfirm = async () => {
    if (!user || !variantId || !revertingChange) return;

    setIsReverting(true);
    setRevertError(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/revert-change`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          changeId: revertingChange.id,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || "Failed to revert change.");
      }

      setRevertingChange(null);
      showToast(`Change reverted. Variant incremented to v${data.newVersion}.`, "success");
      await fetchVariant(true);
      await fetchFitComparison();
    } catch (err: any) {
      setRevertError(err.message || "Failed to revert change.");
    } finally {
      setIsReverting(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!user || !variantId) return;
    setIsPdfDownloading(true);
    try {
      const idToken = await user.getIdToken();
      const res = await fetch(`/api/variants/${variantId}/export/pdf?template=ats`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!res.ok) {
        throw new Error("Failed to download PDF export.");
      }
      const blob = await res.blob();
      const contentDisposition = res.headers.get("content-disposition");
      let filename = `${variant?.title?.replace(/[^a-zA-Z0-9_-]/g, "_") || "targeted_resume"}_v${variant?.version || 1}.pdf`;
      if (contentDisposition && contentDisposition.includes("filename=")) {
        const match = contentDisposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) filename = match[1];
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      showToast("PDF exported successfully", "success");
    } catch (err: any) {
      console.error("PDF download error:", err);
      showToast("Failed to download PDF. Please try again.", "error");
    } finally {
      setIsPdfDownloading(false);
    }
  };

  const handleCopyExport = () => {
    if (exportData?.content) {
      navigator.clipboard.writeText(exportData.content);
      setExportCopied(true);
      showToast("Export copied to clipboard", "info");
      setTimeout(() => setExportCopied(false), 2000);
    }
  };

  const handleDownloadExport = () => {
    if (!exportData) return;
    const ext = exportFormat === "markdown" ? "md" : exportFormat === "json" ? "json" : "txt";
    const filename = `${variant?.title.replace(/[^a-zA-Z0-9_-]/g, "_") || "targeted_resume"}_v${variant?.version}.${ext}`;
    const blob = new Blob([exportData.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    if (exportFormat === "markdown") {
      showToast("Markdown exported successfully", "success");
    } else if (exportFormat === "plain_text") {
      showToast("Text export downloaded", "success");
    } else {
      showToast("JSON exported successfully", "success");
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4 py-8">
        <LoadingState text="Loading targeted resume variant and ledger..." />
      </div>
    );
  }

  if (errorMessage || !variant) {
    return (
      <div className="space-y-6 py-6 max-w-2xl mx-auto">
        <ErrorAlert
          title="Targeted Variant Error"
          message={errorMessage || "Targeted resume variant not found or inaccessible."}
          onRetry={() => fetchVariant()}
        />
        <div className="flex justify-center">
          <Link href="/resumes">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Saved Resumes</span>
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const snapshot = variant.snapshot || {};
  const changeLedger = variant.changeLedger || variant.change_ledger || [];
  const appliedCount = changeLedger.filter((c) => c.status === "Applied").length;
  const revertedCount = changeLedger.filter((c) => c.status === "Reverted").length;
  const targetRole = variant.targetRole || variant.target_role;
  const targetCompany = variant.targetCompany || variant.target_company;
  const variantIdStr = variant.variantId || variant.variant_id || variantId;
  const updatedAtStr = variant.updatedAt || variant.updated_at;
  const currentScoreVal = variant.currentScore ?? variant.current_score ?? variant.baselineScore ?? variant.baseline_score ?? 0;
  const scoreDeltaVal = variant.scoreDelta ?? variant.score_delta;
  const activeBreakdown = variant.currentBreakdown || variant.current_breakdown || variant.baselineBreakdown || variant.baseline_breakdown;

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Notification Banner */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 animate-in fade-in slide-in-from-top-2">
          <ToastBanner message={toast.message} type={toast.type} className="shadow-lg" />
        </div>
      )}

      {/* Breadcrumb & Top Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/70 pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-caption text-secondary">
            <Link href="/resumes" className="hover:text-primary transition-colors flex items-center gap-1">
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Resumes</span>
            </Link>
            <span>/</span>
            <span className="text-primary font-medium">Targeted Variant</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-0.5">
            <h1 className="text-h1 font-bold text-primary">{variant.title}</h1>
            <Badge variant="outline" className="bg-accent/10 border-accent/30 text-accent font-semibold px-2 py-0.5 text-xs">
              v{variant.version}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-secondary pt-0.5">
            <span className="flex items-center gap-1">
              <Briefcase className="h-3.5 w-3.5 text-muted" />
              <strong>Role:</strong> {targetRole}
            </span>
            {targetCompany && (
              <span className="flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5 text-muted" />
                <strong>Company:</strong> {targetCompany}
              </span>
            )}
            <span className="flex items-center gap-1 text-caption text-muted">
              <Calendar className="h-3.5 w-3.5" />
              Updated {formatDate(updatedAtStr || "")}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchVariant(true)}
            disabled={isRefreshing}
            className="gap-1.5"
            title="Refresh variant state from backend"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin text-accent" : ""}`} />
            <span>Sync</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleOpenExport("pdf")}
            className="gap-1.5"
          >
            <Download className="h-3.5 w-3.5 text-secondary" />
            <span>Export</span>
          </Button>

          <Link href={`/analyzer?resumeId=${variantIdStr}`}>
            <Button variant="primary" size="sm" className="gap-1.5 shadow-subtle">
              <Zap className="h-3.5 w-3.5" />
              <span>Run ATS Audit</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* ATS Performance Card */}
      <Card className="bg-surface border-border shadow-subtle">
        <CardContent className="p-5">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Main Score Comparison */}
            <div className="md:col-span-1 border-b md:border-b-0 md:border-r border-border/80 pb-4 md:pb-0 pr-0 md:pr-4 space-y-1 text-center md:text-left">
              <span className="text-caption font-semibold uppercase tracking-wider text-muted">
                ATS Alignment Score
              </span>
              <div className="flex items-baseline justify-center md:justify-start gap-3">
                <span className="text-3xl font-extrabold text-primary">
                  {currentScoreVal}%
                </span>
                {typeof scoreDeltaVal === "number" && (
                  <Badge
                    variant={scoreDeltaVal > 0 ? "success" : "secondary"}
                    className="font-bold text-xs"
                  >
                    {scoreDeltaVal > 0 ? `+${scoreDeltaVal}%` : `${scoreDeltaVal}%`} Delta
                  </Badge>
                )}
              </div>
              <p className="text-caption text-secondary">
                Baseline: {variant.baselineScore ?? variant.baseline_score ?? 0}% (Version v1)
              </p>
            </div>

            {/* Score Breakdown Bars */}
            <div className="md:col-span-3 grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-1 bg-page/60 p-2.5 rounded-btn border border-border/60">
                <span className="text-caption text-muted font-medium">Relevance</span>
                <div className="text-body font-bold text-primary">
                  {activeBreakdown?.relevance ?? 0}%
                </div>
                <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full"
                    style={{ width: `${activeBreakdown?.relevance ?? 0}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1 bg-page/60 p-2.5 rounded-btn border border-border/60">
                <span className="text-caption text-muted font-medium">Keywords</span>
                <div className="text-body font-bold text-primary">
                  {activeBreakdown?.keywords ?? 0}%
                </div>
                <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-status-success rounded-full"
                    style={{ width: `${activeBreakdown?.keywords ?? 0}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1 bg-page/60 p-2.5 rounded-btn border border-border/60">
                <span className="text-caption text-muted font-medium">Metrics & Impact</span>
                <div className="text-body font-bold text-primary">
                  {activeBreakdown?.metrics ?? 0}%
                </div>
                <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full"
                    style={{ width: `${activeBreakdown?.metrics ?? 0}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1 bg-page/60 p-2.5 rounded-btn border border-border/60">
                <span className="text-caption text-muted font-medium">Formatting</span>
                <div className="text-body font-bold text-primary">
                  {activeBreakdown?.formatting ?? 0}%
                </div>
                <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{ width: `${activeBreakdown?.formatting ?? 0}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Tabs Navigation */}
      <div className="flex overflow-x-auto border-b border-border scrollbar-none">
        <button
          onClick={() => setActiveTab("snapshot")}
          className={`px-4 py-2.5 text-small font-semibold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap shrink-0 ${
            activeTab === "snapshot"
              ? "border-accent text-accent"
              : "border-transparent text-secondary hover:text-primary"
          }`}
        >
          <FileText className="h-4 w-4" />
          <span>Resume Snapshot & Editor</span>
        </button>

        <button
          onClick={() => setActiveTab("ledger")}
          className={`px-4 py-2.5 text-small font-semibold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap shrink-0 ${
            activeTab === "ledger"
              ? "border-accent text-accent"
              : "border-transparent text-secondary hover:text-primary"
          }`}
        >
          <History className="h-4 w-4" />
          <span>Change History & Ledger</span>
          <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0.2">
            {changeLedger.length}
          </Badge>
        </button>

        <button
          onClick={() => setActiveTab("comparison")}
          className={`px-4 py-2.5 text-small font-semibold border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap shrink-0 ${
            activeTab === "comparison"
              ? "border-accent text-accent"
              : "border-transparent text-secondary hover:text-primary"
          }`}
        >
          <TrendingUp className="h-4 w-4" />
          <span>Fit Progression</span>
          {fitComparison && (
            <Badge variant={(fitComparison.totalGapsResolved ?? fitComparison.total_gaps_resolved ?? 0) > 0 ? "success" : "outline"} className="ml-1 text-[10px] px-1.5 py-0.2">
              {fitComparison.totalGapsResolved ?? fitComparison.total_gaps_resolved ?? 0} Resolved
            </Badge>
          )}
        </button>
      </div>

      {/* Tab 1: Resume Snapshot & Editor */}
      {activeTab === "snapshot" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-h2 font-semibold text-primary">Targeted Snapshot (Version {variant.version})</h3>
              <p className="text-small text-secondary">
                Edit content or request fact-grounded AI enhancements. Master profile remains unchanged.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => openApplyModal("Experience")}
                className="gap-1.5"
              >
                <Plus className="h-4 w-4" />
                <span>Add Custom Bullet</span>
              </Button>
            </div>
          </div>

          <Card className="border-border shadow-subtle divide-y divide-border/60">
            {/* Header & Summary Section */}
            <div className="p-6 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-primary">{snapshot.headline || variant.title}</h2>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openManualEditModal("Summary", "summary", undefined, snapshot.summary || snapshot.headline || "")}
                    className="h-7 px-2 text-xs gap-1 text-secondary hover:text-primary"
                    title="Manually edit executive summary"
                  >
                    <Pencil className="h-3 w-3" />
                    <span>Edit</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openAiEditModal("Summary", "summary", undefined, snapshot.summary || snapshot.headline || "")}
                    className="h-7 px-2 text-xs gap-1 border-accent/40 text-accent hover:bg-accent-soft"
                    title="Refine executive summary with AI"
                  >
                    <Sparkles className="h-3 w-3" />
                    <span>AI Refine</span>
                  </Button>
                </div>
              </div>

              {snapshot.summary ? (
                <p className="text-body text-secondary leading-relaxed bg-page/40 p-3 rounded-btn border border-border/40">
                  {snapshot.summary}
                </p>
              ) : (
                <p className="text-small text-muted italic">No custom summary provided for this variant.</p>
              )}
            </div>

            {/* Experience Section */}
            {snapshot.experience && snapshot.experience.length > 0 && (
              <div className="p-6 space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Briefcase className="h-4 w-4 text-accent" />
                    <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                      Professional Experience
                    </h4>
                  </div>
                </div>

                <div className="space-y-6">
                  {snapshot.experience.map((exp: any, idx: number) => {
                    const itemId = exp.id || `exp_${idx}`;
                    return (
                      <div key={idx} className="space-y-2 border-b border-border/40 pb-4 last:border-b-0 last:pb-0">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                          <div>
                            <strong className="text-body font-semibold text-primary">{exp.role}</strong>
                            <span className="text-secondary"> &mdash; {exp.company}</span>
                            {exp.location && <span className="text-caption text-muted ml-2">({exp.location})</span>}
                          </div>
                          <div className="flex items-center gap-2">
                            {(exp.startDate || exp.endDate) && (
                              <span className="text-caption text-muted">
                                {exp.startDate} – {exp.isCurrent ? "Present" : exp.endDate}
                              </span>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openApplyModal("Experience", itemId, exp.bullets.length)}
                              className="h-6 px-1.5 text-[11px] text-muted hover:text-primary gap-1"
                              title="Add new bullet point"
                            >
                              <Plus className="h-3 w-3" />
                              <span>Add Bullet</span>
                            </Button>
                          </div>
                        </div>

                        <ul className="list-disc list-outside ml-5 space-y-2 text-body text-secondary">
                          {exp.bullets.map((b: string, bIdx: number) => {
                            const isModified = changeLedger.some(
                              (c) =>
                                c.section === "Experience" &&
                                c.status === "Applied" &&
                                (c.approvedText === b || c.approved_text === b)
                            );
                            return (
                              <li
                                key={bIdx}
                                className={`group transition-all ${
                                  isModified
                                    ? "text-primary font-medium bg-status-success-soft/40 p-2 rounded -ml-2 border-l-2 border-status-success"
                                    : "hover:text-primary"
                                }`}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <span>{b}</span>
                                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 shrink-0">
                                    <button
                                      type="button"
                                      onClick={() => openManualEditModal("Experience", itemId, bIdx, b)}
                                      className="p-1 rounded text-secondary hover:text-primary hover:bg-page"
                                      title="Manually edit bullet"
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => openAiEditModal("Experience", itemId, bIdx, b)}
                                      className="p-1 rounded text-accent hover:bg-accent-soft"
                                      title="AI rewrite / refine bullet"
                                    >
                                      <Sparkles className="h-3 w-3" />
                                    </button>
                                  </div>
                                </div>
                              </li>
                            );
                          })}
                        </ul>

                        {exp.technologies && exp.technologies.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {exp.technologies.map((t: string, tIdx: number) => (
                              <Badge key={tIdx} variant="secondary" className="text-[10px]">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Projects Section */}
            {snapshot.projects && snapshot.projects.length > 0 && (
              <div className="p-6 space-y-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Code2 className="h-4 w-4 text-accent" />
                    <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                      Key Projects & Technical Highlights
                    </h4>
                  </div>
                </div>

                <div className="space-y-5">
                  {snapshot.projects.map((proj: any, idx: number) => {
                    const itemId = proj.id || `proj_${idx}`;
                    const highlights = proj.highlights || proj.bullets || [];
                    return (
                      <div key={idx} className="space-y-2 border-b border-border/40 pb-4 last:border-b-0 last:pb-0">
                        <div className="flex items-center justify-between">
                          <div>
                            <strong className="text-body font-semibold text-primary">{proj.title}</strong>
                            {proj.role && <span className="text-caption text-muted ml-2">({proj.role})</span>}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openApplyModal("Project", itemId, highlights.length)}
                            className="h-6 px-1.5 text-[11px] text-muted hover:text-primary gap-1"
                            title="Add highlight"
                          >
                            <Plus className="h-3 w-3" />
                            <span>Add Highlight</span>
                          </Button>
                        </div>

                        {proj.description && <p className="text-small text-secondary">{proj.description}</p>}

                        <ul className="list-disc list-outside ml-5 space-y-2 text-body text-secondary">
                          {highlights.map((hl: string, hlIdx: number) => {
                            const isModified = changeLedger.some(
                              (c) =>
                                c.section === "Project" &&
                                c.status === "Applied" &&
                                (c.approvedText === hl || c.approved_text === hl)
                            );
                            return (
                              <li
                                key={hlIdx}
                                className={`group transition-all ${
                                  isModified
                                    ? "text-primary font-medium bg-status-success-soft/40 p-2 rounded -ml-2 border-l-2 border-status-success"
                                    : "hover:text-primary"
                                }`}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <span>{hl}</span>
                                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 shrink-0">
                                    <button
                                      type="button"
                                      onClick={() => openManualEditModal("Project", itemId, hlIdx, hl)}
                                      className="p-1 rounded text-secondary hover:text-primary hover:bg-page"
                                      title="Manually edit highlight"
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => openAiEditModal("Project", itemId, hlIdx, hl)}
                                      className="p-1 rounded text-accent hover:bg-accent-soft"
                                      title="AI rewrite / refine highlight"
                                    >
                                      <Sparkles className="h-3 w-3" />
                                    </button>
                                  </div>
                                </div>
                              </li>
                            );
                          })}
                        </ul>

                        {(proj.techStack || proj.technologies) && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {(proj.techStack || proj.technologies).map((t: string, tIdx: number) => (
                              <Badge key={tIdx} variant="secondary" className="text-[10px]">
                                {t}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Skills Section */}
            {snapshot.skills && snapshot.skills.length > 0 && (
              <div className="p-6 space-y-2">
                <div className="flex items-center gap-2">
                  <ListChecks className="h-4 w-4 text-accent" />
                  <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                    Technical Skills & Tools
                  </h4>
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {snapshot.skills.map((s: any, idx: number) => (
                    <Badge key={idx} variant="outline" className="text-small">
                      {s.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Education Section */}
            {snapshot.education && snapshot.education.length > 0 && (
              <div className="p-6 space-y-3">
                <div className="flex items-center gap-2">
                  <GraduationCap className="h-4 w-4 text-accent" />
                  <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                    Education
                  </h4>
                </div>
                <div className="space-y-2">
                  {snapshot.education.map((ed: any, idx: number) => (
                    <div key={idx} className="text-small text-secondary flex items-baseline justify-between">
                      <div>
                        <strong className="text-primary">{ed.degree || "Degree"}</strong> &mdash; {ed.institution}
                        {ed.fieldOfStudy && <span className="text-muted ml-1">in {ed.fieldOfStudy}</span>}
                      </div>
                      {(ed.startDate || ed.endDate) && (
                        <span className="text-caption text-muted">
                          {ed.startDate} – {ed.endDate}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Certifications Section */}
            {snapshot.certifications && snapshot.certifications.length > 0 && (
              <div className="p-6 space-y-3">
                <div className="flex items-center gap-2">
                  <Award className="h-4 w-4 text-accent" />
                  <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                    Certifications & Credentials
                  </h4>
                </div>
                <div className="space-y-2">
                  {snapshot.certifications.map((c: any, idx: number) => (
                    <div key={idx} className="text-small text-secondary flex items-baseline justify-between">
                      <div>
                        <strong className="text-primary">{c.title}</strong>
                        {c.issuer && <span className="text-muted ml-1">&mdash; {c.issuer}</span>}
                      </div>
                      {c.issueDate && (
                        <span className="text-caption text-muted">
                          {c.issueDate}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Tab 2: Change History & Ledger */}
      {activeTab === "ledger" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-h2 font-semibold text-primary">Immutable Change Ledger</h3>
              <p className="text-small text-secondary">
                Track every remediation, direct edit, and revert event across version history.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="success">{appliedCount} Applied</Badge>
              <Badge variant="outline">{revertedCount} Reverted</Badge>
            </div>
          </div>

          {changeLedger.length === 0 ? (
            <EmptyState
              title="No changes recorded"
              description="This targeted variant is currently identical to the source master resume. Apply remediation suggestions or edits to create new versions."
              icon={History}
            />
          ) : (
            <div className="space-y-4">
              {changeLedger.map((chg) => {
                const isReverted = chg.status === "Reverted";
                return (
                  <Card
                    key={chg.id}
                    className={`transition-all border ${
                      isReverted ? "border-border/50 bg-page/40 opacity-75" : "border-border shadow-subtle"
                    }`}
                  >
                    <CardContent className="p-5 space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-2.5">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={isReverted ? "outline" : "success"}
                            className="font-bold text-xs"
                          >
                            {chg.status}
                          </Badge>
                          <span className="text-caption font-mono text-muted">{chg.id}</span>
                          <span className="text-caption text-secondary">&bull;</span>
                          <span className="text-small font-semibold text-primary">{chg.requirementName || chg.requirement_name}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px]">
                            {chg.section} Section
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            v{chg.versionIntroduced || chg.version_introduced}
                          </Badge>
                          {!isReverted && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setRevertingChange(chg);
                                setRevertError(null);
                              }}
                              className="text-status-error hover:bg-status-error-soft text-xs h-7 px-2 gap-1"
                            >
                              <Undo2 className="h-3 w-3" />
                              <span>Revert</span>
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Diff view */}
                      <div className="space-y-2 text-small">
                        {(chg.originalText || chg.original_text) && (
                          <div className="space-y-1">
                            <span className="text-caption font-bold text-status-error/80 uppercase">
                              Original Baseline Text:
                            </span>
                            <div className="p-2.5 rounded bg-status-error-soft/30 text-secondary border border-status-error/20 line-through">
                              {chg.originalText || chg.original_text}
                            </div>
                          </div>
                        )}

                        <div className="space-y-1">
                          <span className="text-caption font-bold text-status-success uppercase">
                            {isReverted ? "Reverted Text:" : "Approved & Applied Text:"}
                          </span>
                          <div className="p-2.5 rounded bg-status-success-soft/30 text-primary font-medium border border-status-success/30">
                            {chg.approvedText || chg.approved_text}
                          </div>
                        </div>
                      </div>

                      {/* Timestamps */}
                      <div className="flex flex-wrap items-center gap-x-4 text-caption text-muted pt-1">
                        <span>Applied: {formatDate(chg.appliedAt || chg.applied_at || "")}</span>
                        {(chg.revertedAt || chg.reverted_at) && (
                          <span className="text-status-error">
                            Reverted: {formatDate(chg.revertedAt || chg.reverted_at || "")} in v{chg.versionReverted || chg.version_introduced || "N/A"}
                          </span>
                        )}
                        {(chg.remediationId || chg.remediation_id) && (
                          <span>Source Remediation: {chg.remediationId || chg.remediation_id}</span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Fit Progression */}
      {activeTab === "comparison" && (
        <div className="space-y-6">
          <div>
            <h3 className="text-h2 font-semibold text-primary">Before / After Fit Progression</h3>
            <p className="text-small text-secondary">
              Derived strictly from stored baseline and current analysis snapshots.
            </p>
          </div>

          {!fitComparison ? (
            <LoadingState text="Loading requirement progression analysis..." />
          ) : (
            <div className="space-y-6">
              {/* Top Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card className="p-4 border-border shadow-subtle space-y-1">
                  <span className="text-caption text-muted font-semibold uppercase">Total Gaps Resolved</span>
                  <div className="text-2xl font-bold text-status-success">
                    {fitComparison.totalGapsResolved ?? fitComparison.total_gaps_resolved ?? 0}
                  </div>
                  <p className="text-caption text-secondary">Missing or partial requirements elevated</p>
                </Card>

                <Card className="p-4 border-border shadow-subtle space-y-1">
                  <span className="text-caption text-muted font-semibold uppercase">Gaps Remaining</span>
                  <div className="text-2xl font-bold text-amber-500">
                    {fitComparison.totalGapsRemaining ?? fitComparison.total_gaps_remaining ?? 0}
                  </div>
                  <p className="text-caption text-secondary">Unchanged gaps or hard constraints</p>
                </Card>

                <Card className="p-4 border-border shadow-subtle space-y-1">
                  <span className="text-caption text-muted font-semibold uppercase">Actual ATS Delta</span>
                  <div className="text-2xl font-bold text-accent">
                    {(fitComparison.scoreDelta ?? fitComparison.score_delta ?? 0) > 0
                      ? `+${fitComparison.scoreDelta ?? fitComparison.score_delta}%`
                      : `${fitComparison.scoreDelta ?? fitComparison.score_delta ?? 0}%`}
                  </div>
                  <p className="text-caption text-secondary">
                    {fitComparison.baselineScore ?? fitComparison.baseline_score ?? 0}% &rarr; {fitComparison.currentScore ?? fitComparison.current_score ?? 0}%
                  </p>
                </Card>
              </div>

              {/* Requirements Progression List */}
              {(() => {
                const progressions = fitComparison.requirementProgressions || fitComparison.requirement_progressions || [];
                return (
                  <div className="space-y-3">
                    <h4 className="text-small font-bold uppercase tracking-wider text-muted">
                      Requirement Progression Matrix ({progressions.length})
                    </h4>

                    {progressions.length === 0 ? (
                      <EmptyState
                        title="No requirement progressions recorded yet"
                        description="Run an ATS Deep Scan on this targeted variant to observe requirement status transitions and gap elevations."
                        icon={TrendingUp}
                      />
                    ) : (
                      <div className="space-y-2">
                        {progressions.map((prog, idx) => {
                          const isResolved = prog.progression === "Resolved";
                          const isImproved = prog.progression === "Improved";
                          const isHardGap = prog.progression === "UnresolvedHardGap";
                          const reqName = prog.requirementName || prog.requirement_name;
                          const baseStatus = prog.baselineStatus || prog.baseline_status;
                          const currStatus = prog.currentStatus || prog.current_status;
                          const evidence = prog.verifiedEvidence || prog.verified_evidence;

                          return (
                            <div
                              key={idx}
                              className="p-4 rounded-card border border-border bg-surface flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                            >
                              <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                  <strong className="text-body font-semibold text-primary">
                                    {reqName}
                                  </strong>
                                  <Badge variant="outline" className="text-[10px]">
                                    {prog.category}
                                  </Badge>
                                  {prog.importance === "MustHave" && (
                                    <Badge variant="secondary" className="text-[10px] text-amber-600">
                                      Must Have
                                    </Badge>
                                  )}
                                </div>

                                <div className="flex items-center gap-2 text-small text-secondary">
                                  <span>{baseStatus}</span>
                                  <span>&rarr;</span>
                                  <span className="font-semibold text-primary">{currStatus}</span>
                                </div>

                                {evidence && (
                                  <p className="text-caption text-muted italic">
                                    Evidence: &ldquo;{evidence}&rdquo;
                                  </p>
                                )}
                              </div>

                              <Badge
                                variant={
                                  isResolved
                                    ? "success"
                                    : isImproved
                                    ? "accent"
                                    : isHardGap
                                    ? "outline"
                                    : "secondary"
                                }
                                className="self-start sm:self-center uppercase font-bold text-xs"
                              >
                                {prog.progression}
                              </Badge>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* Manual Edit Modal */}
      {isManualEditModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsManualEditModalOpen(false)}
          title="Manual Content Edit"
          description="Directly edit this resume section. Your changes will create a new variant version without calling an LLM."
          maxWidth="md"
        >
          <div className="space-y-4">
            {manualEditError && <ErrorAlert message={manualEditError} />}

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Content</label>
              <Textarea
                rows={4}
                value={manualEditText}
                onChange={(e) => setManualEditText(e.target.value)}
                placeholder="Enter exact content..."
                className="text-small"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border/60">
              <Button variant="ghost" onClick={() => setIsManualEditModalOpen(false)} disabled={isSavingManualEdit}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveManualEdit} disabled={isSavingManualEdit}>
                {isSavingManualEdit ? "Saving..." : `Save & Increment to v${variant.version + 1}`}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* AI Edit & Proposal Modal */}
      {isAiEditModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => {
            setIsAiEditModalOpen(false);
            setAiProposal(null);
          }}
          title="AI Bullet & Section Editor"
          description="Request targeted refinement, shortening, or fact-grounded rewording. Review the proposal before applying."
          maxWidth="lg"
        >
          <div className="space-y-5">
            {aiEditError && <ErrorAlert message={aiEditError} />}

            {/* Original Text Reference */}
            <div className="p-3 rounded bg-page border border-border space-y-1">
              <span className="text-caption font-semibold uppercase tracking-wider text-muted">
                Original Text:
              </span>
              <p className="text-small text-secondary italic">
                &ldquo;{aiEditOriginalText}&rdquo;
              </p>
            </div>

            {/* Instruction Input */}
            <div className="space-y-2">
              <label className="text-small font-medium text-primary">Edit Instruction</label>
              <div className="flex gap-2">
                <Input
                  value={aiEditInstruction}
                  onChange={(e) => setAiEditInstruction(e.target.value)}
                  placeholder="e.g. Make shorter, emphasize metrics, add PostgreSQL optimization..."
                  disabled={isGeneratingProposal || isApplyingProposal}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleGenerateAiProposal();
                    }
                  }}
                />
                <Button
                  variant="primary"
                  onClick={handleGenerateAiProposal}
                  disabled={isGeneratingProposal || !aiEditInstruction.trim()}
                  className="gap-1.5 shrink-0"
                >
                  <Wand2 className={`h-4 w-4 ${isGeneratingProposal ? "animate-spin" : ""}`} />
                  <span>{isGeneratingProposal ? "Generating..." : "Propose Edit"}</span>
                </Button>
              </div>
            </div>

            {/* Proposal Card (Rendered only when proposal is returned) */}
            {aiProposal && (
              <div className="space-y-4 border border-border rounded-card p-4 bg-surface shadow-subtle animate-in fade-in">
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-accent" />
                    <span className="text-body font-bold text-primary">AI Edit Proposal</span>
                  </div>
                  <Badge variant={aiProposal.validation.isValid ? "success" : "secondary"}>
                    {aiProposal.validation.isValid ? "Fact Validated" : "Requires Confirmation"}
                  </Badge>
                </div>

                {/* Proposed Text */}
                <div className="space-y-1">
                  <span className="text-caption font-semibold text-status-success uppercase">
                    Proposed Text:
                  </span>
                  <div className="p-3 rounded bg-status-success-soft/30 border border-status-success/30 text-body font-medium text-primary">
                    {aiProposal.proposedText}
                  </div>
                </div>

                {/* Diff Representation */}
                {aiProposal.diff && (
                  <div className="space-y-1">
                    <span className="text-caption font-semibold text-muted uppercase">
                      Changes / Diff:
                    </span>
                    <pre className="p-2.5 rounded bg-page text-caption font-mono overflow-x-auto text-secondary whitespace-pre-wrap">
                      {aiProposal.diff}
                    </pre>
                  </div>
                )}

                {/* User Attestation Confirmation Notice if required */}
                {aiProposal.requiresConfirmation && (
                  <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-small text-amber-600 dark:text-amber-400 space-y-2">
                    <div className="flex items-center gap-1.5 font-semibold">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span>New User-Attested Facts Detected</span>
                    </div>
                    <p className="text-caption">
                      The instruction introduced details (e.g. tools or metrics) not found in candidate baseline evidence.
                      {aiProposal.userAttestedFacts.length > 0 && (
                        <span> Detected items: <strong>{aiProposal.userAttestedFacts.join(", ")}</strong>.</span>
                      )}
                    </p>
                    <label className="flex items-center gap-2 cursor-pointer pt-1">
                      <input
                        type="checkbox"
                        checked={confirmAttestation}
                        onChange={(e) => setConfirmAttestation(e.target.checked)}
                        className="rounded border-border text-accent focus:ring-accent"
                      />
                      <span className="text-small font-medium text-primary">
                        I confirm and attest that these claims are factually accurate.
                      </span>
                    </label>
                  </div>
                )}

                {/* Accept / Reject Buttons */}
                <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setAiProposal(null);
                      setIsAiEditModalOpen(false);
                      showToast("AI changes rejected", "info");
                    }}
                    disabled={isApplyingProposal}
                  >
                    Reject Proposal
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleAcceptAiProposal}
                    disabled={isApplyingProposal || (aiProposal.requiresConfirmation && !confirmAttestation)}
                    className="gap-1.5 shadow-subtle"
                  >
                    <Check className="h-4 w-4" />
                    <span>{isApplyingProposal ? "Applying..." : `Accept & Save v${variant.version + 1}`}</span>
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Apply Direct Change Modal */}
      {isApplyModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsApplyModalOpen(false)}
          title="Apply Targeted Change"
          description="Apply an approved bullet modification directly to this targeted variant. Version will increment."
          maxWidth="md"
        >
          <div className="space-y-4">
            {applyError && (
              <ErrorAlert message={applyError} />
            )}

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Target Requirement Name</label>
              <Input
                placeholder="e.g. Distributed Systems Architecture"
                value={applyRequirementName}
                onChange={(e) => setApplyRequirementName(e.target.value)}
              />
            </div>

            {/* Section, Entry & Bullet Selection */}
            {(() => {
              const availableItems =
                applySection === "Experience"
                  ? snapshot?.experience || []
                  : applySection === "Project"
                  ? snapshot?.projects || []
                  : [];

              const currentItem =
                availableItems.find(
                  (it: any, idx: number) =>
                    it.id === applyTargetItemId ||
                    applyTargetItemId === `${applySection === "Experience" ? "exp" : "proj"}_${idx}` ||
                    (idx === 0 && !applyTargetItemId)
                ) || availableItems[0];

              const currentBullets: string[] =
                applySection === "Experience"
                  ? (currentItem as any)?.bullets || []
                  : applySection === "Project"
                  ? (currentItem as any)?.highlights || []
                  : [];

              const isAppending = applyTargetBulletIndex >= currentBullets.length;
              const originalBulletPreview = !isAppending && currentBullets[applyTargetBulletIndex];

              return (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-small font-medium text-primary">Target Section</label>
                      <select
                        value={applySection}
                        onChange={(e) => handleSectionChange(e.target.value as "Experience" | "Project" | "Summary")}
                        className="w-full h-9 rounded-btn border border-border bg-page px-3 text-small text-primary"
                      >
                        <option value="Experience">Experience</option>
                        <option value="Project">Project</option>
                        <option value="Summary">Summary</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-small font-medium text-primary">Target Entry</label>
                      {availableItems.length > 0 ? (
                        <select
                          value={applyTargetItemId || (applySection === "Experience" ? "exp_0" : "proj_0")}
                          onChange={(e) => {
                            setApplyTargetItemId(e.target.value);
                            setApplyTargetBulletIndex(0);
                          }}
                          className="w-full h-9 rounded-btn border border-border bg-page px-3 text-small text-primary truncate"
                        >
                          {availableItems.map((it: any, idx: number) => {
                            const val = it.id || `${applySection === "Experience" ? "exp" : "proj"}_${idx}`;
                            const label =
                              applySection === "Experience"
                                ? `${it.role || "Role"} — ${it.company || "Company"}`
                                : it.title || `Project ${idx + 1}`;
                            return (
                              <option key={val} value={val}>
                                {idx + 1}. {label}
                              </option>
                            );
                          })}
                        </select>
                      ) : (
                        <div className="h-9 px-3 py-1.5 rounded-btn border border-border bg-page/50 text-caption text-muted flex items-center">
                          Default entry will be initialized
                        </div>
                      )}
                    </div>
                  </div>

                  {applySection !== "Summary" && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-small font-medium text-primary">Target Bullet</label>
                        <span className="text-caption text-muted">
                          {isAppending
                            ? `Appending new bullet #${currentBullets.length + 1}`
                            : `Modifying bullet #${applyTargetBulletIndex + 1}`}
                        </span>
                      </div>

                      <select
                        value={applyTargetBulletIndex}
                        onChange={(e) => setApplyTargetBulletIndex(parseInt(e.target.value, 10) || 0)}
                        className="w-full h-9 rounded-btn border border-border bg-page px-3 text-small text-primary truncate"
                      >
                        {currentBullets.map((b: string, bIdx: number) => (
                          <option key={bIdx} value={bIdx}>
                            Bullet {bIdx + 1}: {b.length > 65 ? b.slice(0, 65) + "..." : b}
                          </option>
                        ))}
                        <option value={currentBullets.length}>
                          + Append as new bullet (Index {currentBullets.length})
                        </option>
                      </select>
                    </div>
                  )}

                  {originalBulletPreview && (
                    <div className="p-2.5 rounded bg-muted/10 border border-border/70 space-y-1">
                      <span className="text-caption font-semibold uppercase text-muted">
                        Current Bullet Text:
                      </span>
                      <p className="text-caption text-secondary italic">
                        &ldquo;{originalBulletPreview}&rdquo;
                      </p>
                    </div>
                  )}
                </div>
              );
            })()}

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Approved Bullet Text</label>
              <Textarea
                rows={3}
                placeholder="Enter the factual, verified bullet point to introduce..."
                value={applyApprovedBullet}
                onChange={(e) => setApplyApprovedBullet(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border/60">
              <Button variant="ghost" onClick={() => setIsApplyModalOpen(false)} disabled={isApplying}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleApplyChangeSubmit} disabled={isApplying}>
                {isApplying ? "Applying Change..." : `Apply & Increment to v${variant.version + 1}`}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Revert Confirmation Dialog */}
      {revertingChange && (
        <Modal
          isOpen={true}
          onClose={() => setRevertingChange(null)}
          title="Revert Change Confirmation"
          description={`Reverting change ${revertingChange.id} on requirement "${revertingChange.requirementName || revertingChange.requirement_name}".`}
          maxWidth="sm"
        >
          <div className="space-y-4">
            {revertError && (
              <ErrorAlert message={revertError} />
            )}

            <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-small text-amber-600 dark:text-amber-400 space-y-1">
              <div className="font-semibold">Deterministic Rollback:</div>
              <div>
                The resume snapshot bullet will be restored to its pre-remediation baseline text.
              </div>
              <div className="text-caption text-muted">
                A new revert record will be appended to the ledger, and the variant will increment to <strong>v{variant.version + 1}</strong>.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <Button variant="ghost" onClick={() => setRevertingChange(null)} disabled={isReverting}>
                Cancel
              </Button>
              <Button
                variant="outline"
                className="border-status-error text-status-error hover:bg-status-error-soft"
                onClick={handleRevertConfirm}
                disabled={isReverting}
              >
                {isReverting ? "Reverting..." : "Confirm Revert"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Export Modal */}
      {isExportModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => {
            cleanupPdfPreview();
            setIsExportModalOpen(false);
          }}
          title="Export Targeted Resume"
          description={`Read-only export generated strictly from variant snapshot v${variant.version}.`}
          maxWidth="lg"
        >
          <div className="space-y-4">
            {/* Format Picker */}
            <div className="flex items-center gap-2 border-b border-border/60 pb-3">
              {(["pdf", "markdown", "plain_text", "json"] as const).map((fmt) => (
                <Button
                  key={fmt}
                  variant={exportFormat === fmt ? "primary" : "outline"}
                  size="sm"
                  onClick={() => handleOpenExport(fmt)}
                  disabled={isExportLoading || isPdfDownloading}
                  className="capitalize"
                >
                  {fmt === "pdf" ? "ATS PDF" : fmt.replace("_", " ")}
                </Button>
              ))}
            </div>

            {/* Content Preview */}
            {exportFormat === "pdf" ? (
              isPdfLoading ? (
                <LoadingState text="Generating ATS vector PDF preview..." />
              ) : pdfPreviewError ? (
                <ErrorAlert message={pdfPreviewError} onRetry={() => handleOpenExport("pdf")} />
              ) : pdfPreviewUrl ? (
                <div className="space-y-3">
                  <div className="rounded-card border border-border bg-page overflow-hidden h-[420px]">
                    <object
                      data={pdfPreviewUrl}
                      type="application/pdf"
                      className="w-full h-full"
                    >
                      <div className="p-6 text-center space-y-3">
                        <p className="text-small text-secondary">Your browser does not support inline PDF previews.</p>
                        <Button variant="primary" size="sm" onClick={handleDownloadPdf}>
                          Download ATS PDF
                        </Button>
                      </div>
                    </object>
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <span className="text-caption text-muted">
                      Template: Single-Column ATS Vector PDF &bull; 100% Parser Compliant
                    </span>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleDownloadPdf}
                      disabled={isPdfDownloading}
                      className="gap-1.5 shadow-subtle"
                    >
                      <Download className={`h-3.5 w-3.5 ${isPdfDownloading ? "animate-bounce" : ""}`} />
                      <span>{isPdfDownloading ? "Downloading..." : "Download ATS PDF"}</span>
                    </Button>
                  </div>
                </div>
              ) : null
            ) : isExportLoading ? (
              <LoadingState text="Generating formatted export..." />
            ) : exportData ? (
              <div className="space-y-3">
                <Textarea
                  readOnly
                  rows={12}
                  value={exportData.content}
                  className="font-mono text-xs bg-page resize-none"
                />
                <div className="flex items-center justify-between pt-2">
                  <span className="text-caption text-muted">
                    Format: {exportData.format} &bull; Generated: {formatDate(exportData.exportedAt || exportData.exported_at || "")}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleCopyExport} className="gap-1">
                      {exportCopied ? <CheckCircle2 className="h-3.5 w-3.5 text-status-success" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{exportCopied ? "Copied!" : "Copy"}</span>
                    </Button>
                    <Button variant="primary" size="sm" onClick={handleDownloadExport} className="gap-1">
                      <Download className="h-3.5 w-3.5" />
                      <span>Download</span>
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </Modal>
      )}
    </div>
  );
}
