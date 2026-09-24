"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProfileSchema, ProfileData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ToastBanner } from "@/components/common/state-views";
import { Save, Plus, X, Globe, Linkedin, Github, RefreshCw } from "lucide-react";

export default function ProfilePage() {
  const { profile, updateProfile, isLoaded } = useCareer();
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [targetRoleInput, setTargetRoleInput] = useState("");

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3500);
  };

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm<ProfileData>({
    resolver: zodResolver(ProfileSchema),
    defaultValues: profile,
  });

  React.useEffect(() => {
    if (profile && !isDirty && isLoaded) {
      reset(profile);
    }
  }, [profile, reset, isDirty, isLoaded]);

  const targetRoles = watch("targetRoles") || [];

  const handleAddTargetRole = () => {
    if (!targetRoleInput.trim()) return;
    if (!targetRoles.includes(targetRoleInput.trim())) {
      setValue("targetRoles", [...targetRoles, targetRoleInput.trim()], { shouldDirty: true });
    }
    setTargetRoleInput("");
  };

  const handleRemoveTargetRole = (roleToRemove: string) => {
    setValue(
      "targetRoles",
      targetRoles.filter((r) => r !== roleToRemove),
      { shouldDirty: true }
    );
  };

  const onSubmit = async (data: ProfileData) => {
    setIsSaving(true);

    // If a target role was typed in but not yet added via button, include it
    let finalRoles = [...(data.targetRoles || [])];
    if (targetRoleInput.trim() && !finalRoles.includes(targetRoleInput.trim())) {
      finalRoles.push(targetRoleInput.trim());
      setTargetRoleInput("");
      setValue("targetRoles", finalRoles);
    }
    const payload: ProfileData = {
      ...data,
      targetRoles: finalRoles,
    };

    try {
      await updateProfile(payload);
      reset(payload);
      showToast("Profile saved successfully", "success");
    } catch (err: any) {
      showToast(err.message || "Failed to save profile. Please try again.", "error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Personal & Contact Profile</h2>
          <p className="text-small text-secondary">
            Primary contact details, professional summary, and target career trajectories.
          </p>
        </div>

        {toast && (
          <ToastBanner message={toast.message} type={toast.type} />
        )}
      </div>

      <form
        onSubmit={handleSubmit(onSubmit, (errs) =>
          showToast("Please fix: " + Object.keys(errs).join(", "), "error")
        )}
        className="space-y-6"
      >
        <Card>
          <CardHeader>
            <CardTitle>Contact & Identity</CardTitle>
            <CardDescription>How recruiters and hiring managers reach you</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Full Name</label>
                <Input
                  placeholder="e.g. Alex Morgan"
                  {...register("fullName")}
                  className={errors.fullName ? "border-status-error" : ""}
                />
                {errors.fullName && (
                  <p className="text-caption text-status-error">{errors.fullName.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Professional Headline</label>
                <Input
                  placeholder="e.g. Full Stack Engineer & AI Systems Specialist"
                  {...register("headline")}
                  className={errors.headline ? "border-status-error" : ""}
                />
                {errors.headline && (
                  <p className="text-caption text-status-error">{errors.headline.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Email Address</label>
                <Input
                  type="email"
                  placeholder="name@example.com"
                  {...register("email")}
                  className={errors.email ? "border-status-error" : ""}
                />
                {errors.email && (
                  <p className="text-caption text-status-error">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-small font-medium text-primary">Phone Number</label>
                <Input
                  placeholder="+1 (555) 000-0000"
                  {...register("phone")}
                  className={errors.phone ? "border-status-error" : ""}
                />
                {errors.phone && (
                  <p className="text-caption text-status-error">{errors.phone.message}</p>
                )}
              </div>

              <div className="space-y-1.5 md:col-span-2">
                <label className="text-small font-medium text-primary">Location</label>
                <Input
                  placeholder="e.g. San Francisco, CA (Open to Remote)"
                  {...register("location")}
                  className={errors.location ? "border-status-error" : ""}
                />
                {errors.location && (
                  <p className="text-caption text-status-error">{errors.location.message}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Online Links */}
        <Card>
          <CardHeader>
            <CardTitle>Professional Profiles & Portfolios</CardTitle>
            <CardDescription>Links embedded in your generated resume headers</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-small font-medium text-primary">
                  <Globe className="h-3.5 w-3.5 text-muted" />
                  <span>Personal Website</span>
                </label>
                <Input
                  placeholder="https://yourportfolio.dev"
                  {...register("website")}
                  className={errors.website ? "border-status-error" : ""}
                />
                {errors.website && (
                  <p className="text-caption text-status-error">{errors.website.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-small font-medium text-primary">
                  <Linkedin className="h-3.5 w-3.5 text-muted" />
                  <span>LinkedIn Profile</span>
                </label>
                <Input
                  placeholder="https://linkedin.com/in/username"
                  {...register("linkedin")}
                  className={errors.linkedin ? "border-status-error" : ""}
                />
                {errors.linkedin && (
                  <p className="text-caption text-status-error">{errors.linkedin.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-small font-medium text-primary">
                  <Github className="h-3.5 w-3.5 text-muted" />
                  <span>GitHub Profile</span>
                </label>
                <Input
                  placeholder="https://github.com/username"
                  {...register("github")}
                  className={errors.github ? "border-status-error" : ""}
                />
                {errors.github && (
                  <p className="text-caption text-status-error">{errors.github.message}</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Executive Summary & Target Roles */}
        <Card>
          <CardHeader>
            <CardTitle>Executive Summary & Target Roles</CardTitle>
            <CardDescription>Core summary statement and desired roles for AI matching</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Master Summary</label>
              <Textarea
                rows={4}
                placeholder="A compelling overview of your technical background, domain impact, and career achievements..."
                {...register("summary")}
                className={errors.summary ? "border-status-error" : ""}
              />
              {errors.summary && (
                <p className="text-caption text-status-error">{errors.summary.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-small font-medium text-primary">Target Job Titles</label>
              <div className="flex gap-2">
                <Input
                  placeholder="e.g. Senior Frontend Engineer"
                  value={targetRoleInput}
                  onChange={(e) => setTargetRoleInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddTargetRole();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={handleAddTargetRole}>
                  Add Role
                </Button>
              </div>

              <div className="flex flex-wrap gap-1.5 pt-2">
                {targetRoles.map((role) => (
                  <Badge key={role} variant="accent" className="gap-1.5 py-1 px-2.5">
                    <span>{role}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveTargetRole(role)}
                      className="hover:text-primary"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" variant="primary" className="gap-1.5" disabled={isSaving}>
            {isSaving ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>Saving Changes...</span>
              </>
            ) : (
              <>
                <Save className="h-4 w-4" />
                <span>Save Profile Changes</span>
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
