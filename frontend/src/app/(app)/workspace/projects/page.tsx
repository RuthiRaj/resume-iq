"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ProjectSchema, ProjectData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import { formatDate } from "@/lib/utils";
import {
  Sparkles,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  ExternalLink,
  Github,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

export default function ProjectsPage() {
  const { projects, addProject, updateProject, deleteProject, isLoaded } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const [techInput, setTechInput] = useState("");
  const [techList, setTechList] = useState<string[]>([]);

  const [highlightInput, setHighlightInput] = useState("");
  const [highlightsList, setHighlightsList] = useState<string[]>([]);

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
    setValue,
    formState: { errors },
  } = useForm<ProjectData>({
    resolver: zodResolver(ProjectSchema),
  });

  const handleOpenAdd = () => {
    setEditingId(null);
    setSubmitError(null);
    setTechList(["Next.js", "TypeScript", "Tailwind CSS"]);
    setHighlightsList(["Engineered high-throughput architecture with 99.9% uptime."]);
    reset({
      title: "",
      role: "",
      startDate: "",
      endDate: "",
      description: "",
      highlights: ["Engineered high-throughput architecture with 99.9% uptime."],
      techStack: ["Next.js", "TypeScript", "Tailwind CSS"],
      liveUrl: "",
      repoUrl: "",
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (proj: ProjectData) => {
    setEditingId(proj.id || null);
    setSubmitError(null);
    setTechList(proj.techStack || []);
    setHighlightsList(proj.highlights || []);
    reset(proj);
    setIsModalOpen(true);
  };

  const handleAddTech = () => {
    if (!techInput.trim()) return;
    if (!techList.includes(techInput.trim())) {
      const updated = [...techList, techInput.trim()];
      setTechList(updated);
      setValue("techStack", updated);
    }
    setTechInput("");
  };

  const handleRemoveTech = (t: string) => {
    const updated = techList.filter((item) => item !== t);
    setTechList(updated);
    setValue("techStack", updated);
  };

  const handleAddHighlight = () => {
    if (!highlightInput.trim()) return;
    const updated = [...highlightsList, highlightInput.trim()];
    setHighlightsList(updated);
    setValue("highlights", updated);
    setHighlightInput("");
  };

  const handleRemoveHighlight = (idx: number) => {
    const updated = highlightsList.filter((_, i) => i !== idx);
    setHighlightsList(updated);
    setValue("highlights", updated);
  };

  const onSubmit = async (data: ProjectData) => {
    if (highlightsList.length === 0) {
      setSubmitError("Please add at least one highlight bullet describing measurable project impact.");
      return;
    }
    if (techList.length === 0) {
      setSubmitError("Please add at least one technology tag.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    const submission = {
      ...data,
      techStack: techList,
      highlights: highlightsList,
    };

    try {
      if (editingId) {
        await updateProject(editingId, submission);
        showToast("Project updated successfully.");
      } else {
        await addProject(submission);
        showToast("Project added successfully.");
      }
      setIsModalOpen(false);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to save project. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    await deleteProject(itemToDelete.id);
    showToast("Project deleted from workspace.");
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
          <h2 className="text-h2 font-semibold text-primary">Featured Engineering Projects</h2>
          <p className="text-small text-secondary">
            Showcase technical complexity, quantifiable impact metrics, live URLs, and tech stacks.
          </p>
        </div>
        <Button onClick={handleOpenAdd} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Project</span>
        </Button>
      </div>

      {!isLoaded ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-5 space-y-3">
                <div className="h-5 bg-border/60 rounded w-1/3" />
                <div className="h-4 bg-border/40 rounded w-1/4" />
                <div className="h-12 bg-border/30 rounded w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects added yet"
          description="Add technical projects with measurable outcomes to demonstrate system capabilities."
          actionLabel="Add Project"
          onAction={handleOpenAdd}
          icon={Sparkles}
        />
      ) : (
        <div className="space-y-4">
          {projects.map((proj) => (
            <Card key={proj.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-5">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="space-y-2.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-h2 font-semibold text-primary">{proj.title}</h3>
                      {proj.role && (
                        <span className="text-body font-medium text-secondary">
                          &bull; {proj.role}
                        </span>
                      )}
                    </div>

                    {(proj.startDate || proj.endDate) && (
                      <div className="flex items-center gap-1.5 text-small text-muted">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>
                          {formatDate(proj.startDate)} &mdash; {formatDate(proj.endDate)}
                        </span>
                      </div>
                    )}

                    <p className="text-body text-secondary leading-relaxed">{proj.description}</p>

                    {/* Highlights */}
                    <div className="space-y-1 pt-1">
                      <ul className="list-disc pl-4 space-y-1 text-small text-primary">
                        {proj.highlights?.map((hl, i) => (
                          <li key={i} className="leading-relaxed">
                            {hl}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Tech Stack */}
                    {proj.techStack && proj.techStack.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-2">
                        {proj.techStack.map((tech) => (
                          <Badge key={tech} variant="outline" className="bg-page text-secondary">
                            {tech}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {/* Links */}
                    <div className="flex flex-wrap items-center gap-3 pt-2">
                      {proj.liveUrl && (
                        <a
                          href={proj.liveUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-small font-medium text-accent hover:underline"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                          <span>Live Demo</span>
                        </a>
                      )}
                      {proj.repoUrl && (
                        <a
                          href={proj.repoUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-small font-medium text-secondary hover:text-primary"
                        >
                          <Github className="h-3.5 w-3.5" />
                          <span>Repository</span>
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start">
                    <Button
                      onClick={() => handleOpenEdit(proj)}
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span>Edit</span>
                    </Button>
                    <Button
                      onClick={() =>
                        proj.id &&
                        setItemToDelete({
                          id: proj.id,
                          name: proj.title,
                        })
                      }
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

      {/* Add / Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingId ? "Edit Project" : "Add Engineering Project"}
        description="Detail system architecture, tech stacks, links, and impact metrics."
        maxWidth="2xl"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {submitError && (
            <div className="flex items-center gap-2 rounded-btn bg-status-error-soft p-3 text-status-error text-small font-medium border border-status-error/20">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Project Title *</label>
              <Input
                placeholder="e.g. Distributed Task Queue"
                {...register("title")}
                className={errors.title ? "border-status-error" : ""}
              />
              {errors.title && (
                <p className="text-caption text-status-error">{errors.title.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Your Role *</label>
              <Input
                placeholder="e.g. Lead Architect / Creator"
                {...register("role")}
                className={errors.role ? "border-status-error" : ""}
              />
              {errors.role && (
                <p className="text-caption text-status-error">{errors.role.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Start Date (YYYY-MM) *</label>
              <Input
                placeholder="2023-03"
                {...register("startDate")}
                className={errors.startDate ? "border-status-error" : ""}
              />
              {errors.startDate && (
                <p className="text-caption text-status-error">{errors.startDate.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">End Date (YYYY-MM) *</label>
              <Input
                placeholder="2023-08"
                {...register("endDate")}
                className={errors.endDate ? "border-status-error" : ""}
              />
              {errors.endDate && (
                <p className="text-caption text-status-error">{errors.endDate.message}</p>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Overview / Description *</label>
            <Textarea
              rows={3}
              placeholder="High-level architecture and problem solved..."
              {...register("description")}
              className={errors.description ? "border-status-error" : ""}
            />
            {errors.description && (
              <p className="text-caption text-status-error">{errors.description.message}</p>
            )}
          </div>

          {/* Highlights */}
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">Key Highlights & Metrics *</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. Handled 10k requests/sec with P99 latency under 20ms..."
                value={highlightInput}
                onChange={(e) => setHighlightInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddHighlight();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={handleAddHighlight}>
                Add Highlight
              </Button>
            </div>

            <div className="space-y-1.5 pt-1">
              {highlightsList.map((hl, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between rounded-btn border border-border bg-page p-2 text-small text-primary gap-2"
                >
                  <span>&bull; {hl}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveHighlight(idx)}
                    className="text-muted hover:text-status-error shrink-0 mt-0.5"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Tech Stack */}
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">Technologies Used *</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. Next.js, Rust, Redis"
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Live Demo URL</label>
              <Input
                placeholder="https://..."
                {...register("liveUrl")}
                className={errors.liveUrl ? "border-status-error" : ""}
              />
              {errors.liveUrl && (
                <p className="text-caption text-status-error">{errors.liveUrl.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">GitHub Repository URL</label>
              <Input
                placeholder="https://github.com/..."
                {...register("repoUrl")}
                className={errors.repoUrl ? "border-status-error" : ""}
              />
              {errors.repoUrl && (
                <p className="text-caption text-status-error">{errors.repoUrl.message}</p>
              )}
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
                <span>{editingId ? "Save Changes" : "Add Project"}</span>
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
        title="Delete Project"
        description="Are you sure you want to delete this project from your Master Career Workspace? Existing targeted resume variants will not be affected."
        itemName={itemToDelete?.name}
      />
    </div>
  );
}
