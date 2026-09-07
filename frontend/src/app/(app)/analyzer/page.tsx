"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useCareer, RequirementMatchData, RemediationSuggestionData } from "@/lib/store";
import { useAuth } from "@/lib/auth-context";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/common/state-views";
import {
  Zap,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Sparkles,
  ArrowRight,
  TrendingUp,
  FileText,
  Layers,
  Search,
  Loader2,
  Check,
  AlertCircle,
  Briefcase,
  Code2,
  ListChecks,
  Compass,
  Wand2,
  Send,
  RefreshCw,
  PlusCircle,
  GitBranch,
  ExternalLink,
} from "lucide-react";

interface SkillRequirementData {
  name: string;
  category?: string;
  importance?: string;
  sourceEvidence?: string;
}

interface JobIntelligenceData {
  jobInfo?: {
    roleTitle: string;
    company?: string;
    seniorityLevel?: string;
    employmentType?: string;
    domain?: string;
  };
  mustHaveSkills?: SkillRequirementData[];
  preferredSkills?: SkillRequirementData[];
  technicalStack?: string[];
  responsibilities?: string[];
  experience?: {
    minimumYears?: number;
    requiredLevel?: string;
    description?: string;
  };
  education?: {
    degreeLevel?: string;
    fieldOfStudy?: string;
    isRequired?: boolean;
  };
  certifications?: string[];
  softSkills?: string[];
  summary?: string;
}

