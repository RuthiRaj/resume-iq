"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AchievementSchema, AchievementData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import { formatDate } from "@/lib/utils";
import {
  Trophy,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  ExternalLink,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

export default function AchievementsPage() {
  const { achievements, addAchievement, updateAchievement, deleteAchievement, isLoaded } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [itemToDelete, setItemToDelete] = useState<{ id: string; name: string } | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AchievementData>({
    resolver: zodResolver(AchievementSchema),
  });

  const handleOpenAdd = () => {
    setEditingId(null);
    setSubmitError(null);
    reset({
      title: "",
      issuer: "",
      date: "",
      description: "",
      url: "",
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (ach: AchievementData) => {
    setEditingId(ach.id || null);
    setSubmitError(null);
    reset(ach);
    setIsModalOpen(true);
  };

  const onSubmit = async (data: AchievementData) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      if (editingId) {
        await updateAchievement(editingId, data);
        showToast("Achievement updated successfully.");
      } else {
        await addAchievement(data);
        showToast("Achievement added successfully.");
      }
      setIsModalOpen(false);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to save achievement. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    await deleteAchievement(itemToDelete.id);
    showToast("Achievement deleted from workspace.");
    setItemToDelete(null);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className="flex items-center gap-2 rounded-btn bg-status-success-soft px-4 py-2.5 text-status-success text-small font-medium border border-status-success/20 animate-in fade-in duration-200">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Honors, Awards & Publications</h2>
          <p className="text-small text-secondary">
            Competitive hackathons, open source recognitions, academic research publications, and awards.
          </p>
        </div>
        <Button onClick={handleOpenAdd} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Honor</span>
        </Button>
      </div>

      {!isLoaded ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-5 space-y-3">
                <div className="h-5 bg-border/60 rounded w-1/3" />
                <div className="h-4 bg-border/40 rounded w-1/4" />
                <div className="h-10 bg-border/30 rounded w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : achievements.length === 0 ? (
        <EmptyState
          title="No achievements added"
          description="Add hackathon victories, patent filings, or published papers."
          actionLabel="Add Honor"
          onAction={handleOpenAdd}
          icon={Trophy}
        />
      ) : (
        <div className="space-y-4">
          {achievements.map((ach) => (
            <Card key={ach.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                        <Trophy className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-body font-semibold text-primary">{ach.title}</h3>
                        <p className="text-small font-medium text-secondary">{ach.issuer}</p>
                      </div>
                    </div>

                    {ach.date && (
                      <div className="flex items-center gap-1.5 text-small text-muted pt-1">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>{formatDate(ach.date)}</span>
                      </div>
                    )}

                    <p className="text-body text-secondary leading-relaxed">{ach.description}</p>

                    {ach.url && (
                      <a
                        href={ach.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-small font-medium text-accent hover:underline pt-1"
                      >
                        <span>View Publication / Coverage</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEdit(ach)}
                      className="rounded-[4px] p-1.5 text-secondary hover:bg-page hover:text-primary"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() =>
                        ach.id &&
                        setItemToDelete({
                          id: ach.id,
                          name: ach.title,
                        })
                      }
                      className="rounded-[4px] p-1.5 text-status-error hover:bg-status-error-soft"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingId ? "Edit Honor / Award" : "Add Honor, Award or Publication"}
        description="Provide title, awarding organization, date, and description."
        maxWidth="lg"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {submitError && (
            <div className="flex items-center gap-2 rounded-btn bg-status-error-soft p-3 text-status-error text-small font-medium border border-status-error/20">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Honor / Award Title *</label>
            <Input
              placeholder="e.g. 1st Place - Global AI Hackathon"
              {...register("title")}
              className={errors.title ? "border-status-error" : ""}
            />
            {errors.title && (
              <p className="text-caption text-status-error">{errors.title.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Issuing Organization *</label>
              <Input
                placeholder="e.g. OpenAI / TechCrunch"
                {...register("issuer")}
                className={errors.issuer ? "border-status-error" : ""}
              />
              {errors.issuer && (
                <p className="text-caption text-status-error">{errors.issuer.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Date (YYYY-MM) *</label>
              <Input
                placeholder="2023-11"
                {...register("date")}
                className={errors.date ? "border-status-error" : ""}
              />
              {errors.date && (
                <p className="text-caption text-status-error">{errors.date.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Description & Impact *</label>
            <Textarea
              rows={3}
              placeholder="Describe the recognition, criteria, and significance..."
              {...register("description")}
              className={errors.description ? "border-status-error" : ""}
            />
            {errors.description && (
              <p className="text-caption text-status-error">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Publication / Verification URL</label>
            <Input
              placeholder="https://..."
              {...register("url")}
              className={errors.url ? "border-status-error" : ""}
            />
            {errors.url && (
              <p className="text-caption text-status-error">{errors.url.message}</p>
            )}
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  <span>Saving...</span>
                </>
              ) : (
                <span>{editingId ? "Save Changes" : "Add Honor"}</span>
              )}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <ConfirmDeleteModal
        isOpen={Boolean(itemToDelete)}
        onClose={() => setItemToDelete(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Honor / Award"
        description="Are you sure you want to delete this achievement from your Master Career Workspace? Existing targeted resume variants will not be affected."
        itemName={itemToDelete?.name}
      />
    </div>
  );
}
