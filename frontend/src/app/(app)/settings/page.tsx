"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useCareer } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CareerSignalMeter } from "@/components/common/career-signal-meter";
import { ToastBanner } from "@/components/common/state-views";
import {
  User,
  ShieldCheck,
  Download,
  RotateCcw,
  Sparkles,
  Lock,
  LogOut,
  Loader2,
} from "lucide-react";

export default function SettingsPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const {
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
    achievements,
    documents,
    resumes,
    seedSampleData,
  } = useCareer();

  const [isSeeding, setIsSeeding] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleExportData = () => {
    const backup = {
      profile,
      education,
      skills,
      projects,
      experience,
      certifications,
      achievements,
      documents,
      resumes,
      exportDate: new Date().toISOString(),
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(backup, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `resumeiq_career_vault_backup_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    showToast("Career data backup downloaded", "success");
  };

  const handleSeedData = async () => {
    setIsSeeding(true);
    try {
      await seedSampleData();
      showToast("Sample data imported successfully", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to import sample data.", "error");
    } finally {
      setIsSeeding(false);
    }
  };

  const handleSignOut = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Toast Notification Banner */}
      {toast && (
        <ToastBanner message={toast.message} type={toast.type} />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h1 font-semibold text-primary">Account & Workspace Settings</h1>
          <p className="text-small text-secondary mt-0.5">
            Manage your account profile, cloud data backups, and workspace integrity.
          </p>
        </div>

        <Button onClick={handleSignOut} variant="outline" size="sm" className="gap-1.5 text-status-error border-status-error/30 hover:bg-status-error-soft">
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </Button>
      </div>

      {/* Career Signal Health in Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Workspace Signal Health</CardTitle>
          <CardDescription>Overall diagnostic of your career data depth</CardDescription>
        </CardHeader>
        <CardContent>
          <CareerSignalMeter showBreakdownList={true} showActionLink={false} />
        </CardContent>
      </Card>

      {/* Account Info */}
      <Card>
        <CardHeader>
          <CardTitle>Account Credentials</CardTitle>
          <CardDescription>Your registered identity in Firebase Authentication</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Full Name</label>
              <Input value={profile.fullName || user?.displayName || "User"} readOnly className="bg-page" />
            </div>
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Email Address</label>
              <Input value={user?.email || profile.email || ""} readOnly className="bg-page" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Plan & Subscription */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Subscription Tier</CardTitle>
              <CardDescription>Your active platform permissions and quotas</CardDescription>
            </div>
            <Badge variant="accent" className="font-semibold">
              Pro Career Tier
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-btn border border-border bg-page p-4 space-y-2">
            <div className="flex items-center justify-between text-body font-semibold text-primary">
              <span>Pro Membership</span>
              <span>Active</span>
            </div>
            <p className="text-small text-secondary">
              Includes unlimited AI tailored resumes, deep ATS keyword scans, full career entity history, and PDF rendering engine.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Data Management & Privacy */}
      <Card>
        <CardHeader>
          <CardTitle>Data Management & Privacy</CardTitle>
          <CardDescription>Export and manage your career information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-btn border border-border p-3.5">
            <div className="space-y-0.5">
              <div className="text-body font-semibold text-primary">Export Complete Career Graph</div>
              <p className="text-small text-secondary">
                Download all profile, education, skills, projects, and resumes as portable JSON.
              </p>
            </div>
            <Button onClick={handleExportData} variant="outline" size="sm" className="gap-1.5 shrink-0">
              <Download className="h-4 w-4 text-accent" />
              <span>Download JSON Backup</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Developer / Testing Utilities */}
      <Card className="border-dashed border-border/80">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Developer & Testing Utilities</CardTitle>
              <CardDescription>Tools for development, testing, and sandbox verification</CardDescription>
            </div>
            <Badge variant="outline" className="text-muted text-[11px] uppercase tracking-wider">
              Testing Tool
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-btn border border-border bg-page/50 p-3.5">
            <div className="space-y-0.5">
              <div className="text-body font-semibold text-primary">Seed Synthetic Profile to Cloud</div>
              <p className="text-small text-secondary">
                Write realistic engineer portfolio entities directly into your authenticated Firestore database for sandbox testing.
              </p>
            </div>
            <Button
              onClick={handleSeedData}
              disabled={isSeeding}
              variant="outline"
              size="sm"
              className="gap-1.5 shrink-0 text-accent hover:bg-accent-soft border-accent/30"
            >
              {isSeeding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              <span>{isSeeding ? "Seeding..." : "Load Sample Data"}</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
