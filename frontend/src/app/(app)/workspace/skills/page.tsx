"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { SkillSchema, SkillData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import {
  Layers,
  Plus,
  Pencil,
  Trash2,
  Search,
  CheckCircle2,
  Sparkles,
  Loader2,
  AlertCircle,
} from "lucide-react";

const CATEGORIES = [
  "Languages",
  "Frameworks & Libraries",
  "Cloud & DevOps",
  "Databases & Tools",
  "Methodologies & Soft Skills",
] as const;

const PROFICIENCIES = ["Beginner", "Intermediate", "Advanced", "Expert"] as const;

export default function SkillsPage() {
  const { skills, addSkill, updateSkill, deleteSkill, isLoaded } = useCareer();
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState("");
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
  } = useForm<SkillData>({
    resolver: zodResolver(SkillSchema),
  });

  const handleOpenAdd = (categoryDefault?: string) => {
    setEditingId(null);
    setSubmitError(null);
    reset({
      name: "",
      category: (categoryDefault && categoryDefault !== "All"
        ? categoryDefault
        : "Languages") as SkillData["category"],
      proficiency: "Advanced",
      yearsOfExperience: 3,
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (skill: SkillData) => {
    setEditingId(skill.id || null);
    setSubmitError(null);
    reset(skill);
    setIsModalOpen(true);
  };

  const onSubmit = async (data: SkillData) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      if (editingId) {
        await updateSkill(editingId, data);
        showToast("Skill updated successfully.");
      } else {
        await addSkill(data);
        showToast("Skill added successfully.");
      }
      setIsModalOpen(false);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to save skill. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    await deleteSkill(itemToDelete.id);
    showToast("Skill deleted from workspace.");
    setItemToDelete(null);
  };

  const filteredSkills = skills.filter((s) => {
    const matchesCat = selectedCategory === "All" || s.category === selectedCategory;
    const matchesSearch = s.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className="flex items-center gap-2 rounded-btn bg-status-success-soft px-4 py-2.5 text-status-success text-small font-medium border border-status-success/20 animate-in fade-in duration-200">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Technical & Professional Skills</h2>
          <p className="text-small text-secondary">
            Structured skill inventory mapped to ATS taxonomy and keyword density indexing.
          </p>
        </div>
        <Button onClick={() => handleOpenAdd()} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Skill</span>
        </Button>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 no-scrollbar">
          <button
            onClick={() => setSelectedCategory("All")}
            className={`rounded-btn px-3 py-1 text-small font-medium transition-colors border ${
              selectedCategory === "All"
                ? "bg-accent-soft text-accent border-accent/30 font-semibold"
                : "bg-surface text-secondary border-border hover:text-primary"
            }`}
          >
            All Categories ({skills.length})
          </button>
          {CATEGORIES.map((cat) => {
            const count = skills.filter((s) => s.category === cat).length;
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`rounded-btn px-3 py-1 text-small font-medium transition-colors border whitespace-nowrap ${
                  selectedCategory === cat
                    ? "bg-accent-soft text-accent border-accent/30 font-semibold"
                    : "bg-surface text-secondary border-border hover:text-primary"
                }`}
              >
                {cat} ({count})
              </button>
            );
          })}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted" />
          <Input
            placeholder="Search skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 text-small h-9"
          />
        </div>
      </div>

      {/* Skills Grid / Empty State */}
      {!isLoaded ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4 space-y-2">
                <div className="h-4 bg-border/60 rounded w-1/2" />
                <div className="h-3 bg-border/40 rounded w-1/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredSkills.length === 0 ? (
        <EmptyState
          title="No skills found"
          description="Add technical languages, frameworks, cloud tools, or soft skills to enhance ATS keyword matching."
          actionLabel="Add Skill"
          onAction={() => handleOpenAdd(selectedCategory)}
          icon={Layers}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredSkills.map((skill) => (
            <Card key={skill.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-primary">{skill.name}</span>
                    <Badge variant="outline" className="text-caption bg-page">
                      {skill.proficiency}
                    </Badge>
                  </div>
                  <p className="text-caption text-secondary">
                    {skill.category}
                    {skill.yearsOfExperience !== undefined && ` • ${skill.yearsOfExperience} yrs exp`}
                  </p>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleOpenEdit(skill)}
                    className="rounded-[4px] p-1.5 text-secondary hover:bg-page hover:text-primary"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() =>
                      skill.id &&
                      setItemToDelete({
                        id: skill.id,
                        name: skill.name,
                      })
                    }
                    className="rounded-[4px] p-1.5 text-status-error hover:bg-status-error-soft"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingId ? "Edit Skill" : "Add Skill"}
        description="Categorize your technical proficiency and industry experience."
        maxWidth="md"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {submitError && (
            <div className="flex items-center gap-2 rounded-btn bg-status-error-soft p-3 text-status-error text-small font-medium border border-status-error/20">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Skill Name *</label>
            <Input
              placeholder="e.g. TypeScript, React, Docker, Kubernetes"
              {...register("name")}
              className={errors.name ? "border-status-error" : ""}
            />
            {errors.name && (
              <p className="text-caption text-status-error">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Category *</label>
            <select
              {...register("category")}
              className="w-full rounded-input border border-border bg-surface px-3 py-2 text-body text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Proficiency *</label>
              <select
                {...register("proficiency")}
                className="w-full rounded-input border border-border bg-surface px-3 py-2 text-body text-primary focus:outline-none focus:ring-1 focus:ring-accent"
              >
                {PROFICIENCIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Years Experience</label>
              <Input
                type="number"
                min={0}
                max={50}
                {...register("yearsOfExperience", { valueAsNumber: true })}
              />
            </div>
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
                <span>{editingId ? "Save Changes" : "Add Skill"}</span>
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
        title="Delete Skill"
        description="Are you sure you want to delete this skill from your Master Career Workspace? Existing targeted resume variants will not be affected."
        itemName={itemToDelete?.name}
      />
    </div>
  );
}
