"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AppSidebar } from "@/components/common/app-sidebar";
import { AppHeader } from "@/components/common/app-header";
import { LoadingState } from "@/components/common/state-views";
import { WorkspaceAutoRefresh, GlobalToastHost } from "@/components/common/workspace-auto-refresh";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-page">
        <LoadingState text="Verifying authentication..." />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-page print:h-auto print:w-auto print:overflow-visible print:bg-white print:block">
      {/* Desktop Fixed Left Sidebar */}
      <div className="hidden md:flex h-full flex-shrink-0 print:hidden no-print">
        <AppSidebar />
      </div>

      {/* Mobile Drawer Backdrop & Sidebar */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden print:hidden no-print">
          <div
            className="fixed inset-0 bg-primary/40 transition-opacity"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative z-50 h-full w-64 animate-in slide-in-from-left duration-200">
            <AppSidebar onCloseMobile={() => setIsMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden print:overflow-visible print:h-auto print:w-full print:block">
        <div className="print:hidden no-print">
          <AppHeader onOpenMobileMenu={() => setIsMobileMenuOpen(true)} />
        </div>
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 print:p-0 print:m-0 print:overflow-visible print:h-auto print:w-full print:block">
          <div className="mx-auto max-w-7xl space-y-6 print:m-0 print:p-0 print:max-w-none print:w-full print:space-y-0 print:block">{children}</div>
        </main>
      </div>

      {/* Workspace is the source of truth: auto-refresh stale tailored resumes */}
      <div className="print:hidden no-print">
        <WorkspaceAutoRefresh />
        <GlobalToastHost />
      </div>
    </div>
  );
}

