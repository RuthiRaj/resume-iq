"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Search,
  Menu,
  Sparkles,
  Plus,
  Zap,
  UploadCloud,
  FileText,
  HelpCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { CommandMenu } from "./command-menu";

interface AppHeaderProps {
  onOpenMobileMenu?: () => void;
}

export function AppHeader({ onOpenMobileMenu }: AppHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const [isCreateMenuOpen, setIsCreateMenuOpen] = useState(false);

  // Generate clean breadcrumb / title
  const getPageMeta = () => {
    if (pathname.startsWith("/workspace/profile")) return { section: "Career Profile", title: "Personal Profile" };
    if (pathname.startsWith("/workspace/education")) return { section: "Career Profile", title: "Education History" };
    if (pathname.startsWith("/workspace/skills")) return { section: "Career Profile", title: "Technical Skills" };
    if (pathname.startsWith("/workspace/experience")) return { section: "Career Profile", title: "Work Experience" };
    if (pathname.startsWith("/workspace/projects")) return { section: "Career Profile", title: "Featured Projects" };
    if (pathname.startsWith("/workspace/certifications")) return { section: "Career Profile", title: "Certifications" };
    if (pathname.startsWith("/workspace/achievements")) return { section: "Career Profile", title: "Achievements" };
    if (pathname.startsWith("/workspace/documents")) return { section: "Career Profile", title: "Documents & Transcripts" };
    if (pathname.startsWith("/builder")) return { section: "Resume Studio", title: "Resume Builder" };
    if (pathname.startsWith("/resumes")) return { section: "Resume Studio", title: "My Resumes" };
    if (pathname.startsWith("/analyzer")) return { section: "Resume Intelligence", title: "Resume ATS Analyzer" };
    if (pathname.startsWith("/settings")) return { section: "System", title: "Settings" };
    return { section: "Overview", title: "Dashboard" };
  };

  const meta = getPageMeta();

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border bg-surface px-4 sm:px-6">
        {/* Left: Mobile Menu Toggle & Title */}
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenMobileMenu}
            className="rounded-btn p-1.5 text-secondary hover:bg-page md:hidden"
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex items-center gap-2 text-small text-secondary">
            <span className="hidden sm:inline-block">{meta.section}</span>
            <span className="hidden sm:inline-block text-border">/</span>
            <span className="text-body font-semibold text-primary">{meta.title}</span>
          </div>
        </div>

        {/* Right: Quick Search + Action Buttons */}
        <div className="flex items-center gap-2.5">
          {/* Quick Search trigger button */}
          <button
            onClick={() => setIsCommandOpen(true)}
            className="hidden sm:flex h-9 w-64 items-center justify-between rounded-input border border-border bg-page px-3 text-small text-secondary hover:border-accent/40 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-muted" />
              <span>Search workspace...</span>
            </div>
            <kbd className="rounded border border-border/80 bg-surface px-1.5 py-0.5 text-[10px] font-mono text-muted">
              Ctrl+K
            </kbd>
          </button>

          <button
            onClick={() => setIsCommandOpen(true)}
            className="flex sm:hidden h-9 w-9 items-center justify-center rounded-btn border border-border bg-page text-secondary"
            aria-label="Search"
          >
            <Search className="h-4 w-4" />
          </button>

          {/* New Resume Dropdown / Button */}
          <div className="relative">
            <Button
              onClick={() => setIsCreateMenuOpen(!isCreateMenuOpen)}
              variant="primary"
              size="sm"
              className="gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New Resume</span>
              <span className="sm:hidden">New</span>
            </Button>

            {isCreateMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsCreateMenuOpen(false)}
                />
                <div className="absolute right-0 top-full z-50 mt-1.5 w-56 rounded-btn border border-border bg-surface p-1.5 shadow-dropdown animate-in fade-in-50 slide-in-from-top-1">
                  <button
                    onClick={() => {
                      setIsCreateMenuOpen(false);
                      router.push("/builder");
                    }}
                    className="flex w-full items-center gap-2.5 rounded-btn p-2 text-left text-body hover:bg-accent-soft hover:text-accent group transition-colors"
                  >
                    <Sparkles className="h-4 w-4 text-accent" />
                    <div>
                      <div className="font-medium text-primary group-hover:text-accent">Generate from Job</div>
                      <div className="text-caption text-secondary">Tailor to specific JD</div>
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      setIsCreateMenuOpen(false);
                      router.push("/analyzer");
                    }}
                    className="flex w-full items-center gap-2.5 rounded-btn p-2 text-left text-body hover:bg-accent-soft hover:text-accent group transition-colors"
                  >
                    <Zap className="h-4 w-4 text-accent" />
                    <div>
                      <div className="font-medium text-primary group-hover:text-accent">Analyze ATS Match</div>
                      <div className="text-caption text-secondary">Check score against JD</div>
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      setIsCreateMenuOpen(false);
                      router.push("/workspace/documents");
                    }}
                    className="flex w-full items-center gap-2.5 rounded-btn p-2 text-left text-body hover:bg-accent-soft hover:text-accent group transition-colors"
                  >
                    <UploadCloud className="h-4 w-4 text-accent" />
                    <div>
                      <div className="font-medium text-primary group-hover:text-accent">Upload & Parse</div>
                      <div className="text-caption text-secondary">Import existing PDF</div>
                    </div>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Global Command Palette */}
      <CommandMenu isOpen={isCommandOpen} onClose={() => setIsCommandOpen(false)} />
    </>
  );
}
