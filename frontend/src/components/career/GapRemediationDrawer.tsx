"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { GapRemediationStrategy } from "@/types/career";
import {
  BookOpen,
  CheckCircle2,
  Code2,
  ExternalLink,
  Layers,
  Sparkles,
  Target,
  Wrench,
  AlertCircle,
} from "lucide-react";

interface GapRemediationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  remediations: GapRemediationStrategy[];
  targetRole: string;
}

export function GapRemediationDrawer({
  isOpen,
  onClose,
  remediations,
  targetRole,
}: GapRemediationDrawerProps) {
  const [selectedReq, setSelectedReq] = useState<string | null>(
    remediations.length > 0 ? remediations[0].requirementName : null
  );

  const activeStrategy =
    remediations.find((r) => r.requirementName === selectedReq) ||
    remediations[0] ||
    null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Experiential Gap Remediation Blueprints"
      maxWidth="xl"
    >
      <div className="space-y-6">
        {/* Header Notice */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 flex items-start space-x-3">
          <Sparkles className="w-5 h-5 text-primary-400 mt-0.5 shrink-0" />
          <div className="text-xs text-slate-300 space-y-1">
            <p className="font-medium text-slate-200">
              Zero-Hallucination Career Intelligence for {targetRole}
            </p>
            <p>
              ResumeIQ will never fabricate unverified experience. The actionable learning paths and verifiable portfolio
              blueprints below guide you in acquiring and demonstrating genuine competencies required for this role.
            </p>
          </div>
        </div>

        {/* Multi-Tab Selector for Missing Requirements */}
        {remediations.length > 1 && (
          <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
            {remediations.map((strat) => {
              const isSelected =
                (selectedReq || remediations[0]?.requirementName) ===
                strat.requirementName;
              return (
                <button
                  key={strat.requirementName}
                  type="button"
                  onClick={() => setSelectedReq(strat.requirementName)}
                  className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all ${
                    isSelected
                      ? "bg-primary-600 text-white shadow-sm"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700"
                  }`}
                >
                  {strat.requirementName}
                </button>
              );
            })}
          </div>
        )}

        {activeStrategy && (
          <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-1">
            {/* Requirement Overview */}
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="text-base font-semibold text-slate-100">
                  {activeStrategy.requirementName}
                </span>
                <Badge
                  variant="outline"
                  className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-xs"
                >
                  {activeStrategy.severity}
                </Badge>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/30 p-3 rounded border border-slate-800/60">
              {activeStrategy.remediationGuidance}
            </p>

            {/* Actionable Learning Paths */}
            {activeStrategy.learningPaths.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  <BookOpen className="w-4 h-4 text-emerald-400" />
                  <span>Actionable Learning Curriculum</span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {activeStrategy.learningPaths.map((lp, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-900/40 border border-slate-800 rounded-lg p-4 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-slate-200">
                          {lp.title}
                        </h4>
                        <Badge variant="secondary" className="text-xs">
                          {lp.estimatedWeeks} Weeks Estimated
                        </Badge>
                      </div>

                      <div className="space-y-1.5">
                        <span className="text-[11px] font-medium text-slate-400">
                          Key Milestones:
                        </span>
                        <ul className="space-y-1">
                          {lp.keyMilestones.map((ms, mIdx) => (
                            <li
                              key={mIdx}
                              className="text-xs text-slate-300 flex items-start space-x-2"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                              <span>{ms}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {lp.authoritativeDocsUrl && (
                        <a
                          href={lp.authoritativeDocsUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1.5 text-xs text-primary-400 hover:text-primary-300 hover:underline pt-1"
                        >
                          <span>Official Documentation & Guide</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Verifiable Project Blueprints */}
            {activeStrategy.projectBlueprints.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2 text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  <Code2 className="w-4 h-4 text-primary-400" />
                  <span>Verifiable Portfolio Project Blueprint</span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {activeStrategy.projectBlueprints.map((proj, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-900/40 border border-slate-800 rounded-lg p-4 space-y-3"
                    >
                      <h4 className="text-xs font-semibold text-slate-200">
                        {proj.projectTitle}
                      </h4>
                      <p className="text-xs text-slate-300">
                        {proj.problemStatement}
                      </p>

                      <div className="space-y-1.5 pt-1">
                        <span className="text-[11px] font-medium text-slate-400">
                          Architecture Components:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {proj.architectureComponents.map((comp, cIdx) => (
                            <Badge
                              key={cIdx}
                              variant="outline"
                              className="text-[11px] bg-slate-800/60 border-slate-700 text-slate-300"
                            >
                              {comp}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-slate-800">
                        <span className="text-[11px] font-medium text-slate-400">
                          Verification Checklist:
                        </span>
                        <ul className="space-y-1">
                          {proj.verificationChecklist.map((item, vIdx) => (
                            <li
                              key={vIdx}
                              className="text-xs text-slate-300 flex items-start space-x-2"
                            >
                              <div className="w-1.5 h-1.5 rounded-full bg-primary-400 mt-1.5 shrink-0" />
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-slate-800">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
