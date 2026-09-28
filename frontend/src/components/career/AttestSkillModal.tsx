"use client";

import React, { useState, useEffect } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ShieldAlert,
  CheckCircle2,
  HelpCircle,
  Layers,
  Loader2,
  Sparkles,
} from "lucide-react";

export const SKILL_CATEGORIES = [
  "Languages",
  "Frameworks & Libraries",
  "Cloud & DevOps",
  "Databases & Tools",
  "Methodologies & Soft Skills",
] as const;

export type SkillCategory = typeof SKILL_CATEGORIES[number];

export const PROFICIENCIES = [
  "Beginner",
  "Intermediate",
  "Advanced",
  "Expert",
] as const;

export type ProficiencyLevel = typeof PROFICIENCIES[number];

export interface AttestSkillFormData {
  name: string;
  category: SkillCategory;
  proficiency: ProficiencyLevel;
  yearsOfExperience: number;
  context: string;
}

interface AttestSkillModalProps {
  isOpen: boolean;
  onClose: () => void;
  skillName: string;
  onConfirm: (data: AttestSkillFormData) => Promise<void>;
  isSubmitting?: boolean;
}

/**
 * Heuristic suggesting an appropriate initial category for technical skills.
 * Never persists automatically; candidate reviews and confirms before submission.
 */
function suggestCategory(rawName: string): SkillCategory {
  const lower = rawName.toLowerCase().trim();

  // Languages
  if (
    /^(python|go|golang|typescript|javascript|java|c\+\+|cpp|c#|csharp|c|rust|ruby|php|swift|kotlin|scala|sql|r|dart)$/.test(
      lower
    )
  ) {
    return "Languages";
  }

  // Frameworks & Libraries
  if (
    /^(react|react\.js|next\.js|nextjs|vue|vue\.js|angular|fastapi|django|flask|express|express\.js|spring boot|springboot|\.net|dotnet|tailwind|tailwindcss)$/.test(
      lower
    ) ||
    lower.includes("framework") ||
    lower.includes("library")
  ) {
    return "Frameworks & Libraries";
  }

  // Cloud & DevOps
  if (
    /^(aws|amazon web services|gcp|google cloud|azure|microsoft azure|docker|kubernetes|k8s|terraform|ci\/cd|cicd|jenkins|github actions)$/.test(
      lower
    ) ||
    lower.includes("devops") ||
    lower.includes("cloud")
  ) {
    return "Cloud & DevOps";
  }

  // Databases & Tools
  if (
    /^(postgres|postgresql|mongo|mongodb|mysql|redis|sqlite|dynamodb|elasticsearch|cassandra|kafka|rabbitmq|git|graphql|grpc)$/.test(
      lower
    ) ||
    lower.includes("database") ||
    lower.includes("sql")
  ) {
    return "Databases & Tools";
  }

  // Methodologies & Soft Skills
  if (
    /^(agile|scrum|kanban|communication|leadership|mentorship|collaboration|teamwork|system design|microservices)$/.test(
      lower
    )
  ) {
    return "Methodologies & Soft Skills";
  }

  return "Languages";
}

