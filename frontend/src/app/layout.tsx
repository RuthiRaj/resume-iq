import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/styles/globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { CareerProvider } from "@/lib/store";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ResumeIQ — AI Career Workspace & Resume Intelligence Platform",
  description:
    "Store your career information once. Let AI intelligently use it to create and analyze resumes tailored to every job opportunity.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-page text-primary antialiased">
        <AuthProvider>
          <CareerProvider>{children}</CareerProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
