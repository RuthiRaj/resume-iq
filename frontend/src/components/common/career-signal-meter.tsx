"use client";

import React from "react";
import Link from "next/link";
import { useCareer } from "@/lib/store";
import { calculateCareerSignal, cn } from "@/lib/utils";
import { ArrowUpRight, Sparkles } from "lucide-react";

export interface SignalBreakdownItem {
  name: string;
  score: number;
  color: string;
  key: string;
}

export interface CareerSignalData {
  overall: number;
  breakdown: SignalBreakdownItem[];
}

export interface CareerSignalMeterViewProps {
  overall: number;
  breakdown: SignalBreakdownItem[];
  showBreakdownList?: boolean;
  showActionLink?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
  isInteractive?: boolean;
}

/**
 * Pure Presentational Meter View
 * Independent of any data source or Firebase authentication state.
 */
export function CareerSignalMeterView({
  overall,
  breakdown,
  showBreakdownList = true,
  showActionLink = true,
  className,
  size = "md",
  isInteractive = true,
}: CareerSignalMeterViewProps) {
  // Calculate sum of scores for relative width normalization in horizontal bar
  const totalScorePoints = breakdown.reduce((sum, b) => sum + b.score, 0);
  const barHeight = size === "sm" ? "h-2" : size === "lg" ? "h-4" : "h-3";

  return (
    <div className={cn("w-full space-y-4", className)}>
      {/* Header with Title and Overall % */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded-[4px] bg-accent-soft text-accent">
            <Sparkles className="h-3 w-3" />
          </div>
          <span className="text-caption text-secondary font-semibold">Career Signal Completeness</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-h2 font-semibold text-primary">{overall}%</span>
          <span className="rounded-[4px] bg-accent-soft px-1.5 py-0.5 text-caption font-semibold text-accent">
            {overall >= 90 ? "Excellent" : overall >= 75 ? "Strong" : "In Progress"}
          </span>
        </div>
      </div>

      {/* Signature Multi-Segment Horizontal Bar */}
      <div
        className={cn(
          "relative flex w-full overflow-hidden rounded-full bg-[#E4E7EC] p-0.5 gap-1",
          barHeight
        )}
      >
        {breakdown.map((item) => {
          const segmentWidth = totalScorePoints > 0 ? (item.score / totalScorePoints) * 100 : 0;
          if (segmentWidth <= 0) return null;

          return (
            <div
              key={item.key}
              title={`${item.name}: ${item.score}%`}
              style={{
                width: `${segmentWidth}%`,
                backgroundColor: item.color,
              }}
              className="h-full rounded-full transition-all duration-500 ease-out"
            />
          );
        })}
      </div>

      {/* Per-Category Percentages Listed Below the Bar */}
      {showBreakdownList && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6 pt-1">
          {breakdown.map((item) => {
            const cardContent = (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-small text-secondary group-hover:text-primary transition-colors">
                      {item.name}
                    </span>
                  </div>
                  {isInteractive && (
                    <ArrowUpRight className="h-3 w-3 text-muted opacity-0 group-hover:opacity-100 group-hover:text-accent transition-all" />
                  )}
                </div>
                <div className="mt-2 flex items-baseline justify-between">
                  <span className="text-body font-semibold text-primary">{item.score}%</span>
                  <span className="text-caption text-muted">
                    {item.score >= 90 ? "Complete" : item.score >= 50 ? "Good" : "Needs Info"}
                  </span>
                </div>
              </>
            );

            if (!isInteractive) {
              return (
                <div
                  key={item.key}
                  className="flex flex-col justify-between rounded-btn border border-border bg-surface p-2.5"
                >
                  {cardContent}
                </div>
              );
            }

            return (
              <Link
                key={item.key}
                href={`/workspace/${item.key === "certifications" ? "certifications" : item.key}`}
                className="group flex flex-col justify-between rounded-btn border border-border bg-surface p-2.5 hover:border-accent/40 hover:bg-page transition-all"
              >
                {cardContent}
              </Link>
            );
          })}
        </div>
      )}

      {/* Action link */}
      {showActionLink && overall < 100 && (
        <div className="flex items-center justify-between rounded-[8px] bg-accent-soft/50 border border-accent/20 px-3 py-2 text-small text-secondary">
          <span>Boost your signal to 100% for maximum ATS job relevance</span>
          <Link
            href="/workspace/experience"
            className="font-medium text-accent hover:underline inline-flex items-center gap-1"
          >
            Optimize now &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}

export interface CareerSignalMeterProps {
  data?: CareerSignalData;
  showBreakdownList?: boolean;
  showActionLink?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
  isInteractive?: boolean;
}

/**
 * Smart / Contextual CareerSignalMeter
 * If `data` is provided, acts as a pure presentational component without hooking into Firebase.
 * If `data` is omitted, connects to the authenticated user's live Firestore store.
 */
export function CareerSignalMeter({
  data,
  showBreakdownList = true,
  showActionLink = true,
  className,
  size = "md",
  isInteractive = true,
}: CareerSignalMeterProps) {
  // If static data is provided (e.g. on Landing Page), bypass useCareer entirely
  if (data) {
    return (
      <CareerSignalMeterView
        overall={data.overall}
        breakdown={data.breakdown}
        showBreakdownList={showBreakdownList}
        showActionLink={showActionLink}
        className={className}
        size={size}
        isInteractive={isInteractive}
      />
    );
  }

  return (
    <LiveCareerSignalMeter
      showBreakdownList={showBreakdownList}
      showActionLink={showActionLink}
      className={className}
      size={size}
      isInteractive={isInteractive}
    />
  );
}

function LiveCareerSignalMeter({
  showBreakdownList = true,
  showActionLink = true,
  className,
  size = "md",
  isInteractive = true,
}: Omit<CareerSignalMeterProps, "data">) {
  const { profile, education, skills, projects, experience, certifications } = useCareer();

  const { overall, breakdown } = calculateCareerSignal({
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
  });

  return (
    <CareerSignalMeterView
      overall={overall}
      breakdown={breakdown}
      showBreakdownList={showBreakdownList}
      showActionLink={showActionLink}
      className={className}
      size={size}
      isInteractive={isInteractive}
    />
  );
}
