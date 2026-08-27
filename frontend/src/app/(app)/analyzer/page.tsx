"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useCareer } from "@/lib/store";
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
} from "lucide-react";

function AnalyzerContent() {
  const searchParams = useSearchParams();
  const resumeIdParam = searchParams.get("resumeId");

  const { resumes, skills, addSkill, saveAtsAnalysis } = useCareer();
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
  const [relevanceScore, setRelevanceScore] = useState(0);
  const [keywordScore, setKeywordScore] = useState(0);
  const [impactScore, setImpactScore] = useState(0);
  const [formatScore, setFormatScore] = useState(0);
  const [summaryFeedback, setSummaryFeedback] = useState("");

  const [missingSkills, setMissingSkills] = useState<Array<{ name: string; priority: string; reason: string }>>([]);
  const [matchingSkills, setMatchingSkills] = useState<Array<{ name: string; context: string }>>([]);
  const [partialSkills, setPartialSkills] = useState<Array<{ name: string; note: string }>>([]);

  // Automatically restore saved analysis when selecting an analyzed resume
  useEffect(() => {
    if (selectedResumeId && selectedResumeId !== "workspace") {
      const found = resumes.find((r) => r.id === selectedResumeId);
      if (found && typeof found.atsScore === "number") {
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
        }
        setHasAnalyzed(true);
      }
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
      setHasAnalyzed(true);

      // Persist to client store state for reactive UI updates
      if (selectedResumeId && selectedResumeId !== "workspace") {
        await saveAtsAnalysis(selectedResumeId, {
          atsScore: data.atsScore,
          scoreBreakdown: data.scoreBreakdown,
          targetRole: jobTitle.trim(),
          targetCompany: jobCompany.trim(),
          analysisResults: {
            summaryFeedback: data.summaryFeedback,
            matchingSkills: data.matchingSkills,
            missingSkills: data.missingSkills,
            partialSkills: data.partialSkills,
            metadata: data.metadata,
          },
        });
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze resume. Please try again.");
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
    setErrorMessage(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-h1 font-semibold text-primary">Resume ATS & Relevance Analyzer</h1>
        <p className="text-small text-secondary mt-0.5">
          Scan your resumes against target job descriptions using Google AI to identify keyword gaps, semantic density, and ATS readiness.
        </p>
      </div>

      {/* Error Alert if API error */}
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
                  <span>Evaluating ATS Match with Google AI...</span>
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
                <span className="font-semibold text-primary">Run ATS Deep Scan</span> to evaluate keyword match density and discover missing skills.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6 animate-in fade-in-50 duration-300">
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
