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
import { formatDate } from "@/lib/utils";
import { Trophy, Plus, Pencil, Trash2, Calendar, ExternalLink } from "lucide-react";

export default function AchievementsPage() {
  const { achievements, addAchievement, updateAchievement, deleteAchievement } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

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
    reset(ach);
    setIsModalOpen(true);
  };

  const onSubmit = (data: AchievementData) => {
    if (editingId) {
      updateAchievement(editingId, data);
    } else {
      addAchievement(data);
    }
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
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

      {achievements.length === 0 ? (
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

                    <div className="flex items-center gap-1.5 text-small text-muted pt-1">
                      <Calendar className="h-3.5 w-3.5" />
                      <span>{formatDate(ach.date)}</span>
                    </div>

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
                      onClick={() => ach.id && deleteAchievement(ach.id)}
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
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Honor / Award Title</label>
            <Input
              placeholder="e.g. 1st Place Winner — Global AI Hackathon"
              {...register("title")}
              className={errors.title ? "border-status-error" : ""}
            />
            {errors.title && (
              <p className="text-caption text-status-error">{errors.title.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Awarding Entity / Event</label>
              <Input
                placeholder="e.g. TechCrunch Disrupt 2024"
                {...register("issuer")}
                className={errors.issuer ? "border-status-error" : ""}
              />
              {errors.issuer && (
                <p className="text-caption text-status-error">{errors.issuer.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Date (YYYY-MM)</label>
              <Input
                placeholder="2024-10"
                {...register("date")}
                className={errors.date ? "border-status-error" : ""}
              />
              {errors.date && (
                <p className="text-caption text-status-error">{errors.date.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Description & Impact</label>
            <Textarea
              rows={3}
              placeholder="Describe the competitive pool, what you built or discovered, and key outcomes..."
              {...register("description")}
              className={errors.description ? "border-status-error" : ""}
            />
            {errors.description && (
              <p className="text-caption text-status-error">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Reference URL (Optional)</label>
            <Input placeholder="https://..." {...register("url")} />
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingId ? "Save Changes" : "Add Honor"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
