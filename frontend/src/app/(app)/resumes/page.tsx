"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCareer, ResumeItem } from "@/lib/store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/common/state-views";
import { formatDate } from "@/lib/utils";
import {
  FileText,
  Plus,
  Pencil,
  Copy,
  Trash2,
  Zap,
  Download,
  Calendar,
  Grid,
  List,
  Search,
  ExternalLink,
  Sparkles,
} from "lucide-react";

export default function ResumesPage() {
  const router = useRouter();
  const { resumes, duplicateResume, deleteResume, updateResume } = useCareer();

  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [searchQuery, setSearchQuery] = useState("");
  const [renameItem, setRenameItem] = useState<ResumeItem | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const filtered = resumes.filter(
    (r) =>
      r.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.targetRole.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.targetCompany && r.targetCompany.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleOpenRename = (r: ResumeItem) => {
    setRenameItem(r);
    setRenameTitle(r.title);
  };

  const handleSaveRename = () => {
    if (renameItem && renameTitle.trim()) {
      updateResume(renameItem.id, { title: renameTitle.trim() });
      setRenameItem(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-h1 font-semibold text-primary">My Saved Resumes</h1>
          <p className="text-small text-secondary mt-0.5">
            Manage target resume versions, run ATS score audits, and export to PDF.
          </p>
        </div>

        <Link href="/builder" className="self-start sm:self-center">
          <Button variant="primary" size="sm" className="gap-1.5">
            <Plus className="h-4 w-4" />
            <span>Create New Resume</span>
          </Button>
        </Link>
      </div>

      {/* Filter & View Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <Input
            placeholder="Search by role, company, title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-small h-9"
          />
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-btn border border-border bg-page p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={`rounded p-1 text-secondary transition-colors ${
                viewMode === "grid" ? "bg-surface text-primary font-semibold shadow-subtle" : "hover:text-primary"
              }`}
              aria-label="Grid view"
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`rounded p-1 text-secondary transition-colors ${
                viewMode === "list" ? "bg-surface text-primary font-semibold shadow-subtle" : "hover:text-primary"
              }`}
              aria-label="List view"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {filtered.length === 0 ? (
        <EmptyState
          title="No resumes found"
          description="Create your first tailored resume using our AI Builder or adjust your search filter."
          actionLabel="Create Resume"
          onAction={() => router.push("/builder")}
          icon={FileText}
        />
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((res) => (
            <Card key={res.id} className="hover:border-accent/40 transition-all flex flex-col justify-between">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <Badge variant="outline" className="capitalize text-[10px]">
                      {res.template} Template
                    </Badge>
                    <h3 className="text-body font-bold text-primary line-clamp-2 pt-1">{res.title}</h3>
                  </div>

                  <div className="flex flex-col items-end">
                    <span className="text-caption uppercase text-muted font-semibold">ATS</span>
                    <span className="text-body font-bold text-status-success">{res.score}%</span>
                  </div>
                </div>

                <div className="space-y-1 text-small text-secondary">
                  <div>Target: <strong className="text-primary">{res.targetRole}</strong></div>
                  {res.targetCompany && <div>Company: <strong className="text-primary">{res.targetCompany}</strong></div>}
                  <div className="text-caption text-muted pt-1">
                    Edited {formatDate(res.lastEdited)}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1 pt-1">
                  {res.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10.5px]">
                      {tag}
                    </Badge>
                  ))}
                </div>

                <div className="flex items-center justify-between border-t border-border/80 pt-3">
                  <div className="flex items-center gap-1">
                    <Link href={`/builder?resumeId=${res.id}`}>
                      <Button variant="outline" size="sm" className="gap-1">
                        <Pencil className="h-3 w-3" />
                        <span>Edit</span>
                      </Button>
                    </Link>
                    <Link href={`/analyzer?resumeId=${res.id}`}>
                      <Button variant="ghost" size="sm" className="text-accent gap-1">
                        <Zap className="h-3 w-3" />
                        <span>ATS</span>
                      </Button>
                    </Link>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenRename(res)}
                      title="Rename"
                      className="p-1.5 rounded text-secondary hover:bg-page hover:text-primary"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => duplicateResume(res.id)}
                      title="Duplicate"
                      className="p-1.5 rounded text-secondary hover:bg-page hover:text-primary"
                    >
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => deleteResume(res.id)}
                      title="Delete"
                      className="p-1.5 rounded text-status-error hover:bg-status-error-soft"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((res) => (
            <Card key={res.id} className="hover:border-accent/30 transition-all">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] bg-accent-soft text-accent">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-body font-semibold text-primary">{res.title}</h4>
                      <Badge variant="outline" className="capitalize text-[10px]">
                        {res.template}
                      </Badge>
                      <Badge variant="success">{res.score}% ATS</Badge>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-small text-secondary">
                      <span>Role: {res.targetRole}</span>
                      {res.targetCompany && <span>&bull; {res.targetCompany}</span>}
                      <span>&bull;</span>
                      <span>Edited {formatDate(res.lastEdited)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center">
                  <Link href={`/builder?resumeId=${res.id}`}>
                    <Button variant="outline" size="sm">
                      Edit in Builder
                    </Button>
                  </Link>
                  <Link href={`/analyzer?resumeId=${res.id}`}>
                    <Button variant="ghost" size="sm" className="text-accent">
                      ATS Scan
                    </Button>
                  </Link>
                  <button
                    onClick={() => duplicateResume(res.id)}
                    className="p-1.5 rounded text-secondary hover:bg-page hover:text-primary"
                    title="Duplicate"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => deleteResume(res.id)}
                    className="p-1.5 rounded text-status-error hover:bg-status-error-soft"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Rename Modal */}
      {renameItem && (
        <Modal
          isOpen={true}
          onClose={() => setRenameItem(null)}
          title="Rename Resume"
          description="Update the display title for this resume version."
          maxWidth="sm"
        >
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-small font-medium text-primary">Resume Title</label>
              <Input
                value={renameTitle}
                onChange={(e) => setRenameTitle(e.target.value)}
                autoFocus
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-border/60">
              <Button variant="ghost" onClick={() => setRenameItem(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveRename}>
                Save Title
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
