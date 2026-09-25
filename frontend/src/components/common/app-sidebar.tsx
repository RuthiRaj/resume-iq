"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  GraduationCap,
  Sparkles,
  Briefcase,
  Layers,
  Award,
  Trophy,
  Files,
  Zap,
  FileText,
  Settings,
  X,
  Plus,
  Compass,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCareer } from "@/lib/store";
import { calculateCareerSignal } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

interface AppSidebarProps {
  onCloseMobile?: () => void;
}

export function AppSidebar({ onCloseMobile }: AppSidebarProps) {
  const pathname = usePathname();
  const { profile, education, skills, projects, experience, certifications } = useCareer();

  const { overall } = calculateCareerSignal({
    profile,
    education,
    skills,
    projects,
    experience,
    certifications,
  });

  const navGroups: NavGroup[] = [
    {
      title: "Overview",
      items: [
        { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      ],
    },
    {
      title: "Career Profile",
      items: [
        { label: "Profile", href: "/workspace/profile", icon: User },
        { label: "Education", href: "/workspace/education", icon: GraduationCap },
        { label: "Skills", href: "/workspace/skills", icon: Layers },
        { label: "Experience", href: "/workspace/experience", icon: Briefcase },
        { label: "Projects", href: "/workspace/projects", icon: Sparkles },
        { label: "Certifications", href: "/workspace/certifications", icon: Award },
        { label: "Achievements", href: "/workspace/achievements", icon: Trophy },
        { label: "Documents", href: "/workspace/documents", icon: Files },
      ],
    },
    {
      title: "Resume Studio",
      items: [
        { label: "My Resumes", href: "/resumes", icon: FileText },
        { label: "Resume Builder", href: "/builder", icon: Sparkles },
      ],
    },
    {
      title: "Career & Resume Intelligence",
      items: [
        { label: "Resume Analyzer", href: "/analyzer", icon: Zap, badge: "ATS" },
        { label: "Career Roadmaps", href: "/career/roadmaps", icon: Compass },
      ],
    },
    {
      title: "System",
      items: [
        { label: "Settings", href: "/settings", icon: Settings },
      ],
    },
  ];

  return (
    <aside className="flex h-full w-64 flex-col justify-between border-r border-border bg-surface select-none">
      {/* Top Section: Logo & Quick New Resume CTA */}
      <div className="flex flex-col">
        {/* Brand Header */}
        <div className="flex h-14 items-center justify-between border-b border-border/80 px-4">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-accent text-white font-semibold text-body">
              R
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-h2 font-semibold tracking-tight text-primary">ResumeIQ</span>
              <span className="rounded-[4px] bg-accent-soft px-1 text-[10px] font-semibold uppercase text-accent">
                AI
              </span>
            </div>
          </Link>

          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="rounded-btn p-1 text-secondary hover:bg-page md:hidden"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Quick Builder CTA */}
        <div className="p-3">
          <Link
            href="/builder"
            onClick={onCloseMobile}
            className="flex items-center justify-center gap-2 rounded-btn bg-accent px-3 py-2 text-small font-medium text-white shadow-subtle hover:bg-accent/95 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Create New Resume</span>
          </Link>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-2">
          {navGroups.map((group) => (
            <div key={group.title} className="space-y-1">
              <div className="px-2.5 py-1 text-caption text-muted font-semibold uppercase tracking-[0.4px]">
                {group.title}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onCloseMobile}
                    className={cn(
                      "flex items-center justify-between rounded-btn px-2.5 py-1.5 text-body transition-colors",
                      isActive
                        ? "bg-accent-soft font-semibold text-accent"
                        : "text-secondary hover:bg-page hover:text-primary"
                    )}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={cn(
                          "h-4 w-4",
                          isActive ? "text-accent" : "text-muted group-hover:text-primary"
                        )}
                      />
                      <span>{item.label}</span>
                    </div>

                    {item.badge && (
                      <span className="rounded-[4px] bg-accent/10 px-1 py-0.5 text-caption font-semibold text-accent">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </div>

      {/* Bottom Section: User Profile & Completeness Snapshot */}
      <div className="border-t border-border/80 p-3 space-y-3">
        {/* Workspace Completeness mini gauge */}
        <Link
          href="/workspace/profile"
          onClick={onCloseMobile}
          className="block rounded-btn border border-border bg-page p-2.5 hover:border-accent/40 transition-colors"
        >
          <div className="flex items-center justify-between text-caption text-secondary">
            <span className="font-semibold uppercase tracking-[0.4px]">Career Signal</span>
            <span className="font-semibold text-primary">{overall}%</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent transition-all duration-500"
              style={{ width: `${overall}%` }}
            />
          </div>
        </Link>

        {/* User Card */}
        <div className="flex items-center justify-between rounded-btn p-1.5">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-caption font-semibold text-accent border border-accent/20 uppercase">
              {profile.fullName
                ? profile.fullName
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                : "IQ"}
            </div>
            <div className="flex flex-col truncate">
              <span className="truncate text-body font-medium text-primary">
                {profile.fullName || "My Workspace"}
              </span>
              <span className="truncate text-caption text-secondary">Pro Plan</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
