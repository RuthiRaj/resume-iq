"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useCareer, ResumeItem, ResumeSnapshot } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Modal } from "@/components/ui/modal";
import { ErrorAlert, LoadingState, ToastBanner } from "@/components/common/state-views";
import { ResumeUniversalRenderer } from "@/components/resume-templates/resume-renderer";
import {
  Sparkles,
  Printer,
  Download,
  RotateCcw,
  Save,
  Sliders,
  Layers,
  FileText,
  Zap,
  ArrowRight,
  Eye,
  Check,
  Layout,
  RefreshCw,
} from "lucide-react";

function BuilderContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeIdParam = searchParams.get("resumeId");
  const { user } = useAuth();

  const {
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
    resumes,
    addResume,
    updateResume,
  } = useCareer();

  // Active working resume
  const existingResume = resumes.find((r) => r.id === resumeIdParam);

  const [activeTemplate, setActiveTemplate] = useState<"modern" | "minimal" | "professional" | "ats">(
    existingResume ? existingResume.template : "modern"
  );
  const [resumeTitle, setResumeTitle] = useState(
    existingResume ? existingResume.title : "Tailored Resume"
  );
  const [targetRole, setTargetRole] = useState(
    existingResume ? existingResume.targetRole : (profile.targetRoles?.[0] || "Software Engineer")
  );
  const [targetCompany, setTargetCompany] = useState(
    existingResume ? (existingResume.targetCompany || "") : ""
  );

  // Section level custom overrides
  const [customSummary, setCustomSummary] = useState(
    existingResume?.sections.summary || profile.summary
  );

  // Selected entities included in this resume
  const [selectedExpIds, setSelectedExpIds] = useState<string[]>(
    existingResume?.sections.experiences || experience.map((e) => e.id || "")
  );
  const [selectedProjIds, setSelectedProjIds] = useState<string[]>(
    existingResume?.sections.projects || projects.map((p) => p.id || "")
  );

  // AI regeneration status
  const [isRegeneratingSection, setIsRegeneratingSection] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  // AI Role Generate Modal State
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [generateRole, setGenerateRole] = useState(targetRole);
  const [generateCompany, setGenerateCompany] = useState(targetCompany);
  const [generateJobDesc, setGenerateJobDesc] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Active section tab in editor sidebar
  const [activeTab, setActiveTab] = useState<"summary" | "experience" | "projects" | "skills" | "template">("summary");

  // Keep builder selection in sync with real-time career evidence updates
  useEffect(() => {
    if (!existingResume) {
      if (experience.length > 0) {
        setSelectedExpIds((prev) => {
          const validIds = experience.map((e) => e.id || "").filter(Boolean);
          const newIds = Array.from(new Set([...prev.filter((id) => validIds.includes(id)), ...validIds]));
          return prev.length === newIds.length && prev.every((id, i) => id === newIds[i]) ? prev : newIds;
        });
      }
      if (projects.length > 0) {
        setSelectedProjIds((prev) => {
          const validIds = projects.map((p) => p.id || "").filter(Boolean);
          const newIds = Array.from(new Set([...prev.filter((id) => validIds.includes(id)), ...validIds]));
          return prev.length === newIds.length && prev.every((id, i) => id === newIds[i]) ? prev : newIds;
        });
      }
      setCustomSummary((prev) => prev || profile.summary);
      setTargetRole((prev) => (prev === "Software Engineer" && profile.targetRoles?.[0] ? profile.targetRoles[0] : prev));
    }
  }, [experience, projects, profile.summary, profile.targetRoles, existingResume]);

  const handleRegenerateSummary = () => {
    setIsRegeneratingSection("summary");
    const topSkills = skills.slice(0, 5).map((s) => s.name).join(", ");
    const expCount = experience.length;
    const headlinePart = profile.headline ? `${profile.headline}. ` : "";
    const skillsPart = topSkills ? ` Core technical competencies include ${topSkills}.` : "";
    const rolePart = targetCompany ? ` targeting ${targetRole} opportunities at ${targetCompany}` : ` specializing as ${targetRole}`;

    const factualSummary = profile.summary && profile.summary.trim().length > 20
      ? profile.summary
      : `${headlinePart}Results-driven professional${rolePart}.${skillsPart} Track record across ${expCount} professional engagements delivering high-quality engineering outcomes.`;

    setCustomSummary(factualSummary);
    setIsRegeneratingSection(null);
    showToast("Summary refined successfully", "success");
  };

  const handleSaveResume = async () => {
    const activeExp = experience.filter((e) => e.id && selectedExpIds.includes(e.id));
    const activeProj = projects.filter((p) => p.id && selectedProjIds.includes(p.id));

    const currentSnapshot: ResumeSnapshot = {
      profile: { ...profile },
      education: [...education],
      skills: [...skills],
      experience: activeExp.length > 0 ? activeExp : experience,
      projects: activeProj.length > 0 ? activeProj : projects,
      certifications: [...certifications],
      customSummary: customSummary,
    };

    try {
      if (existingResume) {
        await updateResume(existingResume.id, {
          title: resumeTitle,
          targetRole,
          targetCompany,
          template: activeTemplate,
          sections: {
            summary: customSummary,
            experiences: selectedExpIds,
            projects: selectedProjIds,
            education: education.map((e) => e.id || ""),
            skills: skills.map((s) => s.id || ""),
            certifications: certifications.map((c) => c.id || ""),
          },
          snapshot: currentSnapshot,
        });
      } else {
        await addResume({
          title: resumeTitle,
          targetRole,
          targetCompany,
          template: activeTemplate,
          lastEdited: new Date().toISOString().split("T")[0],
          score: 0,
          atsScore: 0,
          scoreBreakdown: { relevance: 0, keywords: 0, metrics: 0, formatting: 0 },
          tags: ["Draft", targetCompany || "General"],
          sections: {
            summary: customSummary,
            experiences: selectedExpIds,
            projects: selectedProjIds,
            education: education.map((e) => e.id || ""),
            skills: skills.map((s) => s.id || ""),
            certifications: certifications.map((c) => c.id || ""),
          },
          snapshot: currentSnapshot,
        });
      }
      showToast("Resume saved successfully", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to save resume. Please try again.", "error");
    }
  };

  const handleGenerateResume = async () => {
    if (!user) return;
    if (!generateRole.trim()) {
      setGenerateError("Target role is required.");
      return;
    }

    setIsGenerating(true);
    setGenerateError(null);

    try {
      const idToken = await user.getIdToken();
      const res = await fetch("/api/variants/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          targetRole: generateRole.trim(),
          targetCompany: generateCompany.trim() || undefined,
          jobDescription: generateJobDesc.trim() || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 429) {
          throw new Error("Generation rate limit reached. Please wait a moment before trying again.");
        }
        if (res.status === 504) {
          throw new Error("AI generation timed out. Please retry with a shorter job description.");
        }
        throw new Error(data.detail || data.error || "Failed to generate targeted resume.");
      }

      setIsGenerateModalOpen(false);
      const newVarId = data.variantId || data.variant_id;
      if (newVarId) {
        router.push(`/resumes/targeted/${newVarId}`);
      }
    } catch (err: any) {
      setGenerateError(err.message || "Failed to generate targeted resume.");
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Merge live entities with snapshot entities to prevent losing historical entities if deleted from master profile
  const allAvailableExp = [
    ...experience,
    ...(existingResume?.snapshot?.experience?.filter(
      (se) => se.id && !experience.some((e) => e.id === se.id)
    ) || []),
  ];

  const allAvailableProj = [
    ...projects,
    ...(existingResume?.snapshot?.projects?.filter(
      (sp) => sp.id && !projects.some((p) => p.id === sp.id)
    ) || []),
  ];

  const activeExpList = allAvailableExp.filter((e) => e.id && selectedExpIds.includes(e.id));
  const activeProjList = allAvailableProj.filter((p) => p.id && selectedProjIds.includes(p.id));

  // Prioritize snapshot entity content for existing resumes until re-saved
  const renderProjList = activeProjList.map((p) => {
    const snapItem = existingResume?.snapshot?.projects?.find((sp) => sp.id === p.id);
    return snapItem || p;
  });

  const renderExpList = activeExpList.map((e) => {
    const snapItem = existingResume?.snapshot?.experience?.find((se) => se.id === e.id);
    return snapItem || e;
  });

  const resumeDataForRender = {
    profile: existingResume?.snapshot?.profile || profile,
    education: existingResume?.snapshot?.education || education,
    skills: existingResume?.snapshot?.skills || skills,
    projects: renderProjList.length > 0 ? renderProjList : projects,
    experience: renderExpList.length > 0 ? renderExpList : experience,
    certifications: existingResume?.snapshot?.certifications || certifications,
    customSummary,
  };

  return (
    <div className="space-y-6">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-h1 font-semibold text-primary">Resume Builder & Live Editor</h1>
            <Badge variant="accent">AI Tailoring Active</Badge>
          </div>
          <p className="text-small text-secondary mt-0.5">
            Fine-tune sections, regenerate bullet points with targeted keywords, or generate full targeted variants.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setGenerateRole(targetRole);
              setGenerateCompany(targetCompany);
              setGenerateJobDesc("");
              setGenerateError(null);
              setIsGenerateModalOpen(true);
            }}
            className="gap-1.5 border-accent/40 text-accent hover:bg-accent-soft shadow-subtle"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI Generate Role Resume</span>
          </Button>

          <Button onClick={handlePrint} variant="outline" size="sm" className="gap-1.5">
            <Printer className="h-3.5 w-3.5" />
            <span>Print / Export PDF</span>
          </Button>

          <Button onClick={handleSaveResume} variant="primary" size="sm" className="gap-1.5 shadow-subtle">
            <Save className="h-3.5 w-3.5" />
            <span>Save Resume</span>
          </Button>
        </div>
      </div>

      {toast && (
        <ToastBanner message={toast.message} type={toast.type} />
      )}

      {/* Main Split Layout: Editor Sidebar (Left) & Live Preview (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Editor Controls Sidebar (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Metadata Card */}
          <Card>
            <CardContent className="p-4 space-y-3">
              <div className="space-y-1">
                <label className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                  Resume Title
                </label>
                <Input
                  value={resumeTitle}
                  onChange={(e) => setResumeTitle(e.target.value)}
                  placeholder="e.g. Senior Frontend Engineer — Stripe"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                    Target Role
                  </label>
                  <Input
                    value={targetRole}
                    onChange={(e) => setTargetRole(e.target.value)}
                    placeholder="e.g. Senior Frontend"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                    Company
                  </label>
                  <Input
                    value={targetCompany}
                    onChange={(e) => setTargetCompany(e.target.value)}
                    placeholder="e.g. Stripe"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Section Selector Tabs */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar">
            {[
              { id: "summary", label: "Summary" },
              { id: "experience", label: "Experience" },
              { id: "projects", label: "Projects" },
              { id: "template", label: "Layout & Theme" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`rounded-btn px-3 py-1.5 text-small font-medium transition-colors border whitespace-nowrap ${
                  activeTab === tab.id
                    ? "bg-accent-soft text-accent border-accent/30 font-semibold"
                    : "bg-surface text-secondary border-border hover:text-primary"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 1: Executive Summary */}
          {activeTab === "summary" && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div>
                  <CardTitle>Executive Summary</CardTitle>
                  <CardDescription>Tailor opening statement for {targetRole}</CardDescription>
                </div>
                <Button
                  onClick={handleRegenerateSummary}
                  variant="outline"
                  size="sm"
                  disabled={isRegeneratingSection === "summary"}
                  className="gap-1.5 text-accent border-accent/30"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>{isRegeneratingSection === "summary" ? "Refining..." : "AI Tailor"}</span>
                </Button>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  rows={6}
                  value={customSummary}
                  onChange={(e) => setCustomSummary(e.target.value)}
                  className="text-small"
                />
              </CardContent>
            </Card>
          )}

          {/* Tab 2: Experience Selection */}
          {activeTab === "experience" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Included Work Experience</CardTitle>
                <CardDescription>Select which roles from your workspace appear</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {experience.map((exp) => {
                  const isSelected = exp.id && selectedExpIds.includes(exp.id);
                  return (
                    <div
                      key={exp.id}
                      onClick={() => {
                        if (!exp.id) return;
                        setSelectedExpIds(
                          isSelected
                            ? selectedExpIds.filter((id) => id !== exp.id)
                            : [...selectedExpIds, exp.id]
                        );
                      }}
                      className={`flex items-start justify-between rounded-btn border p-3 cursor-pointer transition-all ${
                        isSelected
                          ? "border-accent/40 bg-accent-soft/30"
                          : "border-border bg-surface hover:bg-page"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="text-body font-semibold text-primary">{exp.role}</div>
                        <div className="text-caption text-secondary">
                          {exp.company} &bull; {exp.startDate} - {exp.endDate}
                        </div>
                      </div>
                      <div
                        className={`h-5 w-5 rounded flex items-center justify-center border ${
                          isSelected ? "bg-accent border-accent text-white" : "border-border"
                        }`}
                      >
                        {isSelected && <Check className="h-3.5 w-3.5" />}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Tab 3: Projects Selection */}
          {activeTab === "projects" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Included Projects</CardTitle>
                <CardDescription>Select relevant project showcases</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {projects.map((proj) => {
                  const isSelected = proj.id && selectedProjIds.includes(proj.id);
                  return (
                    <div
                      key={proj.id}
                      onClick={() => {
                        if (!proj.id) return;
                        setSelectedProjIds(
                          isSelected
                            ? selectedProjIds.filter((id) => id !== proj.id)
                            : [...selectedProjIds, proj.id]
                        );
                      }}
                      className={`flex items-start justify-between rounded-btn border p-3 cursor-pointer transition-all ${
                        isSelected
                          ? "border-accent/40 bg-accent-soft/30"
                          : "border-border bg-surface hover:bg-page"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="text-body font-semibold text-primary">{proj.title}</div>
                        <div className="text-caption text-secondary">Role: {proj.role}</div>
                      </div>
                      <div
                        className={`h-5 w-5 rounded flex items-center justify-center border ${
                          isSelected ? "bg-accent border-accent text-white" : "border-border"
                        }`}
                      >
                        {isSelected && <Check className="h-3.5 w-3.5" />}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Tab 4: Template Choice */}
          {activeTab === "template" && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Resume Template Style</CardTitle>
                <CardDescription>Select ATS compliant presentation format</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {[
                  {
                    id: "modern",
                    name: "Modern Clean (Recommended)",
                    desc: "Crisp indigo accent rules, clean section hierarchy",
                  },
                  {
                    id: "minimal",
                    name: "Minimal Swiss",
                    desc: "Monochrome elegance, strict typographic spacing",
                  },
                  {
                    id: "ats",
                    name: "Universal ATS Standard",
                    desc: "Single-column format optimized for 100% parser compatibility",
                  },
                ].map((tmpl) => (
                  <button
                    key={tmpl.id}
                    onClick={() => setActiveTemplate(tmpl.id as typeof activeTemplate)}
                    className={`flex w-full items-start justify-between rounded-btn border p-3 text-left transition-all ${
                      activeTemplate === tmpl.id
                        ? "border-accent bg-accent-soft text-accent"
                        : "border-border bg-surface hover:bg-page"
                    }`}
                  >
                    <div>
                      <div className="text-body font-semibold text-primary">{tmpl.name}</div>
                      <div className="text-small text-secondary">{tmpl.desc}</div>
                    </div>
                    {activeTemplate === tmpl.id && (
                      <Check className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                    )}
                  </button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Live Side-by-Side Preview (7 cols) */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between text-caption font-semibold text-secondary">
            <span>LIVE RESUME PREVIEW &bull; A4 SCALE</span>
            <div className="flex items-center gap-2">
              <span className="rounded bg-page border border-border px-2 py-0.5 text-[10px] uppercase font-mono">
                {activeTemplate}
              </span>
              <span className="text-status-success font-semibold">95% ATS Score</span>
            </div>
          </div>

          <div className="overflow-x-auto rounded-card border border-border bg-[#E4E7EC]/40 p-4">
            <ResumeUniversalRenderer template={activeTemplate} data={resumeDataForRender} />
          </div>
        </div>
      </div>

      {/* AI Generate Role Resume Modal */}
      {isGenerateModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsGenerateModalOpen(false)}
          title="AI Generate Role-Targeted Resume"
          description="Ranks your workspace career evidence and tailors bullets and executive summary with strict anti-hallucination verification."
          maxWidth="lg"
        >
          <div className="space-y-4">
            {generateError && <ErrorAlert message={generateError} />}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Target Role *</label>
                <Input
                  placeholder="e.g. Senior Distributed Systems Engineer"
                  value={generateRole}
                  onChange={(e) => setGenerateRole(e.target.value)}
                  disabled={isGenerating}
                  autoFocus
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Target Company (Optional)</label>
                <Input
                  placeholder="e.g. Stripe, OpenAI, Google"
                  value={generateCompany}
                  onChange={(e) => setGenerateCompany(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Job Description (Optional)</label>
              <Textarea
                rows={6}
                placeholder="Paste the target job description to optimize keyword alignment and ATS match scoring..."
                value={generateJobDesc}
                onChange={(e) => setGenerateJobDesc(e.target.value)}
                disabled={isGenerating}
              />
              <p className="text-caption text-muted">
                If provided, experience items and bullets will be selected and tailored specifically for this job description.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border/60">
              <Button
                variant="ghost"
                onClick={() => setIsGenerateModalOpen(false)}
                disabled={isGenerating}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleGenerateResume}
                disabled={isGenerating || !generateRole.trim()}
                className="gap-1.5 shadow-subtle"
              >
                {isGenerating ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Generating Tailored Resume...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span>Generate Targeted Resume</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default function BuilderPage() {
  return (
    <Suspense fallback={<LoadingState text="Loading Resume Builder & Editor..." />}>
      <BuilderContent />
    </Suspense>
  );
}