function AnalyzerContent() {
  const searchParams = useSearchParams();
  const resumeIdParam = searchParams.get("resumeId");

  const { resumes, skills, addSkill } = useCareer();
  const { user } = useAuth();

  const [selectedResumeId, setSelectedResumeId] = useState<string>(
    resumeIdParam || (resumes[0]?.id || "workspace")
  );
  const [jobTitle, setJobTitle] = useState("Senior Full Stack Engineer");
  const [jobCompany, setJobCompany] = useState("Stripe");
  const [jobDescription, setJobDescription] = useState(
    "We are looking for a Senior Full Stack Engineer to join Stripe developer platforms.\n\nRequirements:\n- 3+ years experience with TypeScript, React, Next.js, and Node.js.\n- Strong database fundamentals in PostgreSQL and Prisma.\n- Experience with AWS cloud infrastructure (ECS, Lambda, S3) and Docker.\n- Focus on performance, design system tokens, and API reliability.\n- Familiarity with AI developer tools or vector search is a plus."
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Analysis Metrics
  const [overallScore, setOverallScore] = useState(0);
  const [previousScore, setPreviousScore] = useState<number | null>(null);
  const [atsDelta, setAtsDelta] = useState<number | null>(null);
  const [relevanceScore, setRelevanceScore] = useState(0);
  const [keywordScore, setKeywordScore] = useState(0);
  const [impactScore, setImpactScore] = useState(0);
  const [formatScore, setFormatScore] = useState(0);
  const [summaryFeedback, setSummaryFeedback] = useState("");

  const [missingSkills, setMissingSkills] = useState<Array<{ name: string; priority: string; reason: string }>>([]);
  const [matchingSkills, setMatchingSkills] = useState<Array<{ name: string; context: string }>>([]);
  const [partialSkills, setPartialSkills] = useState<Array<{ name: string; note: string }>>([]);
  const [jobIntelligence, setJobIntelligence] = useState<JobIntelligenceData | null>(null);
  const [requirementMatches, setRequirementMatches] = useState<RequirementMatchData[]>([]);
  const [remediationSuggestions, setRemediationSuggestions] = useState<RemediationSuggestionData[]>([]);

  // Interactive Remediation State
  const [candidateFacts, setCandidateFacts] = useState<Record<string, string>>({});
  const [editingBullets, setEditingBullets] = useState<Record<string, string>>({});
  const [appliedRemediations, setAppliedRemediations] = useState<Record<string, boolean>>({});
  const [synthesizingId, setSynthesizingId] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [targetedResumeId, setTargetedResumeId] = useState<string | null>(null);

  const router = useRouter();
  const [isForkingVariant, setIsForkingVariant] = useState(false);
  const [forkVariantError, setForkVariantError] = useState<string | null>(null);

  // Automatically restore saved analysis when selecting an analyzed resume
  const lastLoadedKeyRef = useRef<string | null>(null);

  useEffect(() => {
    if (selectedResumeId && selectedResumeId !== "workspace") {
      const found = resumes.find((r) => r.id === selectedResumeId);
      if (found && typeof found.atsScore === "number") {
        const resumeAnalysisKey = `${found.id}_${found.lastAnalyzedAt || ""}_${found.atsScore}`;
        if (lastLoadedKeyRef.current === resumeAnalysisKey) {
          return;
        }
        lastLoadedKeyRef.current = resumeAnalysisKey;

        setOverallScore(found.atsScore);
        if (found.scoreBreakdown) {
          setRelevanceScore(found.scoreBreakdown.relevance);
          setKeywordScore(found.scoreBreakdown.keywords);
          setImpactScore(found.scoreBreakdown.metrics);
          setFormatScore(found.scoreBreakdown.formatting);
        }
        if (found.targetRole) setJobTitle(found.targetRole);
        if (found.targetCompany) setJobCompany(found.targetCompany);

        if (found.analysisResults) {
          setSummaryFeedback(found.analysisResults.summaryFeedback || "");
          setMatchingSkills(found.analysisResults.matchingSkills || []);
          setMissingSkills(found.analysisResults.missingSkills || []);
          setPartialSkills(found.analysisResults.partialSkills || []);
          setJobIntelligence(found.analysisResults.jobIntelligence || null);
          setRequirementMatches(found.analysisResults.requirementMatches || []);
          setRemediationSuggestions(found.analysisResults.remediationSuggestions || []);
        }
        setHasAnalyzed(true);
      } else {
        lastLoadedKeyRef.current = null;
      }
    } else {
      lastLoadedKeyRef.current = null;
    }
  }, [selectedResumeId, resumes]);

  const handleRunAnalysis = async () => {
    if (!user) {
      setErrorMessage("Please sign in to run ATS analysis.");
      return;
    }

    if (!jobTitle || jobTitle.trim().length < 2) {
      setErrorMessage("Target job title must be at least 2 characters.");
      return;
    }

    if (!jobDescription || jobDescription.trim().length < 30) {
      setErrorMessage("Job description must be at least 30 characters.");
      return;
    }

    if (jobDescription.length > 25000) {
      setErrorMessage("Job description exceeds the maximum length of 25,000 characters.");
      return;
    }

    setErrorMessage(null);
    setIsAnalyzing(true);

    try {
      const idToken = await user.getIdToken();
      const response = await fetch("/api/ai/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          resumeId: selectedResumeId,
          targetRole: jobTitle.trim(),
          targetCompany: jobCompany.trim(),
          jobDescription: jobDescription.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `Analysis failed with status ${response.status}`);
      }

      setOverallScore(data.atsScore);
      if (data.scoreBreakdown) {
        setRelevanceScore(data.scoreBreakdown.relevance);
        setKeywordScore(data.scoreBreakdown.keywords);
        setImpactScore(data.scoreBreakdown.metrics);
        setFormatScore(data.scoreBreakdown.formatting);
      }
      setSummaryFeedback(data.summaryFeedback || "");
      setMatchingSkills(data.matchingSkills || []);
      setMissingSkills(data.missingSkills || []);
      setPartialSkills(data.partialSkills || []);
      setJobIntelligence(data.jobIntelligence || null);
      setRequirementMatches(data.requirementMatches || []);
      setRemediationSuggestions(data.remediationSuggestions || []);
      setHasAnalyzed(true);

      // Initialize editing bullets map
      if (data.remediationSuggestions) {
        const editMap: Record<string, string> = {};
        data.remediationSuggestions.forEach((sug: RemediationSuggestionData) => {
          if (sug.suggestedBullet) editMap[sug.id] = sug.suggestedBullet;
        });
        setEditingBullets((prev) => ({ ...prev, ...editMap }));
      }

      // Local component state is already updated above.
      // Persistence is handled authoritatively by the backend endpoint in Firestore.
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze resume. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleForkTargetedVariant = async () => {
    if (!user) {
      setErrorMessage("Please sign in to fork a targeted variant.");
      return;
    }

    if (!jobDescription || jobDescription.trim().length < 30) {
      setErrorMessage("Job description must be at least 30 characters to create a targeted variant.");
      return;
    }

    setIsForkingVariant(true);
    setForkVariantError(null);

    try {
      const idToken = await user.getIdToken();
      const masterId = selectedResumeId === "workspace" ? (resumes[0]?.id || "workspace") : selectedResumeId;

      const res = await fetch("/api/variants/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          masterResumeId: masterId,
          targetRole: jobTitle.trim() || "Target Role",
          targetCompany: jobCompany.trim() || "",
          jobDescription: jobDescription.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || "Failed to create targeted variant.");
      }

      router.push(`/resumes/targeted/${data.variantId}`);
    } catch (err: any) {
      setForkVariantError(err.message || "Failed to fork targeted variant.");
    } finally {
      setIsForkingVariant(false);
    }
  };

  const handleSynthesizeBullet = async (sug: RemediationSuggestionData) => {
    if (!user) return;
    const factText = candidateFacts[sug.id]?.trim();
    if (!factText || factText.length < 5) {
      setErrorMessage("Please enter at least a few words describing your real-world experience.");
      return;
    }

    setSynthesizingId(sug.id);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const response = await fetch("/api/ai/remediate/synthesize-bullet", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          requirementName: sug.requirementName,
          candidateFact: factText,
          targetRole: jobTitle,
          jobContext: jobDescription.substring(0, 300),
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to synthesize bullet.");
      }

      setEditingBullets((prev) => ({ ...prev, [sug.id]: data.synthesizedBullet }));
      // Update local suggestion validation report
      setRemediationSuggestions((prev) =>
        prev.map((item) =>
          item.id === sug.id
            ? { ...item, suggestedBullet: data.synthesizedBullet, validation: data.validation, status: data.status }
            : item
        )
      );
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to synthesize bullet from facts.");
    } finally {
      setSynthesizingId(null);
    }
  };

  const handleApplyRemediation = async (sug: RemediationSuggestionData) => {
    if (!user) return;
    const approvedBullet = editingBullets[sug.id]?.trim() || sug.suggestedBullet?.trim();
    if (!approvedBullet) {
      setErrorMessage("Cannot apply an empty bullet.");
      return;
    }

    setApplyingId(sug.id);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const response = await fetch("/api/ai/remediate/apply", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          resumeId: targetedResumeId || selectedResumeId,
          remediationId: sug.id,
          sourceEvidenceId: sug.sourceEvidenceId,
          targetSection: sug.targetSection || "Experience",
          targetExperienceId: sug.targetExperienceId,
          targetBulletIndex: sug.targetBulletIndex,
          approvedBullet: approvedBullet,
          targetRole: jobTitle,
          targetCompany: jobCompany,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to apply remediation.");
      }

      setAppliedRemediations((prev) => ({ ...prev, [sug.id]: true }));
      if (data.targetedResumeId) {
        setTargetedResumeId(data.targetedResumeId);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to apply remediation to targeted resume.");
    } finally {
      setApplyingId(null);
    }
  };

  const handleReAnalyzeTargetFit = async () => {
    if (!user) return;
    setPreviousScore(overallScore);
    const resumeToAnalyze = targetedResumeId || selectedResumeId;

    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const idToken = await user.getIdToken();
      const response = await fetch("/api/ai/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          resumeId: resumeToAnalyze,
          targetRole: jobTitle.trim(),
          targetCompany: jobCompany.trim(),
          jobDescription: jobDescription.trim(),
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Re-analysis failed.");

      const newScore = data.atsScore;
      setAtsDelta(newScore - overallScore);
      setOverallScore(newScore);

      if (data.scoreBreakdown) {
        setRelevanceScore(data.scoreBreakdown.relevance);
        setKeywordScore(data.scoreBreakdown.keywords);
        setImpactScore(data.scoreBreakdown.metrics);
        setFormatScore(data.scoreBreakdown.formatting);
      }
      setSummaryFeedback(data.summaryFeedback || "");
      setMatchingSkills(data.matchingSkills || []);
      setMissingSkills(data.missingSkills || []);
      setPartialSkills(data.partialSkills || []);
      setJobIntelligence(data.jobIntelligence || null);
      setRequirementMatches(data.requirementMatches || []);
      setRemediationSuggestions(data.remediationSuggestions || []);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to re-analyze targeted resume fit.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAddMissingSkill = (skillName: string) => {
    addSkill({
      name: skillName,
      category: "Cloud & DevOps",
      proficiency: "Intermediate",
      yearsOfExperience: 1,
    });
    setMissingSkills((prev) => prev.filter((s) => s.name !== skillName));
    setMatchingSkills((prev) => [...prev, { name: skillName, context: "Added to Career Profile" }]);
  };

  const handleLoadSampleJD = () => {
    setJobTitle("Senior Full Stack Engineer");
    setJobCompany("Stripe");
    setJobDescription(
      "We are looking for a Senior Full Stack Engineer to join Stripe developer platforms.\n\nRequirements:\n- 3+ years experience with TypeScript, React, Next.js, and Node.js.\n- Strong database fundamentals in PostgreSQL and Prisma.\n- Experience with AWS cloud infrastructure (ECS, Lambda, S3) and Docker.\n- Focus on performance, design system tokens, and API reliability.\n- Familiarity with AI developer tools or vector search is a plus."
    );
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* Header */}
      <div>
        <h1 className="text-h1 font-bold text-primary tracking-tight">AI ATS Match Analyzer</h1>
        <p className="text-body text-secondary mt-1">
          Perform deterministic ATS scoring, discover keyword gaps, extract structured Job Intelligence, and verify Requirement Evidence Matching powered by Groq.
        </p>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="flex items-start gap-3 rounded-btn border border-status-error/30 bg-status-error-soft/60 p-4 text-status-error">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="space-y-1 text-small">
            <div className="font-semibold">Analysis Notice</div>
            <div>{errorMessage}</div>
          </div>
        </div>
      )}

      {/* Target Input Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle>Target Role & Job Description</CardTitle>
            <CardDescription>Select the resume source and paste the opportunity details</CardDescription>
          </div>
          <Button onClick={handleLoadSampleJD} variant="outline" size="sm">
            Load Sample Stripe JD
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Resume Source</label>
              <select
                value={selectedResumeId}
                onChange={(e) => {
                  setSelectedResumeId(e.target.value);
                  setErrorMessage(null);
                }}
                className="flex h-9 w-full rounded-input border border-border bg-surface px-3 py-1.5 text-body text-primary focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="workspace">Master Career Workspace Profile (Live)</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title} ({r.template.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Target Job Title</label>
              <Input
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="e.g. Senior Full Stack Engineer"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Target Company (Optional)</label>
              <Input
                value={jobCompany}
                onChange={(e) => setJobCompany(e.target.value)}
                placeholder="e.g. Stripe"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Paste Job Description</label>
            <Textarea
              rows={5}
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste full job description requirements here..."
            />
          </div>

          <div className="flex justify-end">
            <Button
              onClick={handleRunAnalysis}
              variant="primary"
              disabled={isAnalyzing}
              className="gap-2"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Evaluating ATS Match & Requirement Evidence...</span>
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4" />
                  <span>Run ATS Deep Scan</span>
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Results View or Ready State */}
      {!hasAnalyzed ? (
        <Card className="border-dashed border-border">
          <CardContent className="p-10 flex flex-col items-center justify-center text-center space-y-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent">
              <Zap className="h-6 w-6" />
            </div>
            <div className="space-y-1 max-w-md">
              <div className="text-body font-semibold text-primary">Ready for ATS Deep Scan</div>
              <p className="text-small text-secondary">
                Select a resume version or your master profile above, provide the target job requirements, and click{" "}
                <span className="font-semibold text-primary">Run ATS Deep Scan</span> to extract structured Job Intelligence, verify Requirement Evidence Matching, and evaluate keyword match density.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
          {/* Phase 5.4 Targeted Resume Workspace Callout Banner */}
          <Card className="border-accent/40 bg-gradient-to-r from-accent-soft/30 via-surface to-accent-soft/20 shadow-sm">
            <CardContent className="p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-btn bg-accent text-accent-foreground shadow-sm">
                  <GitBranch className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-body font-semibold text-primary flex items-center gap-2">
                    Targeted Resume Workspace
                    <Badge variant="accent" className="text-[10px] font-semibold uppercase tracking-wider">Phase 5.4</Badge>
                  </h3>
                  <p className="text-small text-secondary mt-0.5">
                    Fork an isolated, immutable variant for <span className="font-medium text-primary">{jobTitle || "this role"}</span>{jobCompany ? ` at ${jobCompany}` : ""}. Track bullet versions, fit progression, and export without modifying your master resume.
                  </p>
                  {forkVariantError && (
                    <p className="text-caption text-status-danger mt-1 font-medium">{forkVariantError}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                {targetedResumeId ? (
                  <Button
                    size="sm"
                    className="gap-1.5 shadow-sm"
                    onClick={() => router.push(`/resumes/targeted/${targetedResumeId}`)}
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open Variant Workspace
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    className="gap-1.5 shadow-sm"
                    onClick={handleForkTargetedVariant}
                    disabled={isForkingVariant || !jobDescription || jobDescription.trim().length < 30}
                  >
                    {isForkingVariant ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Forking Variant...
                      </>
                    ) : (
                      <>
                        <GitBranch className="h-4 w-4" />
                        Fork Targeted Variant
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Score Overview Row */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Overall Large Score Card */}
            <Card className="md:col-span-2 border-accent/30 bg-surface">
              <CardContent className="p-6 flex flex-col justify-between h-full space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-caption uppercase text-accent font-semibold tracking-[0.4px]">
                    Overall ATS Readiness
                  </span>
                  <Badge variant={overallScore >= 90 ? "success" : overallScore >= 75 ? "accent" : "warning"}>
                    {overallScore >= 90 ? "Top 5% Candidate" : overallScore >= 75 ? "Strong Fit" : "Developing Fit"}
                  </Badge>
                </div>

                <div className="flex items-baseline gap-2">
                  <span className="text-[48px] font-bold leading-none text-primary">
                    {overallScore}
                  </span>
                  <span className="text-h2 text-muted font-normal">/ 100</span>
                </div>

                <p className="text-small text-secondary leading-relaxed">
                  {summaryFeedback || `Your resume demonstrates alignment with the ${jobTitle} role at ${jobCompany || "target employer"}.`}
                </p>
              </CardContent>
            </Card>

            {/* 3 Metric Breakdown Cards */}
            <Card className="flex flex-col justify-between">
              <CardContent className="p-4 space-y-2">
                <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                  Relevance Match
                </span>
                <div className="text-h1 font-semibold text-primary">{relevanceScore}%</div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full bg-accent transition-all duration-500"
                    style={{ width: `${relevanceScore}%` }}
                  />
                </div>
                <p className="text-caption text-secondary">Domain & role alignment</p>
              </CardContent>
            </Card>

            <Card className="flex flex-col justify-between">
              <CardContent className="p-4 space-y-2">
                <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                  Keyword Density
                </span>
                <div className="text-h1 font-semibold text-status-success">{keywordScore}%</div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full bg-status-success transition-all duration-500"
                    style={{ width: `${keywordScore}%` }}
                  />
                </div>
                <p className="text-caption text-secondary">{matchingSkills.length} keywords matched</p>
              </CardContent>
            </Card>

            <Card className="flex flex-col justify-between">
              <CardContent className="p-4 space-y-2">
                <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                  Impact & Metrics
                </span>
                <div className="text-h1 font-semibold text-primary">{impactScore}%</div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className="h-full bg-accent transition-all duration-500"
                    style={{ width: `${impactScore}%` }}
                  />
                </div>
                <p className="text-caption text-secondary">Quantifiable metrics verified</p>
              </CardContent>
            </Card>
          </div>

          {/* Requirement Evidence Matching Matrix (Phase 5.2.1) */}
          {requirementMatches && requirementMatches.length > 0 && (
            <Card className="border-accent/20 bg-surface">
              <CardHeader className="pb-3 border-b border-border/40">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-btn bg-accent-soft text-accent">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-semibold">
                        Requirement Evidence Matching
                      </CardTitle>
                      <CardDescription>
                        Fine-grained evidence mapping comparing verified candidate experience against target job requirements
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-caption">
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="h-2 w-2 rounded-full bg-status-success inline-block"></span>
                      Strong ({requirementMatches.filter((m) => m.matchStatus === "StrongMatch").length})
                    </span>
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="h-2 w-2 rounded-full bg-status-warning inline-block"></span>
                      Partial ({requirementMatches.filter((m) => m.matchStatus === "PartialMatch").length})
                    </span>
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="h-2 w-2 rounded-full bg-status-error inline-block"></span>
                      Missing ({requirementMatches.filter((m) => m.matchStatus === "Missing").length})
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4 space-y-3">
                {requirementMatches.map((match, idx) => (
                  <div
                    key={`rm-${match.requirementName}-${idx}`}
                    className={`rounded-btn border p-4 space-y-3 transition-all ${
                      match.matchStatus === "StrongMatch"
                        ? "border-status-success/30 bg-status-success-soft/20"
                        : match.matchStatus === "PartialMatch"
                        ? "border-status-warning/30 bg-status-warning-soft/20"
                        : "border-status-error/30 bg-status-error-soft/20"
                    }`}
                  >
                    {/* Header Row */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-body font-semibold text-primary">{match.requirementName}</span>
                        <Badge
                          variant={match.importance === "MustHave" ? "warning" : "outline"}
                          className="text-[10px] px-1.5 py-0"
                        >
                          {match.importance === "MustHave" ? "Must-Have" : "Preferred"}
                        </Badge>
                        {match.category && (
                          <span className="text-[11px] text-muted font-medium bg-surface px-2 py-0.5 rounded border border-border/40">
                            {match.category}
                          </span>
                        )}
                        {match.evidenceSourceSection && match.evidenceSourceSection !== "None" && (
                          <span className="text-[11px] font-medium bg-accent-soft text-accent px-2 py-0.5 rounded border border-accent/30">
                            {match.evidenceSourceSection === "Experience" ? "Work Experience" : match.evidenceSourceSection === "SkillTag" ? "Skill List" : match.evidenceSourceSection}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            match.matchStatus === "StrongMatch"
                              ? "success"
                              : match.matchStatus === "PartialMatch"
                              ? "accent"
                              : "default"
                          }
                          className="text-caption font-semibold"
                        >
                          {match.matchStatus === "StrongMatch"
                            ? "Strong Match"
                            : match.matchStatus === "PartialMatch"
                            ? "Partial Match"
                            : "Missing"}
                        </Badge>
                        <span className="text-[11px] text-secondary">
                          Confidence: <span className="font-medium text-primary">{match.confidence}</span>
                        </span>
                      </div>
                    </div>

                    {/* Match Rationale ("Why?") */}
                    {match.matchReason && (
                      <div className="text-small text-secondary bg-surface/80 p-2.5 rounded border border-border/40">
                        <span className="font-semibold text-primary">Why? </span>
                        {match.matchReason}
                      </div>
                    )}

                    {/* Gap Explanation (when Partial or Missing) */}
                    {match.matchStatus !== "StrongMatch" && match.gapReason && (
                      <div className="text-small text-status-warning bg-status-warning-soft/40 p-2.5 rounded border border-status-warning/30 flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-status-warning" />
                        <div>
                          <span className="font-semibold text-primary">Gap: </span>
                          <span>{match.gapReason}</span>
                          {match.gapType && match.gapType !== "None" && (
                            <span className="ml-2 text-[10px] uppercase font-bold text-muted bg-surface px-1.5 py-0.5 rounded border border-border">
                              {match.gapType}
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Evidence Grid: JD Quote vs Candidate Resume Evidence */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-caption pt-1">
                      {/* Job Requirement Source Snippet */}
                      <div className="rounded bg-surface p-2.5 border border-border/50 space-y-1">
                        <div className="font-medium text-primary text-[11px] uppercase tracking-wide text-muted">
                          Job Description Requirement
                        </div>
                        <div className="text-secondary italic">
                          {match.jobSourceEvidence
                            ? `"${match.jobSourceEvidence}"`
                            : "Explicit requirement specified in job description."}
                        </div>
                      </div>

                      {/* Candidate Resume Grounded Evidence */}
                      <div className="rounded bg-surface p-2.5 border border-border/50 space-y-1">
                        <div className="font-medium text-primary text-[11px] uppercase tracking-wide text-muted">
                          Candidate Resume Evidence
                        </div>
                        {match.resumeEvidence ? (
                          <div className="text-primary font-medium">
                            &ldquo;{match.resumeEvidence}&rdquo;
                          </div>
                        ) : (
                          <div className="text-status-error italic">
                            No supporting candidate evidence detected in resume snapshot.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Evidence-Grounded Gap Remediation Section (Phase 5.3) */}
          {remediationSuggestions && remediationSuggestions.length > 0 && (
            <Card className="border-accent/30 bg-surface shadow-sm">
              <CardHeader className="pb-3 border-b border-border/40">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-btn bg-accent-soft text-accent">
                      <Wand2 className="h-4 w-4" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-semibold">
                        Targeted Gap Remediation Engine
                      </CardTitle>
                      <CardDescription>
                        Truthful, evidence-grounded action plan to resolve requirement gaps without fabricating claims
                      </CardDescription>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {atsDelta !== null && (
                      <Badge variant="success" className="text-caption font-semibold px-2.5 py-1">
                        ATS Delta: +{atsDelta} pts ({previousScore}% → {overallScore}%)
                      </Badge>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleReAnalyzeTargetFit}
                      disabled={isAnalyzing}
                      className="text-caption gap-1.5 h-8"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isAnalyzing ? "animate-spin" : ""}`} />
                      Re-Analyze Target Fit
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4 space-y-4">
                {remediationSuggestions.map((sug) => {
                  const isApplied = appliedRemediations[sug.id];
                  const currentEditBullet = editingBullets[sug.id] !== undefined ? editingBullets[sug.id] : (sug.suggestedBullet || "");
                  const isSynthesizing = synthesizingId === sug.id;
                  const isApplying = applyingId === sug.id;

                  return (
                    <div
                      key={sug.id}
                      className={`rounded-btn border p-4 space-y-3 transition-all ${
                        isApplied
                          ? "border-status-success/40 bg-status-success-soft/20"
                          : sug.eligibility === "NotRemediable"
                          ? "border-border/60 bg-surface-raised/40"
                          : "border-border/60 bg-surface"
                      }`}
                    >
                      {/* Remediation Header */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-body font-semibold text-primary">{sug.requirementName}</span>
                          <Badge
                            variant={sug.importance === "MustHave" ? "warning" : "outline"}
                            className="text-[10px] px-1.5 py-0"
                          >
                            {sug.importance === "MustHave" ? "Must-Have" : "Preferred"}
                          </Badge>
                          <Badge
                            variant={
                              sug.eligibility === "Remediable"
                                ? "accent"
                                : sug.eligibility === "RequiresCandidateFacts"
                                ? "warning"
                                : "outline"
                            }
                            className="text-[10px] px-1.5 py-0"
                          >
                            {sug.eligibility === "Remediable"
                              ? "Grounded Rewrite"
                              : sug.eligibility === "RequiresCandidateFacts"
                              ? "Supply Missing Facts"
                              : sug.eligibility === "PartiallyRemediable"
                              ? "Adjacent Tech"
                              : "Hard Experience Gap"}
                          </Badge>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-medium text-secondary">
                            Impact:{" "}
                            <span
                              className={`font-semibold ${
                                sug.potentialImpact === "High"
                                  ? "text-accent"
                                  : sug.potentialImpact === "Medium"
                                  ? "text-primary"
                                  : "text-muted"
                              }`}
                            >
                              {sug.potentialImpact} Potential
                            </span>
                          </span>
                          {isApplied && (
                            <div className="flex items-center gap-1.5">
                              <Badge variant="success" className="text-[10px] gap-1">
                                <Check className="h-3 w-3" /> Applied to Targeted Resume
                              </Badge>
                              {targetedResumeId && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => router.push(`/resumes/targeted/${targetedResumeId}`)}
                                  className="h-6 text-[11px] px-2 gap-1 text-accent hover:text-accent-strong hover:bg-accent-soft/30"
                                >
                                  <ExternalLink className="h-3 w-3" /> Workspace
                                </Button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Strategy Guidance */}
                      <div className="text-small text-secondary bg-surface-raised p-2.5 rounded border border-border/40">
                        <span className="font-semibold text-primary">Remediation Strategy: </span>
                        {sug.guidance}
                      </div>

                      {/* Case 1: ImproveExistingBullet (Grounded Rewrite) */}
                      {sug.actionType === "ImproveExistingBullet" || sug.actionType === "ClarifyAdjacentTechnology" ? (
                        <div className="space-y-3 pt-1">
                          {sug.originalEvidence && (
                            <div className="text-caption text-muted bg-surface/60 p-2 rounded border border-border/30">
                              <span className="font-semibold text-primary">Original Resume Evidence: </span>
                              <span className="italic">&ldquo;{sug.originalEvidence}&rdquo;</span>
                            </div>
                          )}

                          <div className="space-y-1.5">
                            <label className="text-caption font-semibold text-primary">
                              Improved Bullet (Editable):
                            </label>
                            <Textarea
                              value={currentEditBullet}
                              onChange={(e) => setEditingBullets((prev) => ({ ...prev, [sug.id]: e.target.value }))}
                              rows={2}
                              className="text-small bg-surface focus-visible:ring-accent"
                              disabled={isApplied}
                              placeholder="Review or edit the improved bullet..."
                            />
                          </div>

                          {/* Claim Validation Warnings if any */}
                          {sug.validation?.unsupportedClaims && sug.validation.unsupportedClaims.length > 0 && (
                            <div className="rounded bg-status-warning-soft/30 p-2.5 border border-status-warning/40 text-caption text-status-warning space-y-1">
                              <div className="font-semibold flex items-center gap-1.5">
                                <AlertTriangle className="h-3.5 w-3.5" />
                                Claim-Preservation Warning:
                              </div>
                              {sug.validation.unsupportedClaims.map((uc, i) => (
                                <div key={i} className="text-[11px]">
                                  • {uc.reason} <span className="text-primary font-medium">({uc.promptForUser})</span>
                                </div>
                              ))}
                            </div>
                          )}

                          <div className="flex justify-end items-center gap-2 pt-1">
                            {isApplied && targetedResumeId && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => router.push(`/resumes/targeted/${targetedResumeId}`)}
                                className="text-caption gap-1.5 border-accent/40 text-accent hover:bg-accent-soft/30"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                Open Workspace
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant={isApplied ? "outline" : "primary"}
                              disabled={isApplied || isApplying || !currentEditBullet.trim()}
                              onClick={() => handleApplyRemediation(sug)}
                              className="text-caption gap-1.5"
                            >
                              {isApplying ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : isApplied ? (
                                <Check className="h-3.5 w-3.5 text-status-success" />
                              ) : (
                                <PlusCircle className="h-3.5 w-3.5" />
                              )}
                              {isApplied ? "Applied to Targeted Resume" : "Apply to Targeted Resume"}
                            </Button>
                          </div>
                        </div>
                      ) : sug.actionType === "PromptForMissingFacts" || sug.actionType === "AddProjectContext" ? (
                        /* Case 2: Candidate Fact Prompt & Synthesis */
                        <div className="space-y-3 pt-1">
                          <div className="rounded bg-accent-soft/40 p-3 border border-accent/30 space-y-2">
                            <div className="text-small font-semibold text-primary flex items-center gap-1.5">
                              <Sparkles className="h-4 w-4 text-accent" />
                              {sug.missingFactPrompt || `Did you work with ${sug.requirementName}? Describe your real-world experience below:`}
                            </div>
                            <Textarea
                              value={candidateFacts[sug.id] || ""}
                              onChange={(e) => setCandidateFacts((prev) => ({ ...prev, [sug.id]: e.target.value }))}
                              rows={2}
                              className="text-small bg-surface focus-visible:ring-accent"
                              disabled={isApplied}
                              placeholder="e.g. Deployed microservices using Kubernetes on AWS EKS during my internship..."
                            />
                            <div className="flex justify-end">
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isSynthesizing || isApplied || !(candidateFacts[sug.id]?.trim()?.length > 4)}
                                onClick={() => handleSynthesizeBullet(sug)}
                                className="text-caption gap-1.5"
                              >
                                {isSynthesizing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5 text-accent" />}
                                Synthesize Truthful Bullet
                              </Button>
                            </div>
                          </div>

                          {/* Synthesized Bullet Preview */}
                          {currentEditBullet && (
                            <div className="space-y-2 pt-1 border-t border-border/40">
                              <label className="text-caption font-semibold text-primary">
                                Synthesized Bullet (Fact-Grounded & Editable):
                              </label>
                              <Textarea
                                value={currentEditBullet}
                                onChange={(e) => setEditingBullets((prev) => ({ ...prev, [sug.id]: e.target.value }))}
                                rows={2}
                                className="text-small bg-surface focus-visible:ring-accent"
                                disabled={isApplied}
                              />
                              <div className="flex justify-end items-center gap-2 pt-1">
                                {isApplied && targetedResumeId && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => router.push(`/resumes/targeted/${targetedResumeId}`)}
                                    className="text-caption gap-1.5 border-accent/40 text-accent hover:bg-accent-soft/30"
                                  >
                                    <ExternalLink className="h-3.5 w-3.5" />
                                    Open Workspace
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  variant={isApplied ? "outline" : "primary"}
                                  disabled={isApplied || isApplying || !currentEditBullet.trim()}
                                  onClick={() => handleApplyRemediation(sug)}
                                  className="text-caption gap-1.5"
                                >
                                  {isApplying ? (
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  ) : isApplied ? (
                                    <Check className="h-3.5 w-3.5 text-status-success" />
                                  ) : (
                                    <PlusCircle className="h-3.5 w-3.5" />
                                  )}
                                  {isApplied ? "Applied to Targeted Resume" : "Apply to Targeted Resume"}
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        /* Case 3: ExplainHardGap */
                        <div className="rounded bg-surface-raised p-3 border border-border/60 text-caption text-secondary space-y-1">
                          <span className="font-semibold text-primary">Why this gap cannot be phrased away: </span>
                          <span>The role demands seniority or multi-year duration beyond your current timeline. Focus on highlighting strong depth in adjacent areas.</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Target Job Intelligence Section (Phase 5.1) */}
          {jobIntelligence && (
            <Card className="border-accent/20 bg-surface">
              <CardHeader className="pb-3 border-b border-border/40">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-btn bg-accent-soft text-accent">
                      <Briefcase className="h-4 w-4" />
                    </div>
                    <div>
                      <CardTitle className="text-base font-semibold">
                        Target Job Intelligence: {jobIntelligence.jobInfo?.roleTitle || jobTitle}
                      </CardTitle>
                      <CardDescription>
                        Structured role criteria and requirements faithfully extracted from the job description
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {jobIntelligence.jobInfo?.seniorityLevel && jobIntelligence.jobInfo.seniorityLevel !== "Unspecified" && (
                      <Badge variant="accent">{jobIntelligence.jobInfo.seniorityLevel}</Badge>
                    )}
                    {jobIntelligence.jobInfo?.domain && (
                      <Badge variant="outline">{jobIntelligence.jobInfo.domain}</Badge>
                    )}
                    {jobIntelligence.jobInfo?.employmentType && (
                      <Badge variant="outline">{jobIntelligence.jobInfo.employmentType}</Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4 space-y-5">
                {/* Role Summary */}
                {jobIntelligence.summary && (
                  <p className="text-small text-secondary bg-surface-raised p-3 rounded-btn border border-border/50">
                    <span className="font-semibold text-primary">Role Summary: </span>
                    {jobIntelligence.summary}
                  </p>
                )}

                {/* Requirements Grid: Must-Have vs. Preferred */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Must-Have Requirements */}
                  <div className="space-y-2.5 rounded-btn border border-status-error/20 bg-status-error-soft/20 p-3.5">
                    <div className="flex items-center justify-between">
                      <span className="text-small font-semibold text-primary flex items-center gap-1.5">
                        <AlertTriangle className="h-4 w-4 text-status-warning" />
                        Must-Have Qualifications ({jobIntelligence.mustHaveSkills?.length || 0})
                      </span>
                    </div>
                    <div className="space-y-2">
                      {(!jobIntelligence.mustHaveSkills || jobIntelligence.mustHaveSkills.length === 0) ? (
                        <div className="text-caption text-secondary py-2">No explicit must-have requirements identified.</div>
                      ) : (
                        jobIntelligence.mustHaveSkills.map((s, idx) => (
                          <div key={`must-${s.name}-${idx}`} className="rounded bg-surface p-2 border border-border/40 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-body font-medium text-primary">{s.name}</span>
                              {s.category && <span className="text-[11px] text-muted">{s.category}</span>}
                            </div>
                            {s.sourceEvidence && (
                              <div className="text-caption text-secondary italic">
                                &ldquo;{s.sourceEvidence}&rdquo;
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Preferred Requirements */}
                  <div className="space-y-2.5 rounded-btn border border-accent/20 bg-accent-soft/20 p-3.5">
                    <div className="flex items-center justify-between">
                      <span className="text-small font-semibold text-primary flex items-center gap-1.5">
                        <Sparkles className="h-4 w-4 text-accent" />
                        Preferred & Bonus Qualifications ({jobIntelligence.preferredSkills?.length || 0})
                      </span>
                    </div>
                    <div className="space-y-2">
                      {(!jobIntelligence.preferredSkills || jobIntelligence.preferredSkills.length === 0) ? (
                        <div className="text-caption text-secondary py-2">No explicit bonus requirements identified.</div>
                      ) : (
                        jobIntelligence.preferredSkills.map((s, idx) => (
                          <div key={`pref-${s.name}-${idx}`} className="rounded bg-surface p-2 border border-border/40 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-body font-medium text-primary">{s.name}</span>
                              {s.category && <span className="text-[11px] text-muted">{s.category}</span>}
                            </div>
                            {s.sourceEvidence && (
                              <div className="text-caption text-secondary italic">
                                &ldquo;{s.sourceEvidence}&rdquo;
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                {/* Technical Stack Cloud */}
                {jobIntelligence.technicalStack && jobIntelligence.technicalStack.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-small font-semibold text-primary flex items-center gap-1.5">
                      <Code2 className="h-4 w-4 text-accent" />
                      Extracted Technical Stack ({jobIntelligence.technicalStack.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {jobIntelligence.technicalStack.map((tech, idx) => (
                        <Badge key={`tech-${tech}-${idx}`} variant="default" className="text-caption px-2 py-0.5">
                          {tech}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Core Responsibilities */}
                {jobIntelligence.responsibilities && jobIntelligence.responsibilities.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-small font-semibold text-primary flex items-center gap-1.5">
                      <ListChecks className="h-4 w-4 text-status-success" />
                      Key Responsibilities
                    </span>
                    <ul className="space-y-1 text-small text-secondary pl-5 list-disc">
                      {jobIntelligence.responsibilities.map((resp, idx) => (
                        <li key={`resp-${idx}`}>{resp}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Skill Matching Matrix */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Matching Skills */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-status-success flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Matching Skills ({matchingSkills.length})</span>
                  </CardTitle>
                </div>
                <CardDescription>Direct keyword and concept matches found</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {matchingSkills.length === 0 ? (
                  <div className="py-6 text-center text-small text-secondary">
                    No direct skill matches detected.
                  </div>
                ) : (
                  matchingSkills.map((s, idx) => (
                    <div
                      key={`${s.name}-${idx}`}
                      className="flex items-center justify-between rounded-btn border border-status-success/20 bg-status-success-soft/40 p-2.5"
                    >
                      <div>
                        <div className="text-body font-semibold text-primary">{s.name}</div>
                        <div className="text-caption text-secondary">{s.context}</div>
                      </div>
                      <Check className="h-4 w-4 text-status-success shrink-0" />
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Missing Skills */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-status-error flex items-center gap-2">
                    <XCircle className="h-4 w-4" />
                    <span>Missing Skills ({missingSkills.length})</span>
                  </CardTitle>
                </div>
                <CardDescription>Explicit requirements not detected in resume</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {missingSkills.length === 0 ? (
                  <div className="py-6 text-center text-small text-status-success font-medium">
                    <CheckCircle2 className="mx-auto h-6 w-6 mb-1 text-status-success" />
                    No critical missing skills!
                  </div>
                ) : (
                  missingSkills.map((s, idx) => (
                    <div
                      key={`${s.name}-${idx}`}
                      className="flex items-start justify-between rounded-btn border border-status-error/20 bg-status-error-soft/40 p-2.5 gap-2"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-body font-semibold text-primary">{s.name}</span>
                          <Badge
                            variant={s.priority === "High" ? "warning" : "default"}
                            className="text-[10px] px-1 py-0"
                          >
                            {s.priority}
                          </Badge>
                        </div>
                        <div className="text-caption text-secondary mt-0.5">{s.reason}</div>
                      </div>
                      <Button
                        onClick={() => handleAddMissingSkill(s.name)}
                        variant="outline"
                        size="sm"
                        className="text-caption h-7 px-2 shrink-0 border-status-error/40 text-status-error hover:bg-status-error-soft"
                      >
                        + Add Skill
                      </Button>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Partial / Related Skills */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-accent flex items-center gap-2">
                    <Sparkles className="h-4 w-4" />
                    <span>Partial Matches ({partialSkills.length})</span>
                  </CardTitle>
                </div>
                <CardDescription>Semantically adjacent skills to emphasize</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {partialSkills.length === 0 ? (
                  <div className="py-6 text-center text-small text-secondary">
                    No partial skill opportunities identified.
                  </div>
                ) : (
                  partialSkills.map((s, idx) => (
                    <div
                      key={`${s.name}-${idx}`}
                      className="rounded-btn border border-accent/20 bg-accent-soft/40 p-2.5 space-y-1"
                    >
                      <div className="text-body font-semibold text-primary">{s.name}</div>
                      <div className="text-caption text-secondary">{s.note}</div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalyzerPage() {
  return (
    <Suspense fallback={<LoadingState text="Loading ATS Analyzer..." />}>
      <AnalyzerContent />
    </Suspense>
  );
}
