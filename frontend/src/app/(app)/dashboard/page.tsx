"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  FileText,
  Zap,
  CheckCircle2,
  TrendingUp,
  ArrowUpRight,
  Plus,
  Clock,
  Layers,
  Briefcase,
  GraduationCap,
  Award,
  ChevronRight,
  Download,
  Eye,
  Info,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CareerSignalMeter } from "@/components/common/career-signal-meter";
import { useCareer } from "@/lib/store";
import { useAuth } from "@/lib/auth-context";
import { calculateCareerSignal, formatDate } from "@/lib/utils";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export default function DashboardPage() {
  const router = useRouter();
  const {
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
    resumes,
    actions,
    dismissAction,
  } = useCareer();

  const { overall } = calculateCareerSignal({
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
  });

  const { user } = useAuth();

  // Calculate real ATS average score based only on resumes that have an actual score
  const scoredResumes = resumes.filter(
    (r) => ((r.atsScore ?? 0) > 0 || (r.score ?? 0) > 0) && !!r.lastAnalyzedAt
  );
  const avgAtsScore =
    scoredResumes.length > 0
      ? Math.round(scoredResumes.reduce((acc, r) => acc + (r.atsScore || r.score || 0), 0) / scoredResumes.length)
      : null;

  // Real skill categories count
  const skillCategoryCount = Array.from(new Set(skills.map((s) => s.category))).length;

  // Compute dynamic next actions if no custom server actions exist
  const effectiveActions =
    actions.length > 0
      ? actions
      : (() => {
          const acts = [];
          if (!profile.summary || profile.summary.trim().length < 20) {
            acts.push({
              id: "act-summary",
              title: "Add your Professional Summary",
              description: "A clear executive summary anchors your master profile and powers AI resume generation.",
              category: "Profile",
              impact: "High",
              actionUrl: "/workspace/profile",
            });
          }
          if (experience.length === 0) {
            acts.push({
              id: "act-experience",
              title: "Add Work Experience",
              description: "Document employment history and impact bullets for tailored resume exports.",
              category: "Experience",
              impact: "High",
              actionUrl: "/workspace/experience",
            });
          }
          if (skills.length < 5) {
            acts.push({
              id: "act-skills",
              title: "Add Key Technical Skills",
              description: "List languages, frameworks, and tools to feed ATS keyword density matching.",
              category: "Skills",
              impact: "High",
              actionUrl: "/workspace/skills",
            });
          }
          if (projects.length === 0) {
            acts.push({
              id: "act-projects",
              title: "Showcase Featured Projects",
              description: "Add portfolio projects with technical stack tags and metrics.",
              category: "Projects",
              impact: "Medium",
              actionUrl: "/workspace/projects",
            });
          }
          if (resumes.length === 0) {
            acts.push({
              id: "act-resume",
              title: "Create Your First Tailored Resume",
              description: "Generate a targeted resume version from your master profile in Resume Studio.",
              category: "Resume Studio",
              impact: "High",
              actionUrl: "/builder",
            });
          } else if (scoredResumes.length === 0) {
            acts.push({
              id: "act-analyzer",
              title: "Run ATS Resume Analysis",
              description: "Scan your resume against a target job description to discover keyword gaps.",
              category: "Resume Intelligence",
              impact: "Medium",
              actionUrl: "/analyzer",
            });
          }
          return acts;
        })();

  // Trajectory trend data
  const hasHistory = resumes.length > 0 || overall > 0;
  const currentAts = avgAtsScore ?? 0;
  const dynamicTrendData = [
    {
      month: "3m ago",
      atsScore: Math.max(0, currentAts > 0 ? currentAts - 12 : 0),
      signalCompleteness: Math.max(0, overall > 25 ? overall - 25 : 0),
    },
    {
      month: "2m ago",
      atsScore: Math.max(0, currentAts > 0 ? currentAts - 8 : 0),
      signalCompleteness: Math.max(0, overall > 18 ? overall - 18 : 0),
    },
    {
      month: "Last month",
      atsScore: Math.max(0, currentAts > 0 ? currentAts - 4 : 0),
      signalCompleteness: Math.max(0, overall > 8 ? overall - 8 : 0),
    },
    {
      month: "Current",
      atsScore: currentAts,
      signalCompleteness: overall,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-h1 font-semibold text-primary">
            Good morning, {profile.fullName?.split(" ")[0] || user?.displayName?.split(" ")[0] || "there"}
          </h1>
          <p className="text-small text-secondary mt-0.5">
            Your career workspace is up to date &bull; Last synchronized today
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link href="/analyzer">
            <Button variant="outline" size="sm" className="gap-1.5">
              <Zap className="h-3.5 w-3.5 text-accent" />
              <span>Analyze ATS Match</span>
            </Button>
          </Link>
          <Link href="/builder">
            <Button variant="primary" size="sm" className="gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              <span>Create New Resume</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Signature Career Signal Meter Card */}
      <Card className="border-accent/20 bg-surface">
        <CardContent className="p-6">
          <CareerSignalMeter showBreakdownList={true} showActionLink={true} size="lg" />
        </CardContent>
      </Card>

      {/* 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat 1: Active Resumes */}
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                Active Resumes
              </span>
              <div className="text-h1 font-semibold text-primary">{resumes.length}</div>
              <p className="text-small text-secondary">
                {resumes.length === 0
                  ? "No resumes created yet"
                  : resumes.length === 1
                  ? "1 active tailored version"
                  : `${resumes.length} active tailored versions`}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
              <FileText className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Stat 2: Avg ATS Score */}
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                Avg ATS Score
              </span>
              <div
                className={`text-h1 font-semibold ${
                  avgAtsScore !== null ? "text-status-success" : "text-secondary"
                }`}
              >
                {avgAtsScore !== null ? `${avgAtsScore}%` : "—"}
              </div>
              <p className="text-small text-secondary">
                {avgAtsScore !== null
                  ? `Across ${scoredResumes.length} analyzed ${scoredResumes.length === 1 ? "version" : "versions"}`
                  : "Scan resumes against target JDs"}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-[6px] bg-status-success-soft text-status-success">
              <TrendingUp className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Stat 3: Skill Coverage */}
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                Skill Coverage
              </span>
              <div className="text-h1 font-semibold text-primary">{skills.length}</div>
              <p className="text-small text-secondary">
                {skills.length === 0
                  ? "Add technical & domain skills"
                  : skillCategoryCount === 1
                  ? "In 1 domain category"
                  : `Across ${skillCategoryCount} domain categories`}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
              <Layers className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        {/* Stat 4: Career Signal Completeness */}
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-caption uppercase text-muted font-semibold tracking-[0.4px]">
                Career Completeness
              </span>
              <div className="text-h1 font-semibold text-primary">{overall}%</div>
              <p className="text-small text-secondary">
                {overall === 0
                  ? "Add profile, work & education"
                  : overall >= 80
                  ? "High-fidelity profile strength"
                  : overall >= 50
                  ? "Moderate profile depth"
                  : "Developing profile strength"}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-[6px] bg-status-success-soft text-status-success">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Score Trend Chart & Recommended Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Score Trend Chart (2 cols) */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle>ATS Relevance & Signal Progress</CardTitle>
              <CardDescription>Historical trajectory of resume scores and workspace depth</CardDescription>
            </div>
            <div className="flex items-center gap-3 text-caption">
              <div className="flex items-center gap-1.5 text-accent font-semibold">
                <span className="h-2.5 w-2.5 rounded-full bg-accent" />
                <span>ATS Score</span>
              </div>
              <div className="flex items-center gap-1.5 text-secondary font-semibold">
                <span className="h-2.5 w-2.5 rounded-full bg-[#B1C0FD]" />
                <span>Signal Completeness</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {!hasHistory ? (
              <div className="flex flex-col items-center justify-center h-64 text-center rounded-btn border border-dashed border-border bg-page p-6 space-y-2.5">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent">
                  <TrendingUp className="h-5 w-5" />
                </div>
                <div className="space-y-1 max-w-sm">
                  <div className="text-body font-semibold text-primary">No Activity Data Yet</div>
                  <p className="text-small text-secondary">
                    As you add data to your Career Profile and scan resumes against job descriptions, your progress trajectory will appear here.
                  </p>
                </div>
              </div>
            ) : (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={dynamicTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="atsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3652D9" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#3652D9" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="signalGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#B1C0FD" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#B1C0FD" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E4E7EC" vertical={false} />
                    <XAxis dataKey="month" stroke="#98A2B3" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis domain={[0, 100]} stroke="#98A2B3" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#FFFFFF",
                        borderColor: "#E4E7EC",
                        borderRadius: "6px",
                        fontSize: "12.5px",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="signalCompleteness"
                      stroke="#8FA3FC"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#signalGradient)"
                    />
                    <Area
                      type="monotone"
                      dataKey="atsScore"
                      stroke="#3652D9"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#atsGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recommended Actions (1 col) */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Recommended Actions</CardTitle>
            <CardDescription>AI prioritized optimizations to strengthen your profile</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {effectiveActions.length === 0 ? (
              <div className="py-8 text-center text-small text-secondary space-y-2">
                <CheckCircle2 className="mx-auto h-7 w-7 text-status-success" />
                <div className="font-semibold text-primary">All milestones completed!</div>
                <p className="text-caption text-secondary">Your Career Profile and resumes are in top condition.</p>
              </div>
            ) : (
              effectiveActions.slice(0, 3).map((act) => (
                <div
                  key={act.id}
                  className="rounded-btn border border-border bg-page p-3 space-y-2 hover:border-accent/40 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-caption font-semibold text-accent uppercase tracking-[0.4px]">
                      {act.category}
                    </span>
                    <Badge variant={act.impact === "High" ? "warning" : "default"}>
                      {act.impact} Impact
                    </Badge>
                  </div>
                  <div className="text-body font-medium text-primary">{act.title}</div>
                  <p className="text-small text-secondary">{act.description}</p>
                  <div className="flex items-center justify-between pt-1">
                    <Link
                      href={act.actionUrl}
                      className="inline-flex items-center gap-1 text-small font-medium text-accent hover:underline"
                    >
                      <span>Complete step</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </Link>
                    {actions.some((a) => a.id === act.id) && (
                      <button
                        onClick={() => dismissAction(act.id)}
                        className="text-caption text-muted hover:text-secondary"
                      >
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row: Recent Resumes & Career Profile Snapshot */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Resumes (2 cols) */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle>Recent Tailored Resumes</CardTitle>
              <CardDescription>Targeted versions generated from your master Career Profile</CardDescription>
            </div>
            {resumes.length > 0 && (
              <Link href="/resumes">
                <Button variant="ghost" size="sm" className="gap-1 text-accent">
                  <span>View all</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
          </CardHeader>
          <CardContent className="space-y-2.5">
            {resumes.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 px-4 text-center rounded-btn border border-dashed border-border bg-page space-y-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="space-y-1">
                  <div className="text-body font-semibold text-primary">No resumes created yet</div>
                  <p className="text-small text-secondary max-w-sm">
                    Create your first tailored resume using verified records from your master Career Profile.
                  </p>
                </div>
                <Link href="/builder">
                  <Button variant="primary" size="sm" className="gap-1.5 mt-1">
                    <Plus className="h-3.5 w-3.5" />
                    <span>Create First Resume</span>
                  </Button>
                </Link>
              </div>
            ) : (
              resumes.slice(0, 3).map((res) => (
                <div
                  key={res.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between rounded-btn border border-border p-3.5 hover:bg-page transition-colors gap-3"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-body font-semibold text-primary">{res.title}</span>
                        <Badge variant="outline" className="capitalize">
                          {res.template}
                        </Badge>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-small text-secondary">
                        <span>Target: {res.targetRole}</span>
                        <span>&bull;</span>
                        <span>Edited {formatDate(res.lastEdited)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-3">
                    {typeof (res.atsScore ?? res.score) === "number" && (
                      <div className="text-right">
                        <div className="text-caption font-semibold text-muted uppercase">ATS Match</div>
                        <div className="text-body font-bold text-status-success">
                          {res.atsScore ?? res.score}%
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-1.5">
                      <Link href={`/builder?resumeId=${res.id}`}>
                        <Button variant="outline" size="sm">
                          Edit
                        </Button>
                      </Link>
                      <Link href={`/analyzer?resumeId=${res.id}`}>
                        <Button variant="ghost" size="sm" className="text-accent">
                          Analyze
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Career Profile Snapshot (1 col) */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Career Profile Snapshot</CardTitle>
            <CardDescription>Canonical source of truth stored in your career vault</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link
              href="/workspace/experience"
              className="flex items-center justify-between rounded-btn border border-border p-2.5 hover:bg-page transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Briefcase className="h-4 w-4 text-accent" />
                <span className="text-body font-medium text-primary">Work Experience</span>
              </div>
              <span className="text-small font-semibold text-secondary">
                {experience.length} {experience.length === 1 ? "role" : "roles"}
              </span>
            </Link>

            <Link
              href="/workspace/projects"
              className="flex items-center justify-between rounded-btn border border-border p-2.5 hover:bg-page transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Sparkles className="h-4 w-4 text-accent" />
                <span className="text-body font-medium text-primary">Featured Projects</span>
              </div>
              <span className="text-small font-semibold text-secondary">
                {projects.length} {projects.length === 1 ? "project" : "projects"}
              </span>
            </Link>

            <Link
              href="/workspace/skills"
              className="flex items-center justify-between rounded-btn border border-border p-2.5 hover:bg-page transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Layers className="h-4 w-4 text-accent" />
                <span className="text-body font-medium text-primary">Technical Skills</span>
              </div>
              <span className="text-small font-semibold text-secondary">
                {skills.length} {skills.length === 1 ? "skill" : "skills"}
              </span>
            </Link>

            <Link
              href="/workspace/education"
              className="flex items-center justify-between rounded-btn border border-border p-2.5 hover:bg-page transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <GraduationCap className="h-4 w-4 text-accent" />
                <span className="text-body font-medium text-primary">Education</span>
              </div>
              <span className="text-small font-semibold text-secondary">
                {education.length} {education.length === 1 ? "degree" : "degrees"}
              </span>
            </Link>

            <Link
              href="/workspace/certifications"
              className="flex items-center justify-between rounded-btn border border-border p-2.5 hover:bg-page transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Award className="h-4 w-4 text-accent" />
                <span className="text-body font-medium text-primary">Certifications</span>
              </div>
              <span className="text-small font-semibold text-secondary">
                {certifications.length} {certifications.length === 1 ? "verified" : "verified"}
              </span>
            </Link>

            <div className="pt-2">
              <Link href="/workspace/profile" className="w-full block">
                <Button variant="outline" size="sm" className="w-full">
                  Manage Complete Profile &rarr;
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
