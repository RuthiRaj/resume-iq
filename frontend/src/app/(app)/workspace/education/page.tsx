"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { EducationSchema, EducationData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { ConfirmDeleteModal } from "@/components/common/confirm-delete-modal";
import { formatDate } from "@/lib/utils";
import {
  GraduationCap,
  Plus,
  Pencil,
  Trash2,
  Calendar,
  Award,
  BookOpen,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

export default function EducationPage() {
  const { education, addEducation, updateEducation, deleteEducation, isLoaded } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [courseInput, setCourseInput] = useState("");
  const [coursesList, setCoursesList] = useState<string[]>([]);

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
  } = useForm<EducationData>({
    resolver: zodResolver(EducationSchema),
  });

  const handleOpenAdd = () => {
    setEditingId(null);
    setSubmitError(null);
    setCoursesList([]);
    reset({
      institution: "",
      degree: "",
      fieldOfStudy: "",
      startDate: "",
      endDate: "",
      grade: "",
      activities: "",
      courses: [],
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (item: EducationData) => {
    setEditingId(item.id || null);
    setSubmitError(null);
    setCoursesList(item.courses || []);
    reset({
      institution: item.institution,
      degree: item.degree,
      fieldOfStudy: item.fieldOfStudy,
      startDate: item.startDate,
      endDate: item.endDate,
      grade: item.grade || "",
      activities: item.activities || "",
      courses: item.courses || [],
    });
    setIsModalOpen(true);
  };

  const handleAddCourse = () => {
    if (!courseInput.trim()) return;
    if (!coursesList.includes(courseInput.trim())) {
      const updated = [...coursesList, courseInput.trim()];
      setCoursesList(updated);
      setValue("courses", updated);
    }
    setCourseInput("");
  };

  const handleRemoveCourse = (course: string) => {
    const updated = coursesList.filter((c) => c !== course);
    setCoursesList(updated);
    setValue("courses", updated);
  };

  const onSubmit = async (data: EducationData) => {
    setIsSubmitting(true);
    setSubmitError(null);

    const submission = { ...data, courses: coursesList };
    try {
      if (editingId) {
        await updateEducation(editingId, submission);
        showToast("Degree details updated successfully.");
      } else {
        await addEducation(submission);
        showToast("Degree added successfully.");
      }
      setIsModalOpen(false);
    } catch (err: any) {
      setSubmitError(err.message || "Failed to save degree. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!itemToDelete) return;
    await deleteEducation(itemToDelete.id);
    showToast("Degree deleted from workspace.");
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
          <h2 className="text-h2 font-semibold text-primary">Degrees & Academic Credentials</h2>
          <p className="text-small text-secondary">
            Manage your university education, certifications of study, GPA, honors, and coursework.
          </p>
        </div>
        <Button onClick={handleOpenAdd} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Degree</span>
        </Button>
      </div>

      {!isLoaded ? (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-5 space-y-3">
                <div className="h-5 bg-border/60 rounded w-1/3" />
                <div className="h-4 bg-border/40 rounded w-1/4" />
                <div className="h-8 bg-border/30 rounded w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : education.length === 0 ? (
        <EmptyState
          title="No education added yet"
          description="Add your degree details, coursework, and honors to boost your Career Signal score."
          actionLabel="Add Degree"
          onAction={handleOpenAdd}
          icon={GraduationCap}
        />
      ) : (
        <div className="space-y-4">
          {education.map((item) => (
            <Card key={item.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-5">
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <h3 className="text-h2 font-semibold text-primary">{item.institution}</h3>
                      {item.grade && (
                        <Badge variant="success" className="font-medium">
                          {item.grade}
                        </Badge>
                      )}
                    </div>

                    <div className="text-body font-medium text-secondary">
                      {item.degree} in {item.fieldOfStudy}
                    </div>

                    <div className="flex items-center gap-1.5 text-small text-muted">
                      <Calendar className="h-3.5 w-3.5" />
                      <span>
                        {formatDate(item.startDate)} &mdash; {formatDate(item.endDate)}
                      </span>
                    </div>

                    {item.activities && (
                      <p className="text-small text-secondary pt-1">
                        <span className="font-medium text-primary">Activities / Honors: </span>
                        {item.activities}
                      </p>
                    )}

                    {item.courses && item.courses.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-2">
                        {item.courses.map((course) => (
                          <Badge key={course} variant="outline" className="bg-page text-secondary">
                            {course}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-start">
                    <Button
                      onClick={() => handleOpenEdit(item)}
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span>Edit</span>
                    </Button>
                    <Button
                      onClick={() =>
                        item.id &&
                        setItemToDelete({
                          id: item.id,
                          name: `${item.degree} @ ${item.institution}`,
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
        title={editingId ? "Edit Degree" : "Add Degree"}
        description="Provide university name, degree title, major, date range, and coursework."
        maxWidth="xl"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {submitError && (
            <div className="flex items-center gap-2 rounded-btn bg-status-error-soft p-3 text-status-error text-small font-medium border border-status-error/20">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Institution / University *</label>
            <Input
              placeholder="e.g. Stanford University or MIT"
              {...register("institution")}
              className={errors.institution ? "border-status-error" : ""}
            />
            {errors.institution && (
              <p className="text-caption text-status-error">{errors.institution.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Degree *</label>
              <Input
                placeholder="e.g. B.S. or Master of Science"
                {...register("degree")}
                className={errors.degree ? "border-status-error" : ""}
              />
              {errors.degree && (
                <p className="text-caption text-status-error">{errors.degree.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Field of Study *</label>
              <Input
                placeholder="e.g. Computer Science & AI"
                {...register("fieldOfStudy")}
                className={errors.fieldOfStudy ? "border-status-error" : ""}
              />
              {errors.fieldOfStudy && (
                <p className="text-caption text-status-error">{errors.fieldOfStudy.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Start Date (YYYY-MM) *</label>
              <Input
                placeholder="2018-09"
                {...register("startDate")}
                className={errors.startDate ? "border-status-error" : ""}
              />
              {errors.startDate && (
                <p className="text-caption text-status-error">{errors.startDate.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">End Date (or Expected) *</label>
              <Input
                placeholder="2022-06"
                {...register("endDate")}
                className={errors.endDate ? "border-status-error" : ""}
              />
              {errors.endDate && (
                <p className="text-caption text-status-error">{errors.endDate.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">GPA / Grade / Honors</label>
              <Input placeholder="e.g. 3.92 / 4.0 (Magna Cum Laude)" {...register("grade")} />
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Activities & Societies</label>
              <Input placeholder="e.g. ACM President, Robotics Club" {...register("activities")} />
            </div>
          </div>

          {/* Courses */}
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">Relevant Coursework</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. Distributed Systems, Machine Learning"
                value={courseInput}
                onChange={(e) => setCourseInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddCourse();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={handleAddCourse}>
                Add Course
              </Button>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {coursesList.map((course) => (
                <Badge key={course} variant="secondary" className="gap-1.5 py-1 px-2">
                  <span>{course}</span>
                  <button type="button" onClick={() => handleRemoveCourse(course)}>
                    <X className="h-3 w-3 hover:text-primary" />
                  </button>
                </Badge>
              ))}
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
                <span>{editingId ? "Save Changes" : "Add Degree"}</span>
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
        title="Delete Academic Degree"
        description="Are you sure you want to delete this degree record from your Master Career Workspace? Existing targeted resume variants will not be affected."
        itemName={itemToDelete?.name}
      />
    </div>
  );
}
