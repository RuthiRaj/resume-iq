import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | undefined): string {
  if (!dateString) return "";
  if (dateString.toLowerCase() === "present") return "Present";
  try {
    const [year, month] = dateString.split("-");
    if (!year) return dateString;
    if (!month) return year;
    const date = new Date(parseInt(year), parseInt(month) - 1);
    return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
  } catch {
    return dateString;
  }
}

export function calculateCareerSignal(data: {
  profile: unknown;
  education: unknown[];
  skills: unknown[];
  projects: unknown[];
  experience: unknown[];
  certifications: unknown[];
}): {
  overall: number;
  breakdown: {
    name: string;
    key: string;
    score: number;
    weight: number;
    color: string;
  }[];
} {
  // Score calculations (0-100)
  const profileScore = data.profile ? 95 : 0;
  const educationScore = data.education.length >= 2 ? 100 : data.education.length === 1 ? 80 : 0;
  const skillsScore = data.skills.length >= 10 ? 100 : Math.min(100, data.skills.length * 10);
  const projectsScore = data.projects.length >= 3 ? 100 : data.projects.length * 33;
  const experienceScore = data.experience.length >= 2 ? 100 : data.experience.length * 50;
  const certScore = data.certifications.length >= 2 ? 100 : data.certifications.length * 50;

  const breakdown = [
    { name: "Profile", key: "profile", score: Math.round(profileScore), weight: 0.15, color: "#3652D9" },
    { name: "Education", key: "education", score: Math.round(educationScore), weight: 0.15, color: "#4F6DF5" },
    { name: "Skills", key: "skills", score: Math.round(skillsScore), weight: 0.2, color: "#6E87F9" },
    { name: "Projects", key: "projects", score: Math.round(projectsScore), weight: 0.2, color: "#8FA3FC" },
    { name: "Experience", key: "experience", score: Math.round(experienceScore), weight: 0.2, color: "#B1C0FD" },
    { name: "Certifications", key: "certifications", score: Math.round(certScore), weight: 0.1, color: "#D1DBFE" },
  ];

  const overall = Math.round(
    breakdown.reduce((acc, item) => acc + (item.score * item.weight), 0)
  );

  return { overall, breakdown };
}
