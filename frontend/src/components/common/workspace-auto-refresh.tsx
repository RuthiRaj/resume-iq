"use client";

import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useCareer } from "@/lib/store";
import { ToastBanner } from "@/components/common/state-views";

/**
 * Workspace → tailored-resume auto-refresh.
 *
 * The workspace is the live source of truth: whenever workspace data changes
 * (profile, education, skills, projects, experience, certifications, ...), the
 * store bumps `workspaceRevision`. This component debounces those bumps and
 * then resyncs every workspace-sourced targeted variant via
 * POST /api/variants/{id}/resync.
 *
 * Cost control: the backend resync endpoint is a cheap no-op (a few Firestore
 * reads, no AI) when the variant's anchored workspace hash already matches, so
 * AI regeneration only happens for variants that are genuinely out of sync.
 * The whole behavior can be toggled in Settings ("Auto-refresh tailored
 * resumes"), persisted in localStorage.
 */

const AUTO_REFRESH_KEY = "resumeiq:auto-refresh-resumes";
const DEBOUNCE_MS = 30_000;

export function isAutoRefreshEnabled(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(AUTO_REFRESH_KEY) !== "0";
  } catch {
    return true;
  }
}

export function setAutoRefreshEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(AUTO_REFRESH_KEY, enabled ? "1" : "0");
  } catch {
    // storage unavailable — ignore
  }
}

type ToastType = "success" | "error" | "info";

export function emitWorkspaceToast(message: string, type: ToastType = "success"): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent<{ message: string; type: ToastType }>("resumeiq:toast", {
      detail: { message, type },
    })
  );
}

function waitForVisible(): Promise<void> {
  if (typeof document === "undefined" || !document.hidden) return Promise.resolve();
  return new Promise((resolve) => {
    const onVis = () => {
      if (!document.hidden) {
        document.removeEventListener("visibilitychange", onVis);
        resolve();
      }
    };
    document.addEventListener("visibilitychange", onVis);
    // Failsafe: don't wait forever on a background tab.
    setTimeout(() => {
      document.removeEventListener("visibilitychange", onVis);
      resolve();
    }, 120_000);
  });
}

export function WorkspaceAutoRefresh() {
  const { user } = useAuth();
  const { resumes, workspaceRevision } = useCareer();
  const resumesRef = useRef(resumes);
  resumesRef.current = resumes;
  const userRef = useRef(user);
  userRef.current = user;
  const refreshingRef = useRef(false);

  useEffect(() => {
    if (workspaceRevision === 0) return;
    const currentUser = userRef.current;
    if (!currentUser) return;
    if (!isAutoRefreshEnabled()) return;

    let cancelled = false;

    const run = async () => {
      if (cancelled) return;
      // If a refresh is already running, wait for it to finish instead of
      // dropping this revision's edits: this run then re-reads live evidence
      // per variant and picks up anything the in-flight refresh missed. (N6)
      while (refreshingRef.current && !cancelled) {
        await new Promise((r) => setTimeout(r, 1000));
      }
      if (cancelled) return;
      // Re-check the toggle at execution time, not just when the timer was
      // scheduled: the user may have disabled auto-refresh mid-debounce. (N5)
      if (!isAutoRefreshEnabled()) return;
      await waitForVisible();
      if (cancelled || !isAutoRefreshEnabled()) return;

      const targets = resumesRef.current.filter(
        (r) => r.isTargetedVariant && r.masterResumeId === "workspace"
      );
      if (targets.length === 0) return;

      refreshingRef.current = true;
      emitWorkspaceToast(
        `Workspace changed — refreshing ${targets.length} tailored resume${targets.length === 1 ? "" : "s"}…`,
        "info"
      );
      let refreshed = 0;
      let failed = 0;
      try {
        const idToken = await currentUser.getIdToken();
        for (const t of targets) {
          if (cancelled) break;
          try {
            const res = await fetch(`/api/variants/${encodeURIComponent(t.id)}/resync`, {
              method: "POST",
              headers: { Authorization: `Bearer ${idToken}` },
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && (data.newVersion || data.inSync === false)) {
              refreshed += 1;
            } else if (res.status === 409) {
              // 409 Conflict: user edited or another sync in-flight. Neutral skip; next revision retries.
            } else if (!res.ok) {
              // N2: a non-OK resync (429/500/504) is a failure, not silence.
              failed += 1;
            }
          } catch {
            failed += 1;
          }
        }
      } catch {
        failed = targets.length;
      } finally {
        refreshingRef.current = false;
      }

      if (cancelled) return;
      if (failed > 0) {
        emitWorkspaceToast(
          `Auto-refresh finished with ${failed} failure${failed === 1 ? "" : "s"} — use Sync on the Resumes page to retry.`,
          "error"
        );
      } else if (refreshed > 0) {
        emitWorkspaceToast(
          `Refreshed ${refreshed} tailored resume${refreshed === 1 ? "" : "s"} from your latest workspace.`,
          "success"
        );
      }
      // If refreshed === 0 and failed === 0, every variant was already in
      // sync (backend no-op) — stay silent to avoid toast noise.
      // Always notify listeners (e.g. the Resumes page sync badges) so they
      // can re-check sync status after a background refresh. (N3)
      window.dispatchEvent(
        new CustomEvent("resumeiq:variants-refreshed", {
          detail: { refreshed, failed },
        })
      );
    };

    const timer = setTimeout(run, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceRevision]);

  return null;
}

export function GlobalToastHost() {
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ message: string; type: ToastType }>).detail;
      if (!detail?.message) return;
      setToast({ message: detail.message, type: detail.type || "success" });
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setToast(null), 4000);
    };
    window.addEventListener("resumeiq:toast", handler);
    return () => {
      window.removeEventListener("resumeiq:toast", handler);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  if (!toast) return null;
  return (
    <div className="fixed bottom-4 right-4 z-[100] max-w-sm animate-in fade-in slide-in-from-top-2 duration-200">
      <ToastBanner message={toast.message} type={toast.type} className="shadow-elevated" />
    </div>
  );
}
