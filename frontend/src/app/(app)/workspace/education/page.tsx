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
} from "lucide-react";

export default function EducationPage() {
  const { education, addEducation, updateEducation, deleteEducation } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [courseInput, setCourseInput] = useState("");
  const [coursesList, setCoursesList] = useState<string[]>([]);

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

  const onSubmit = (data: EducationData) => {
    const submission = { ...data, courses: coursesList };
    if (editingId) {
      updateEducation(editingId, submission);
    } else {
      addEducation(submission);
    }
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
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

      {education.length === 0 ? (
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
                        <span className="font-semibold text-primary">Honors & Activities: </span>
                        {item.activities}
                      </p>
                    )}

                    {item.courses && item.courses.length > 0 && (
                      <div className="pt-2">
                        <div className="text-caption font-semibold text-muted uppercase mb-1.5">
                          Relevant Coursework
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {item.courses.map((course) => (
                            <Badge key={course} variant="outline" className="text-secondary bg-page">
                              {course}
                            </Badge>
                          ))}
                        </div>
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
                      onClick={() => item.id && deleteEducation(item.id)}
                      variant="ghost"
                      size="sm"
                      className="text-status-error hover:bg-status-error-soft hover:text-status-error"
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

      {/* Add/Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingId ? "Edit Academic Degree" : "Add Academic Degree"}
        description="Provide institution, degree name, dates, and relevant coursework."
        maxWidth="2xl"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Institution / University</label>
            <Input
              placeholder="e.g. University of California, Berkeley"
              {...register("institution")}
              className={errors.institution ? "border-status-error" : ""}
            />
            {errors.institution && (
              <p className="text-caption text-status-error">{errors.institution.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Degree</label>
              <Input
                placeholder="e.g. B.S. in Computer Science"
                {...register("degree")}
                className={errors.degree ? "border-status-error" : ""}
              />
              {errors.degree && (
                <p className="text-caption text-status-error">{errors.degree.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Field of Study</label>
              <Input
                placeholder="e.g. Computer Science"
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
              <label className="text-small font-medium text-primary">Start Date (YYYY-MM)</label>
              <Input
                placeholder="e.g. 2020-08"
                {...register("startDate")}
                className={errors.startDate ? "border-status-error" : ""}
              />
              {errors.startDate && (
                <p className="text-caption text-status-error">{errors.startDate.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">End Date (or Expected)</label>
              <Input
                placeholder="e.g. 2024-05"
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
              <label className="text-small font-medium text-primary">Grade / GPA (Optional)</label>
              <Input placeholder="e.g. 3.88 / 4.0 GPA" {...register("grade")} />
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Honors & Activities</label>
              <Input
                placeholder="e.g. Dean's Honors List, Lead Chair @ ACM"
                {...register("activities")}
              />
            </div>
          </div>

          {/* Coursework Tags */}
          <div className="space-y-2">
            <label className="text-small font-medium text-primary">Relevant Coursework</label>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. Distributed Systems"
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
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingId ? "Save Changes" : "Add Degree"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
