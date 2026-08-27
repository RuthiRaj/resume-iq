"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  FileText,
  User,
  GraduationCap,
  Sparkles,
  Briefcase,
  Layers,
  Award,
  Trophy,
  Files,
  Zap,
  Sliders,
} from "lucide-react";
import { Modal } from "@/components/ui/modal";

export function CommandMenu({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const searchItems = [
    { name: "Dashboard Overview", category: "Overview", href: "/dashboard", icon: Sparkles },
    { name: "Personal Profile", category: "Career Profile", href: "/workspace/profile", icon: User },
    { name: "Education History", category: "Career Profile", href: "/workspace/education", icon: GraduationCap },
    { name: "Technical Skills", category: "Career Profile", href: "/workspace/skills", icon: Layers },
    { name: "Work Experience", category: "Career Profile", href: "/workspace/experience", icon: Briefcase },
    { name: "Featured Projects", category: "Career Profile", href: "/workspace/projects", icon: Sparkles },
    { name: "Certifications", category: "Career Profile", href: "/workspace/certifications", icon: Award },
    { name: "Achievements & Awards", category: "Career Profile", href: "/workspace/achievements", icon: Trophy },
    { name: "Documents & Transcripts", category: "Career Profile", href: "/workspace/documents", icon: Files },
    { name: "My Saved Resumes", category: "Resume Studio", href: "/resumes", icon: FileText },
    { name: "Resume Builder", category: "Resume Studio", href: "/builder", icon: Sparkles },
    { name: "ATS Resume Analyzer", category: "Resume Intelligence", href: "/analyzer", icon: Zap },
    { name: "Account Settings", category: "System", href: "/settings", icon: Sliders },
  ];

  const filtered = searchItems.filter(
    (item) =>
      item.name.toLowerCase().includes(query.toLowerCase()) ||
      item.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (href: string) => {
    onClose();
    router.push(href);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Quick Command & Search" maxWidth="lg">
      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <input
            autoFocus
            type="text"
            placeholder="Type a screen, skill, or tool (e.g. Projects, Analyzer)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-input border border-border bg-page pl-9 pr-3 py-2 text-body text-primary placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        <div className="max-h-72 overflow-y-auto space-y-1">
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-small text-secondary">
              No matching pages found for &ldquo;{query}&rdquo;
            </div>
          ) : (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.href}
                  onClick={() => handleSelect(item.href)}
                  className="flex w-full items-center justify-between rounded-btn p-2.5 text-left text-body hover:bg-accent-soft hover:text-accent group transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-[4px] bg-page text-secondary group-hover:bg-surface group-hover:text-accent">
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-primary group-hover:text-accent">{item.name}</span>
                  </div>
                  <span className="text-caption text-muted group-hover:text-accent font-semibold">{item.category}</span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </Modal>
  );
}
