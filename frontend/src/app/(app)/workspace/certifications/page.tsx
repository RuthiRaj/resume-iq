"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CertificationSchema, CertificationData } from "@/lib/validations";
import { useCareer } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { formatDate } from "@/lib/utils";
import { Award, Plus, Pencil, Trash2, Calendar, ExternalLink, ShieldCheck } from "lucide-react";

export default function CertificationsPage() {
  const { certifications, addCertification, updateCertification, deleteCertification } = useCareer();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CertificationData>({
    resolver: zodResolver(CertificationSchema),
  });

  const handleOpenAdd = () => {
    setEditingId(null);
    reset({
      title: "",
      issuer: "",
      issueDate: "",
      expiryDate: "",
      credentialId: "",
      credentialUrl: "",
    });
    setIsModalOpen(true);
  };

  const handleOpenEdit = (cert: CertificationData) => {
    setEditingId(cert.id || null);
    reset(cert);
    setIsModalOpen(true);
  };

  const onSubmit = (data: CertificationData) => {
    if (editingId) {
      updateCertification(editingId, data);
    } else {
      addCertification(data);
    }
    setIsModalOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-semibold text-primary">Licenses & Certifications</h2>
          <p className="text-small text-secondary">
            Verified industry credentials from AWS, Google Cloud, Meta, and professional institutes.
          </p>
        </div>
        <Button onClick={handleOpenAdd} variant="primary" size="sm" className="gap-1.5 self-start">
          <Plus className="h-4 w-4" />
          <span>Add Certification</span>
        </Button>
      </div>

      {certifications.length === 0 ? (
        <EmptyState
          title="No certifications added"
          description="Add cloud, architecture, or frontend certifications with credential verification IDs."
          actionLabel="Add Certification"
          onAction={handleOpenAdd}
          icon={Award}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {certifications.map((cert) => (
            <Card key={cert.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                        <Award className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-body font-semibold text-primary">{cert.title}</h3>
                        <p className="text-small font-medium text-secondary">{cert.issuer}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 text-small text-muted pt-1">
                      <Calendar className="h-3.5 w-3.5" />
                      <span>
                        Issued {formatDate(cert.issueDate)}
                        {cert.expiryDate ? ` &bull; Expires ${formatDate(cert.expiryDate)}` : " (No Expiration)"}
                      </span>
                    </div>

                    {cert.credentialId && (
                      <div className="text-caption text-secondary">
                        <span className="font-semibold text-primary">ID: </span>
                        <span className="font-mono">{cert.credentialId}</span>
                      </div>
                    )}

                    {cert.credentialUrl && (
                      <a
                        href={cert.credentialUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-small font-medium text-accent hover:underline pt-1"
                      >
                        <ShieldCheck className="h-3.5 w-3.5 text-status-success" />
                        <span>Verify Credential</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEdit(cert)}
                      className="rounded-[4px] p-1.5 text-secondary hover:bg-page hover:text-primary"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => cert.id && deleteCertification(cert.id)}
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
        title={editingId ? "Edit Certification" : "Add Certification"}
        description="Enter issuing authority, credential ID, and verification link."
        maxWidth="lg"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Certification Name</label>
            <Input
              placeholder="e.g. AWS Certified Solutions Architect"
              {...register("title")}
              className={errors.title ? "border-status-error" : ""}
            />
            {errors.title && (
              <p className="text-caption text-status-error">{errors.title.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Issuing Organization</label>
            <Input
              placeholder="e.g. Amazon Web Services (AWS)"
              {...register("issuer")}
              className={errors.issuer ? "border-status-error" : ""}
            />
            {errors.issuer && (
              <p className="text-caption text-status-error">{errors.issuer.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Issue Date (YYYY-MM)</label>
              <Input
                placeholder="2024-04"
                {...register("issueDate")}
                className={errors.issueDate ? "border-status-error" : ""}
              />
              {errors.issueDate && (
                <p className="text-caption text-status-error">{errors.issueDate.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Expiry Date (Optional)</label>
              <Input placeholder="2027-04" {...register("expiryDate")} />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Credential ID (Optional)</label>
            <Input placeholder="AWS-SAA-8829104" {...register("credentialId")} />
          </div>

          <div className="space-y-1.5">
            <label className="text-small font-medium text-primary">Credential Verification URL</label>
            <Input placeholder="https://aws.amazon.com/verify/..." {...register("credentialUrl")} />
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-border/60">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              {editingId ? "Save Changes" : "Add Certification"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
