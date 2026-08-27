"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ExperienceSchema, ExperienceData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { formatDate } from "@/lib/utils";
import {
  Briefcase,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  MapPin,
  Sparkles,
  X,
} from "lucide-react";

const ACTION_VERBS = ["Spearheaded", "Architected", "Optimized", "Automated", "Engineered", "Scaled", "Reduced", "Accelerated"];

export default function ExperiencePage() {
  const { experience, addExperience, updateExperience, deleteExperience } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [bulletInput, setBulletInput] = useState("");
  const [bulletsList, setBulletsList] = useState<string[]>([]);
  const [techInput, setTechInput] = useState("");
  const [techList, setTechList] = useState<string[]>([]);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ExperienceData>({
    resolver: zodResolver(ExperienceSchema),
  });

  const isCurrent = watch("isCurrent");

  const handleOpenAdd = () => {
    setEditingId(null);
    setBulletsList([
      "Spearheaded redesign of core web client, improving performance scores by 35%.",
    ]);
    setTechList(["React", "TypeScript", "Next.js"]);
    reset({
      company: "",
      role: "",
      location: "San Francisco, CA (Hybrid)",
      startDate: "",
      endDate: "Present",
      isCurrent: true,
      bullets: ["Spearheaded redesign of core web client, improving performance scores by 35%."],
      technologies: ["React", "TypeScript", "Next.js"],
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (exp: ExperienceData) => {
    setEditingId(exp.id || null);
    setBulletsList(exp.bullets || []);
    setTechList(exp.technologies || []);
    reset(exp);
    setIsModalOpen(true);
  };

  const handleAddBullet = (prefix = "") => {
    const textToAdd = prefix ? `${prefix} ` : bulletInput.trim();
    if (!textToAdd) return;
    if (prefix) {
      setBulletInput(prefix + " ");
      return;
    }
    const updated = [...bulletsList, textToAdd];
    setBulletsList(updated);
    setValue("bullets", updated);
    setBulletInput("");
  };

  const handleRemoveBullet = (idx: number) => {
    const updated = bulletsList.filter((_, i) => i !== idx);
    setBulletsList(updated);
    setValue("bullets", updated);
  };

  const handleAddTech = () => {
    if (!techInput.trim()) return;
    if (!techList.includes(techInput.trim())) {
      const updated = [...techList, techInput.trim()];
      setTechList(updated);
      setValue("technologies", updated);
    }
    setTechInput("");
  };

  const handleRemoveTech = (t: string) => {
    const updated = techList.filter((item) => item !== t);
    setTechList(updated);
    setValue("technologies", updated);
  };

  const onSubmit = (data: ExperienceData) => {
    const submission = {
      ...data,
      bullets: bulletsList,
      technologies: techList,
      endDate: data.isCurrent ? "Present" : data.endDate,
    };
    if (editingId) {
      updateExperience(editingId, submission);
    } else {
      addExperience(submission);
    }
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Professional Work Experience</h2>
          <p className="text-small text-secondary">
            Document full-time, contract, and leadership roles with strong quantifiable bullet points.
          </p>
        </div>
        <Button onClick={handleOpenAdd} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Position</span>
        </Button>
      </div>

      {experience.length === 0 ? (
        <EmptyState
          title="No work experience added"
          description="Add your current and previous professional roles to demonstrate career progression."
          actionLabel="Add Position"
          onAction={handleOpenAdd}
          icon={Briefcase}
        />
      ) : (
        <div className="space-y-4">
          {experience.map((exp) => (
            <Card key={exp.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-5">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="space-y-2.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-h2 font-semibold text-primary">{exp.role}</h3>
                      <span className="text-body font-medium text-accent">@ {exp.company}</span>
                      {exp.isCurrent && <Badge variant="success">Current Role</Badge>}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-muted">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>
                          {formatDate(exp.startDate)} &mdash;{" "}
                          {exp.isCurrent ? "Present" : formatDate(exp.endDate)}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5" />
                        <span>{exp.location}</span>
                      </div>
                    </div>

                    {/* Bullet Points */}
                    <div className="space-y-1 pt-1">
                      <ul className="list-disc pl-4 space-y-1 text-small text-primary">
                        {exp.bullets?.map((bullet, i) => (
                          <li key={i} className="leading-relaxed">
                            {bullet}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Tech stack */}
                    {exp.technologies && exp.technologies.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-2">
                        {exp.technologies.map((tech) => (
                          <Badge key={tech} variant="outline" className="bg-page text-secondary">
                            {tech}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-start">
                    <Button
                      onClick={() => handleOpenEdit(exp)}
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span>Edit</span>
                    </Button>
                    <Button
                      onClick={() => exp.id && deleteExperience(exp.id)}
                      variant="ghost"
                      size="sm"
                      className="text-status-error hover:bg-status-error-soft"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
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
        title={editingId ? "Edit Position" : "Add Work Experience"}
        description="Provide company name, title, date range, and bullet points."
        maxWidth="2xl"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Company Name</label>
              <Input
                placeholder="e.g. Stripe or Apex Scale"
                {...register("company")}
                className={errors.company ? "border-status-error" : ""}
              />
              {errors.company && (
                <p className="text-caption text-status-error">{errors.company.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Job Title / Role</label>
              <Input
                placeholder="e.g. Senior Software Engineer"
                {...register("role")}
                className={errors.role ? "border-status-error" : ""}
              />
              {errors.role && (
                <p className="text-caption text-status-error">{errors.role.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Location</label>
            <Input
              placeholder="e.g. San Francisco, CA (Hybrid)"
              {...register("location")}
              className={errors.location ? "border-status-error" : ""}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Start Date (YYYY-MM)</label>
              <Input
                placeholder="2023-01"
                {...register("startDate")}
                className={errors.startDate ? "border-status-error" : ""}
              />
              {errors.startDate && (
                <p className="text-caption text-status-error">{errors.startDate.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-small font-medium text-primary">End Date</label>
                <div className="flex items-center gap-1.5">
                  <input type="checkbox" id="isCurrent" {...register("isCurrent")} />
                  <label htmlFor="isCurrent" className="text-caption text-secondary cursor-pointer">
                    Current Role
                  </label>
                </div>
              </div>
              <Input
                disabled={isCurrent}
                placeholder={isCurrent ? "Present" : "2024-05"}
                {...register("endDate")}
                className={errors.endDate ? "border-status-error" : ""}
              />
            </div>
          </div>

          {/* AI Action Verbs & Bullet points */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-small font-medium text-primary">Experience Bullets</label>
              <div className="flex items-center gap-1 text-caption text-accent font-semibold">
                <Sparkles className="h-3 w-3" />
                <span>AI Action Verbs:</span>
              </div>
            </div>

            {/* Quick Action Verb Chips */}
            <div className="flex flex-wrap gap-1 pb-1">
              {ACTION_VERBS.map((verb) => (
                <button
                  key={verb}
                  type="button"
                  onClick={() => handleAddBullet(verb)}
                  className="rounded border border-border bg-page px-2 py-0.5 text-caption font-medium text-secondary hover:border-accent hover:text-accent"
                >
                  +{verb}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <Input
                placeholder="Type bullet point with metric..."
                value={bulletInput}
                onChange={(e) => setBulletInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddBullet();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={() => handleAddBullet()}>
                Add Bullet
              </Button>
            </div>

            <div className="space-y-1.5 pt-1">
              {bulletsList.map((b, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between rounded-btn border border-border bg-page p-2 text-small text-primary gap-2"
                >
                  <span>&bull; {b}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveBullet(idx)}
                    className="text-muted hover:text-status-error"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Tech Stack */}
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">Technologies Used</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. Next.js"
                value={techInput}
                onChange={(e) => setTechInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTech();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={handleAddTech}>
                Add Tech
              </Button>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {techList.map((tech) => (
                <Badge key={tech} variant="secondary" className="gap-1.5 py-1 px-2">
                  <span>{tech}</span>
                  <button type="button" onClick={() => handleRemoveTech(tech)}>
                    <X className="h-3 w-3 hover:text-primary" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingId ? "Save Position" : "Add Position"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
