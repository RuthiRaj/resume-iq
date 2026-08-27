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
import {
  Layers,
  Plus,
  Pencil,
  Trash2,
  Search,
  CheckCircle2,
  Sparkles,
} from "lucide-react";

const CATEGORIES = [
  "Languages",
  "Frameworks & Libraries",
  "Cloud & DevOps",
  "Databases & Tools",
  "Methodologies & Soft Skills",
] as const;

export default function SkillsPage() {
  const { skills, addSkill, updateSkill, deleteSkill } = useCareer();
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

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
    reset(skill);
    setIsModalOpen(true);
  };

  const onSubmit = (data: SkillData) => {
    if (editingId) {
      updateSkill(editingId, data);
    } else {
      addSkill(data);
    }
    setIsModalOpen(false);
  };

  const filteredSkills = skills.filter((s) => {
    const matchesCat = selectedCategory === "All" || s.category === selectedCategory;
    const matchesSearch = s.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="space-y-6">
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
      {filteredSkills.length === 0 ? (
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
            <div
              key={skill.id}
              className="flex items-center justify-between rounded-card border border-border bg-surface p-3 hover:border-accent/30 transition-all group"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-body font-semibold text-primary">{skill.name}</span>
                  <Badge
                    variant={
                      skill.proficiency === "Expert"
                        ? "accent"
                        : skill.proficiency === "Advanced"
                        ? "success"
                        : "default"
                    }
                  >
                    {skill.proficiency}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-caption text-secondary">
                  <span>{skill.category}</span>
                  {skill.yearsOfExperience !== undefined && (
                    <>
                      <span>&bull;</span>
                      <span>{skill.yearsOfExperience} yrs exp</span>
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleOpenEdit(skill)}
                  className="rounded-[4px] p-1 text-secondary hover:bg-page hover:text-primary"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => skill.id && deleteSkill(skill.id)}
                  className="rounded-[4px] p-1 text-status-error hover:bg-status-error-soft"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingId ? "Edit Skill" : "Add Technical / Professional Skill"}
        description="Provide skill name, category taxonomy, and proficiency level."
        maxWidth="md"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Skill Name</label>
            <Input
              placeholder="e.g. TypeScript or Docker"
              {...register("name")}
              className={errors.name ? "border-status-error" : ""}
            />
            {errors.name && (
              <p className="text-caption text-status-error">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Category</label>
            <select
              {...register("category")}
              className="flex h-9 w-full rounded-input border border-border bg-surface px-3 py-1.5 text-body text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Proficiency</label>
              <select
                {...register("proficiency")}
                className="flex h-9 w-full rounded-input border border-border bg-surface px-3 py-1.5 text-body text-primary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
              >
                <option value="Beginner">Beginner</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Advanced">Advanced</option>
                <option value="Expert">Expert</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Years of Exp</label>
              <Input
                type="number"
                min={0}
                max={50}
                {...register("yearsOfExperience", { valueAsNumber: true })}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingId ? "Save Skill" : "Add Skill"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
