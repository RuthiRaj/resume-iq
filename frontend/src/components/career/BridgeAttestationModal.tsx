"use client";

import React, { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TransferableSkillBridge, CandidateAttestationRequest, AttestSkillResponse } from "@/types/career";
import {
  ShieldCheck,
  Sparkles,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Clock,
  Layers,
} from "lucide-react";

interface BridgeAttestationModalProps {
  isOpen: boolean;
  onClose: () => void;
  bridge: TransferableSkillBridge | null;
  variantId: string;
  variantVersion: number;
  authToken: string;
  onAttestationSuccess: (response: AttestSkillResponse) => void;
}

export function BridgeAttestationModal({
  isOpen,
  onClose,
  bridge,
  variantId,
  variantVersion,
  authToken,
  onAttestationSuccess,
}: BridgeAttestationModalProps) {
  const [attestedContext, setAttestedContext] = useState("");
  const [attestedActions, setAttestedActions] = useState("");
  const [durationOrScale, setDurationOrScale] = useState("");
  const [confirmedTruthful, setConfirmedTruthful] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!bridge) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmedTruthful) {
      setErrorMessage("Please confirm that this attestation is truthful and accurate.");
      return;
    }
    if (attestedContext.trim().length < 5 || attestedActions.trim().length < 5) {
      setErrorMessage("Please provide substantive details for both context and actions.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const payload: CandidateAttestationRequest = {
      variantId,
      requirementName: bridge.requiredSkill,
      adjacentSkillUsed: bridge.candidateSkill,
      targetItemId: bridge.sourceEvidenceId || "exp_0",
      targetBulletIndex: 0,
      attestedContext: attestedContext.trim(),
      attestedActions: attestedActions.trim(),
      durationOrScale: durationOrScale.trim() || undefined,
      expectedVersion: variantVersion,
      applyToWorkspace: false,
    };

    try {
      const res = await fetch("/api/career/attest-skill", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrorMessage(data.detail || data.error || "Attestation failed validation.");
        return;
      }

      onAttestationSuccess(data);
      onClose();
    } catch (err: any) {
      setErrorMessage("Failed to submit attestation. Please retry.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Bridge Skill with Candidate Attestation" maxWidth="lg">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Adjacency Badge Summary */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-semibold text-slate-200">Transferable Bridge:</span>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                {bridge.candidateSkill}
              </Badge>
              <ArrowRight className="w-4 h-4 text-slate-400" />
              <Badge variant="outline" className="bg-primary-500/10 text-primary-400 border-primary-500/30">
                {bridge.requiredSkill}
              </Badge>
            </div>
            <Badge variant="secondary" className="text-xs">
              {Math.round(bridge.transferabilityScore * 100)}% Adjacency Strength
            </Badge>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            {bridge.transferRationale}
          </p>

          {/* Shared Competencies vs Differences */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-800/80">
            <div>
              <span className="text-slate-400 font-medium">Shared Foundations:</span>
              <ul className="mt-1 list-disc list-inside text-slate-300 space-y-0.5">
                {bridge.sharedCompetencies.slice(0, 3).map((comp, idx) => (
                  <li key={idx}>{comp}</li>
                ))}
              </ul>
            </div>
            <div>
              <span className="text-amber-400 font-medium">Critical Differences:</span>
              <ul className="mt-1 list-disc list-inside text-slate-300 space-y-0.5">
                {bridge.criticalDifferences.slice(0, 3).map((diff, idx) => (
                  <li key={idx}>{diff}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Verification Guidance */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-md p-3 flex items-start space-x-2.5">
          <HelpCircle className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
          <div className="text-xs text-blue-200">
            <span className="font-semibold">Attestation Requirement: </span>
            {bridge.attestationPrompt}
          </div>
        </div>

        {/* Form Inputs */}
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1">
              1. Where / When did you apply these concepts? <span className="text-rose-400">*</span>
            </label>
            <Input
              value={attestedContext}
              onChange={(e) => setAttestedContext(e.target.value)}
              placeholder="e.g. During tech stack evaluation at Acme Corp or personal prototype project..."
              required
              className="text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1">
              2. Specific Implementation Actions Taken <span className="text-rose-400">*</span>
            </label>
            <Textarea
              value={attestedActions}
              onChange={(e) => setAttestedActions(e.target.value)}
              placeholder="e.g. Evaluated component lifecycle and implemented prototype UI components utilizing Vue 3 Composition API..."
              rows={3}
              required
              className="text-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-200 mb-1">
              3. Scale or Duration (Optional)
            </label>
            <Input
              value={durationOrScale}
              onChange={(e) => setDurationOrScale(e.target.value)}
              placeholder="e.g. 3 weeks, 500 active users, proof-of-concept branch..."
              className="text-xs"
            />
          </div>
        </div>

        {/* Truthful Confirmation */}
        <div className="bg-slate-900 border border-slate-800 rounded p-3 flex items-start space-x-3">
          <input
            type="checkbox"
            id="confirm-truthful"
            checked={confirmedTruthful}
            onChange={(e) => setConfirmedTruthful(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-700 text-primary-600 focus:ring-primary-500"
          />
          <label htmlFor="confirm-truthful" className="text-xs text-slate-300 leading-normal cursor-pointer">
            <span className="font-semibold text-slate-100">Zero-Hallucination Attestation:</span> I confirm that I have
            genuine, real-world experience performing the actions described above. This change will be validated by ClaimValidator
            and recorded in the variant change ledger.
          </label>
        </div>

        {errorMessage && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded p-3 flex items-center space-x-2 text-xs text-rose-300">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" size="sm" disabled={isSubmitting || !confirmedTruthful}>
            {isSubmitting ? "Validating & Attesting..." : "Apply Attested Bridge"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