export function AttestSkillModal({
  isOpen,
  onClose,
  skillName,
  onConfirm,
  isSubmitting = false,
}: AttestSkillModalProps) {
  const [name, setName] = useState(skillName);
  const [category, setCategory] = useState<SkillCategory>("Languages");
  const [proficiency, setProficiency] = useState<ProficiencyLevel>("Intermediate");
  const [yearsOfExperience, setYearsOfExperience] = useState<number>(1);
  const [context, setContext] = useState("");
  const [confirmedTruthful, setConfirmedTruthful] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && skillName) {
      setName(skillName);
      setCategory(suggestCategory(skillName));
      setProficiency("Intermediate");
      setYearsOfExperience(1);
      setContext("");
      setConfirmedTruthful(false);
      setErrorMessage(null);
    }
  }, [isOpen, skillName]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!confirmedTruthful) {
      setErrorMessage("Please confirm that this skill claim is truthful and accurate.");
      return;
    }

    if (!name.trim()) {
      setErrorMessage("Skill name cannot be empty.");
      return;
    }

    if (context.trim().length < 5) {
      setErrorMessage("Please provide substantive context on how or where you used this skill (min 5 characters).");
      return;
    }

    setErrorMessage(null);

    try {
      await onConfirm({
        name: name.trim(),
        category,
        proficiency,
        yearsOfExperience: Math.max(0, Number(yearsOfExperience) || 0),
        context: context.trim(),
      });
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to save attested skill. Please retry.");
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Attest Missing Skill"
      description="Record practical experience for a target job requirement without fabricating unverified evidence."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="flex items-center gap-2 rounded-btn bg-status-error-soft p-3 text-status-error text-small font-medium border border-status-error/20">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Evidence Grounding Explainer Banner */}
        <div className="rounded-card bg-amber-500/10 border border-amber-500/20 p-3.5 space-y-1.5">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-small">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>Anti-Hallucination & Evidence Gate</span>
          </div>
          <p className="text-caption text-secondary leading-relaxed">
            Attesting this skill records it in your Workspace as{" "}
            <strong className="text-primary">User Attested (Unverified)</strong> with explicit provenance.
            It will not be treated as independently verified until supported by project or work experience.
          </p>
        </div>

        {/* Skill Name */}
        <div className="space-y-1.5">
          <label className="text-small font-medium text-primary flex items-center justify-between">
            <span>Skill Name *</span>
            <span className="text-[11px] text-muted">From JD requirement</span>
          </label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Python, Docker, React"
            required
            className="text-body"
          />
        </div>

        {/* Category & Proficiency Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Category *</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as SkillCategory)}
              className="w-full rounded-input border border-border bg-surface px-3 py-2 text-body text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {SKILL_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Proficiency *</label>
            <select
              value={proficiency}
              onChange={(e) => setProficiency(e.target.value as ProficiencyLevel)}
              className="w-full rounded-input border border-border bg-surface px-3 py-2 text-body text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {PROFICIENCIES.map((prof) => (
                <option key={prof} value={prof}>
                  {prof}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Years of Experience */}
        <div className="space-y-1.5">
          <label className="text-small font-medium text-primary flex items-center justify-between">
            <span>Years of Practical Experience *</span>
            <span className="text-[11px] text-muted">Enter truthful duration</span>
          </label>
          <Input
            type="number"
            min={0}
            max={50}
            step={0.5}
            value={yearsOfExperience}
            onChange={(e) => setYearsOfExperience(Number(e.target.value))}
            required
            className="text-body"
          />
        </div>

        {/* Real-World Context / How Used */}
        <div className="space-y-1.5">
          <label className="text-small font-medium text-primary flex items-center justify-between">
            <span>Where or How Did You Use This Skill? *</span>
            <span className="text-[11px] text-muted">Min 5 chars</span>
          </label>
          <Textarea
            rows={3}
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g. Applied during backend microservices refactoring at prior company, or built personal production pipeline..."
            required
            className="text-body leading-relaxed"
          />
        </div>

        {/* Truthfulness Confirmation Checkbox */}
        <div className="rounded-card bg-surface border border-border/80 p-3 flex items-start gap-2.5">
          <input
            type="checkbox"
            id="confirm-truthful-checkbox"
            checked={confirmedTruthful}
            onChange={(e) => setConfirmedTruthful(e.target.checked)}
            className="mt-0.5 rounded border-border text-accent focus:ring-accent"
          />
          <label htmlFor="confirm-truthful-checkbox" className="text-caption text-primary select-none cursor-pointer leading-snug">
            I explicitly attest that I have hands-on practical familiarity with this technology. I understand this skill will be stored with <strong className="text-amber-600 dark:text-amber-400">User Attested</strong> provenance.
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={isSubmitting || !confirmedTruthful}
            className="gap-1.5"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Saving Attestation...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Confirm & Attest Skill</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
