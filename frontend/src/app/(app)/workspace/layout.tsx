"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  User,
  GraduationCap,
  Layers,
  Sparkles,
  Briefcase,
  Award,
  Trophy,
  Files,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const tabs = [
    { label: "Profile", href: "/workspace/profile", icon: User },
    { label: "Education", href: "/workspace/education", icon: GraduationCap },
    { label: "Skills", href: "/workspace/skills", icon: Layers },
    { label: "Projects", href: "/workspace/projects", icon: Sparkles },
    { label: "Experience", href: "/workspace/experience", icon: Briefcase },
    { label: "Certifications", href: "/workspace/certifications", icon: Award },
    { label: "Achievements", href: "/workspace/achievements", icon: Trophy },
    { label: "Documents", href: "/workspace/documents", icon: Files },
  ];

  return (
    <div className="space-y-6">
      {/* Workspace Header & Subnavigation Tabs */}
      <div className="border-b border-border pb-4 space-y-4">
        <div>
          <h1 className="text-h1 font-semibold text-primary">Career Workspace</h1>
          <p className="text-small text-secondary mt-0.5">
            Maintain your unified career information. Everything here is used by AI to assemble tailored resumes.
          </p>
        </div>

        {/* Horizontal Navigation Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = pathname === tab.href;

            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "flex items-center gap-2 rounded-btn px-3 py-1.5 text-body whitespace-nowrap transition-colors border",
                  isActive
                    ? "bg-surface font-semibold text-accent border-accent/40 shadow-subtle"
                    : "bg-surface/50 text-secondary border-border hover:bg-surface hover:text-primary"
                )}
              >
                <Icon
                  className={cn("h-3.5 w-3.5", isActive ? "text-accent" : "text-muted")}
                />
                <span>{tab.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Workspace Screen Body */}
      <div>{children}</div>
    </div>
  );
}
