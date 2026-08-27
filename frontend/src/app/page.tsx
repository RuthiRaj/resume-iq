"use client";

import React from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Zap,
  Layers,
  FileCheck,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CareerSignalMeter } from "@/components/common/career-signal-meter";
import { landingDemoProfile, landingDemoSignalData } from "@/lib/demo/landing-demo-data";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-page text-primary flex flex-col justify-between">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-[6px] bg-accent text-white font-semibold text-body">
              R
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-h1 font-semibold tracking-tight text-primary">ResumeIQ</span>
              <span className="rounded-[4px] bg-accent-soft px-1.5 py-0.5 text-caption font-semibold uppercase text-accent">
                Workspace
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 text-body text-secondary">
            <a href="#features" className="hover:text-primary transition-colors">
              Core Features
            </a>
            <a href="#signal" className="hover:text-primary transition-colors">
              Career Signal
            </a>
            <a href="#analyzer" className="hover:text-primary transition-colors">
              ATS Intelligence
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-body font-medium text-secondary hover:text-primary px-3 py-1.5"
            >
              Sign In
            </Link>
            <Link href="/login">
              <Button variant="primary" size="sm" className="gap-1.5">
                <span>Enter Platform</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-16 sm:py-24">
        <div className="mx-auto max-w-5xl px-4 text-center sm:px-6 lg:px-8">
          {/* Subtle Eyebrow Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent-soft px-3 py-1 text-caption font-semibold text-accent mb-6">
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI Career Workspace & Resume Intelligence</span>
          </div>

          {/* Display Heading */}
          <h1 className="text-display sm:text-[40px] sm:leading-[48px] font-semibold text-primary tracking-tight max-w-3xl mx-auto">
            Store your career information once. Let AI tailor resumes to every opportunity.
          </h1>

          {/* Subtitle */}
          <p className="mt-5 max-w-2xl mx-auto text-body sm:text-[15px] sm:leading-[24px] text-secondary">
            Maintain a unified career workspace. Generate job-specific resumes in seconds, run deep ATS
            relevance scoring, and eliminate repetitive formatting forever.
          </p>

          {/* Hero CTAs */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link href="/register">
              <Button size="lg" variant="primary" className="h-11 px-5 gap-2">
                <span>Open Career Workspace</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button size="lg" variant="outline" className="h-11 px-5 gap-2">
                <Zap className="h-4 w-4 text-accent" />
                <span>Test ATS Analyzer</span>
              </Button>
            </Link>
          </div>

          {/* Live Interactive Preview Card (Dedicated Fictional Public Dataset) */}
          <div id="signal" className="mt-14 rounded-card border border-border bg-surface p-6 sm:p-8 text-left shadow-subtle">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-border/80 gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-caption uppercase tracking-[0.4px] text-accent font-semibold">
                    Live Workspace Signal Demo
                  </span>
                  <span className="rounded-[4px] bg-status-success-soft px-1.5 py-0.5 text-caption font-semibold text-status-success">
                    Active Preview
                  </span>
                </div>
                <h3 className="mt-1 text-h2 font-semibold text-primary">
                  {landingDemoProfile.headline}
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <Link href="/login">
                  <Button variant="secondary" size="sm" className="gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Generate Tailored Resume</span>
                  </Button>
                </Link>
              </div>
            </div>

            {/* Signature Career Signal Meter Component with Static Demo Data */}
            <div className="mt-6">
              <CareerSignalMeter
                data={landingDemoSignalData}
                showBreakdownList={true}
                showActionLink={false}
                isInteractive={false}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section id="features" className="border-t border-border bg-surface py-16 sm:py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <span className="text-caption text-accent font-semibold tracking-[0.4px]">
              System Architecture
            </span>
            <h2 className="mt-1 text-h1 font-semibold text-primary">
              Built for high-caliber engineers and professionals
            </h2>
            <p className="mt-2 text-body text-secondary">
              A single source of truth for your professional journey, paired with fine-grained ATS intelligence.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Pillar 1 */}
            <div className="rounded-card border border-border bg-page p-6 space-y-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                <Layers className="h-5 w-5" />
              </div>
              <h3 className="text-h2 font-semibold text-primary">Unified Career Workspace</h3>
              <p className="text-small text-secondary leading-relaxed">
                Centralize your education, granular technical skills, impactful project metrics, verified
                certifications, and academic documents in one structured vault.
              </p>
            </div>

            {/* Pillar 2 */}
            <div id="analyzer" className="rounded-card border border-border bg-page p-6 space-y-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-[6px] bg-status-success-soft text-status-success">
                <Zap className="h-5 w-5" />
              </div>
              <h3 className="text-h2 font-semibold text-primary">Real-time ATS Scoring</h3>
              <p className="text-small text-secondary leading-relaxed">
                Compare any resume or profile against specific job descriptions. Get instant matching/missing
                skill matrices, keyword density analysis, and quantifiable suggestions.
              </p>
            </div>

            {/* Pillar 3 */}
            <div className="rounded-card border border-border bg-page p-6 space-y-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                <FileCheck className="h-5 w-5" />
              </div>
              <h3 className="text-h2 font-semibold text-primary">Section-Level AI Refinement</h3>
              <p className="text-small text-secondary leading-relaxed">
                Tailor individual project bullets and experience highlights with precision. Switch seamlessly
                between Modern, Minimal Swiss, Executive, and ATS Standard formats.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Trust & Guarantee Banner */}
      <section className="border-t border-border bg-page py-12">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6 rounded-card border border-border bg-surface p-6 sm:p-8">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-status-success text-small font-semibold">
                <ShieldCheck className="h-4 w-4" />
                <span>Isolated Cloud Privacy</span>
              </div>
              <h4 className="text-h2 font-semibold text-primary">Your career data stays strictly in your control</h4>
              <p className="text-small text-secondary max-w-lg">
                All data is scoped strictly to your authenticated account with rule-enforced access controls.
                Zero unauthorized telemetry or data sharing.
              </p>
            </div>

            <Link href="/register" className="flex-shrink-0">
              <Button variant="primary" size="md">
                Get Started Free
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border bg-surface py-8">
        <div className="mx-auto flex max-w-7xl flex-col sm:flex-row items-center justify-between px-4 sm:px-6 lg:px-8 gap-4 text-small text-secondary">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-primary">ResumeIQ</span>
            <span>&mdash; AI Career Workspace & Resume Intelligence</span>
          </div>
          <div>Enterprise-grade Career Intelligence Platform</div>
        </div>
      </footer>
    </div>
  );
}
