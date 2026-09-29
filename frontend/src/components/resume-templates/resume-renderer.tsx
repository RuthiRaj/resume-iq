"use client";

import React from "react";
import { ProfileData, EducationData, SkillData, ProjectData, ExperienceData, CertificationData } from "@/lib/validations";
import { ResumeItem } from "@/lib/store";
import { formatDate } from "@/lib/utils";
import { Globe, Linkedin, Github, Mail, Phone, MapPin } from "lucide-react";

export interface ResumeData {
  profile: ProfileData;
  education: EducationData[];
  skills: SkillData[];
  projects: ProjectData[];
  experience: ExperienceData[];
  certifications: CertificationData[];
  customSummary?: string;
}

/**
 * Resolves the renderable resume data.
 * If an immutable snapshot exists on the resume, it renders from the snapshot.
 * Otherwise, it falls back to resolving entities from live Career Profile data (legacy compatibility).
 */
export function resolveResumeData(
  resume: ResumeItem,
  liveData?: {
    profile: ProfileData;
    education: EducationData[];
    skills: SkillData[];
    projects: ProjectData[];
    experience: ExperienceData[];
    certifications: CertificationData[];
  }
): ResumeData {
  // 1. Immutable snapshot path (Preferred point-in-time state)
  if (resume.snapshot) {
    return {
      profile: resume.snapshot.profile || (liveData?.profile as ProfileData),
      education: resume.snapshot.education || [],
      skills: resume.snapshot.skills || [],
      projects: resume.snapshot.projects || [],
      experience: resume.snapshot.experience || [],
      certifications: resume.snapshot.certifications || [],
      customSummary: resume.snapshot.customSummary || resume.sections?.summary,
    };
  }

  // 2. Legacy fallback path (resolves live entities by ID references)
  if (liveData) {
    const activeExp = liveData.experience.filter(
      (e) => e.id && resume.sections?.experiences?.includes(e.id)
    );
    const activeProj = liveData.projects.filter(
      (p) => p.id && resume.sections?.projects?.includes(p.id)
    );

    return {
      profile: liveData.profile,
      education: liveData.education,
      skills: liveData.skills,
      experience: activeExp.length > 0 ? activeExp : liveData.experience,
      projects: activeProj.length > 0 ? activeProj : liveData.projects,
      certifications: liveData.certifications,
      customSummary: resume.sections?.summary || liveData.profile.summary,
    };
  }

  // Safe fallback if liveData not provided and snapshot missing
  return {
    profile: {
      fullName: "",
      headline: "",
      email: "",
      phone: "",
      location: "",
      website: "",
      linkedin: "",
      github: "",
      summary: "",
      targetRoles: [],
    },
    education: [],
    skills: [],
    projects: [],
    experience: [],
    certifications: [],
    customSummary: resume.sections?.summary || "",
  };
}

export const ResumeModernTemplate = React.memo(function ResumeModernTemplate({ data }: { data: ResumeData }) {
  const { profile, education, skills, projects, experience, certifications, customSummary } = data;

  return (
    <div className="bg-white p-8 font-sans text-primary text-[11px] leading-[15px] max-w-[800px] mx-auto border border-border shadow-sm print:border-none print:shadow-none print:max-w-none print:w-full print:m-0 print:p-0 print:text-black">
      {/* Header */}
      <div className="border-b-2 border-accent pb-4 mb-4 break-inside-avoid print:break-inside-avoid">
        <h1 className="text-[20px] font-bold text-primary print:text-black tracking-tight">{profile.fullName}</h1>
        <p className="text-[12px] font-medium text-accent print:text-[#3652D9] mt-0.5">{profile.headline}</p>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-secondary print:text-[#475467] mt-2">
          {profile.email && <span>{profile.email}</span>}
          {profile.phone && <span>&bull; {profile.phone}</span>}
          {profile.location && <span>&bull; {profile.location}</span>}
          {profile.website && <span>&bull; {profile.website.replace("https://", "")}</span>}
          {profile.linkedin && <span>&bull; {profile.linkedin.replace("https://", "")}</span>}
          {profile.github && <span>&bull; {profile.github.replace("https://", "")}</span>}
        </div>
      </div>

      {/* Summary */}
      <div className="mb-4 break-inside-avoid print:break-inside-avoid">
        <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-1.5">
          Executive Summary
        </h2>
        <p className="text-secondary print:text-black leading-relaxed">{customSummary || profile.summary}</p>
      </div>

      {/* Experience */}
      {experience.length > 0 && (
        <div className="mb-4">
          <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-2 break-after-avoid print:break-after-avoid">
            Work Experience
          </h2>
          <div className="space-y-3">
            {experience.map((exp) => (
              <div key={exp.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline">
                  <span className="font-bold text-primary print:text-black text-[11.5px]">{exp.role}</span>
                  <span className="text-muted print:text-[#475467] text-[10px]">
                    {formatDate(exp.startDate)} &mdash; {exp.isCurrent ? "Present" : formatDate(exp.endDate)}
                  </span>
                </div>
                <div className="flex justify-between items-baseline text-secondary print:text-[#344054] text-[10.5px] font-medium mb-1">
                  <span>{exp.company}</span>
                  <span>{exp.location}</span>
                </div>
                <ul className="list-disc pl-3.5 space-y-0.5 text-secondary print:text-black">
                  {exp.bullets?.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Projects */}
      {projects.length > 0 && (
        <div className="mb-4">
          <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-2 break-after-avoid print:break-after-avoid">
            Featured Projects
          </h2>
          <div className="space-y-2.5">
            {projects.map((proj) => (
              <div key={proj.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline">
                  <span className="font-bold text-primary print:text-black">{proj.title}</span>
                  <span className="text-muted print:text-[#475467] text-[10px]">
                    {formatDate(proj.startDate)} &mdash; {formatDate(proj.endDate)}
                  </span>
                </div>
                <div className="text-[10px] text-accent print:text-[#3652D9] font-medium mb-0.5">
                  Tech Stack: {proj.techStack?.join(", ")}
                </div>
                <ul className="list-disc pl-3.5 space-y-0.5 text-secondary print:text-black">
                  {proj.highlights?.map((hl, i) => (
                    <li key={i}>{hl}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div className="mb-4 break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-1.5">
            Technical Skills
          </h2>
          <p className="text-secondary print:text-black leading-normal">
            <span className="font-semibold text-primary print:text-black">Core Competencies: </span>
            {skills.map((s) => s.name).join(" • ")}
          </p>
        </div>
      )}

      {/* Education */}
      {education.length > 0 && (
        <div className="mb-4">
          <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-2 break-after-avoid print:break-after-avoid">
            Education
          </h2>
          <div className="space-y-2">
            {education.map((edu) => (
              <div key={edu.id} className="flex justify-between items-baseline break-inside-avoid print:break-inside-avoid">
                <div>
                  <span className="font-bold text-primary print:text-black">{edu.institution}</span>
                  <div className="text-secondary print:text-black">
                    {edu.degree} in {edu.fieldOfStudy} {edu.grade ? `(${edu.grade})` : ""}
                  </div>
                </div>
                <span className="text-muted print:text-[#475467] text-[10px]">
                  {formatDate(edu.startDate)} &mdash; {formatDate(edu.endDate)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Certifications */}
      {certifications.length > 0 && (
        <div className="break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[12px] font-bold text-accent print:text-[#3652D9] uppercase tracking-wider mb-1.5">
            Certifications
          </h2>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-secondary print:text-black text-[10.5px]">
            {certifications.map((c) => (
              <span key={c.id}>
                &bull; <strong className="text-primary print:text-black">{c.title}</strong> &mdash; {c.issuer} ({formatDate(c.issueDate)})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});


export const ResumeMinimalTemplate = React.memo(function ResumeMinimalTemplate({ data }: { data: ResumeData }) {
  const { profile, education, skills, projects, experience, certifications, customSummary } = data;

  return (
    <div className="bg-white p-8 font-sans text-primary text-[11px] leading-[15px] max-w-[800px] mx-auto border border-border shadow-sm print:border-none print:shadow-none print:max-w-none print:w-full print:m-0 print:p-0 print:text-black">
      <div className="text-center pb-4 mb-4 border-b border-border break-inside-avoid print:break-inside-avoid">
        <h1 className="text-[22px] font-normal tracking-wide uppercase text-primary print:text-black">
          {profile.fullName}
        </h1>
        <p className="text-[11px] text-secondary print:text-[#344054] tracking-wider uppercase mt-0.5">
          {profile.headline}
        </p>
        <div className="flex justify-center flex-wrap gap-x-3 text-[10px] text-muted print:text-[#475467] mt-1.5">
          {profile.email && <span>{profile.email}</span>}
          {profile.phone && <span>|</span>}
          {profile.phone && <span>{profile.phone}</span>}
          {profile.location && <span>|</span>}
          {profile.location && <span>{profile.location}</span>}
        </div>
      </div>

      {/* Summary */}
      <div className="mb-4 break-inside-avoid print:break-inside-avoid">
        <h2 className="text-[11px] font-bold uppercase tracking-widest text-primary print:text-black border-b border-border/80 pb-0.5 mb-1.5">
          Profile
        </h2>
        <p className="text-secondary print:text-black leading-relaxed">{customSummary || profile.summary}</p>
      </div>

      {/* Experience */}
      {experience.length > 0 && (
        <div className="mb-4">
          <h2 className="text-[11px] font-bold uppercase tracking-widest text-primary print:text-black border-b border-border/80 pb-0.5 mb-2 break-after-avoid print:break-after-avoid">
            Experience
          </h2>
          <div className="space-y-3">
            {experience.map((exp) => (
              <div key={exp.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline">
                  <span className="font-semibold text-primary print:text-black">{exp.role}, {exp.company}</span>
                  <span className="text-muted print:text-[#475467] text-[10px]">
                    {formatDate(exp.startDate)} — {exp.isCurrent ? "Present" : formatDate(exp.endDate)}
                  </span>
                </div>
                <ul className="list-square pl-3.5 space-y-0.5 text-secondary print:text-black mt-1">
                  {exp.bullets?.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Projects */}
      {projects.length > 0 && (
        <div className="mb-4">
          <h2 className="text-[11px] font-bold uppercase tracking-widest text-primary print:text-black border-b border-border/80 pb-0.5 mb-2 break-after-avoid print:break-after-avoid">
            Projects
          </h2>
          <div className="space-y-2.5">
            {projects.map((proj) => (
              <div key={proj.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline">
                  <span className="font-semibold text-primary print:text-black">{proj.title}</span>
                  <span className="text-muted print:text-[#475467] text-[10px]">
                    {formatDate(proj.startDate)} — {formatDate(proj.endDate)}
                  </span>
                </div>
                <ul className="list-square pl-3.5 space-y-0.5 text-secondary print:text-black mt-0.5">
                  {proj.highlights?.map((hl, i) => (
                    <li key={i}>{hl}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div className="mb-4 break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[11px] font-bold uppercase tracking-widest text-primary print:text-black border-b border-border/80 pb-0.5 mb-1.5">
            Skills
          </h2>
          <p className="text-secondary print:text-black">{skills.map((s) => s.name).join(" / ")}</p>
        </div>
      )}

      {/* Education */}
      {education.length > 0 && (
        <div className="break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[11px] font-bold uppercase tracking-widest text-primary print:text-black border-b border-border/80 pb-0.5 mb-1.5 break-after-avoid print:break-after-avoid">
            Education
          </h2>
          <div className="space-y-1">
            {education.map((edu) => (
              <div key={edu.id} className="flex justify-between items-baseline break-inside-avoid print:break-inside-avoid">
                <span className="text-primary print:text-black font-medium">
                  {edu.degree}, {edu.institution}
                </span>
                <span className="text-muted print:text-[#475467] text-[10px]">
                  {formatDate(edu.startDate)} — {formatDate(edu.endDate)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});


export const ResumeAtsTemplate = React.memo(function ResumeAtsTemplate({ data }: { data: ResumeData }) {
  const { profile, education, skills, projects, experience, certifications, customSummary } = data;

  return (
    <div className="bg-white p-8 font-sans text-black text-[11px] leading-[15px] max-w-[800px] mx-auto border border-border shadow-sm print:border-none print:shadow-none print:max-w-none print:w-full print:m-0 print:p-0">
      <div className="text-center pb-3 mb-3 border-b-2 border-black break-inside-avoid print:break-inside-avoid">
        <h1 className="text-[20px] font-bold uppercase tracking-tight text-black">
          {profile.fullName}
        </h1>
        <div className="flex justify-center flex-wrap gap-x-2 text-[10.5px] text-black mt-1">
          {profile.location && <span>{profile.location}</span>}
          {profile.email && <span>|</span>}
          {profile.email && <span>{profile.email}</span>}
          {profile.phone && <span>|</span>}
          {profile.phone && <span>{profile.phone}</span>}
          {profile.linkedin && <span>|</span>}
          {profile.linkedin && <span>{profile.linkedin}</span>}
        </div>
      </div>

      <div className="mb-3 break-inside-avoid print:break-inside-avoid">
        <h2 className="text-[12px] font-bold uppercase border-b border-black pb-0.5 mb-1 text-black">
          PROFESSIONAL SUMMARY
        </h2>
        <p className="text-black leading-normal">{customSummary || profile.summary}</p>
      </div>

      {skills.length > 0 && (
        <div className="mb-3 break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[12px] font-bold uppercase border-b border-black pb-0.5 mb-1 text-black">
            TECHNICAL SKILLS
          </h2>
          <p className="text-black leading-normal">
            <strong>Key Competencies:</strong> {skills.map((s) => s.name).join(", ")}
          </p>
        </div>
      )}

      {experience.length > 0 && (
        <div className="mb-3">
          <h2 className="text-[12px] font-bold uppercase border-b border-black pb-0.5 mb-1.5 text-black break-after-avoid print:break-after-avoid">
            WORK EXPERIENCE
          </h2>
          <div className="space-y-2.5">
            {experience.map((exp) => (
              <div key={exp.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline font-bold text-black">
                  <span>{exp.company} — {exp.location}</span>
                  <span>{formatDate(exp.startDate)} – {exp.isCurrent ? "Present" : formatDate(exp.endDate)}</span>
                </div>
                <div className="italic text-black font-semibold mb-0.5">{exp.role}</div>
                <ul className="list-disc pl-4 space-y-0.5 text-black">
                  {exp.bullets?.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {projects.length > 0 && (
        <div className="mb-3">
          <h2 className="text-[12px] font-bold uppercase border-b border-black pb-0.5 mb-1.5 text-black break-after-avoid print:break-after-avoid">
            TECHNICAL PROJECTS
          </h2>
          <div className="space-y-2">
            {projects.map((proj) => (
              <div key={proj.id} className="break-inside-avoid print:break-inside-avoid space-y-0.5">
                <div className="flex justify-between items-baseline font-bold text-black">
                  <span>{proj.title} | {proj.role}</span>
                  <span>{formatDate(proj.startDate)} – {formatDate(proj.endDate)}</span>
                </div>
                <ul className="list-disc pl-4 space-y-0.5 text-black">
                  {proj.highlights?.map((hl, i) => (
                    <li key={i}>{hl}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {education.length > 0 && (
        <div className="break-inside-avoid print:break-inside-avoid">
          <h2 className="text-[12px] font-bold uppercase border-b border-black pb-0.5 mb-1 text-black break-after-avoid print:break-after-avoid">
            EDUCATION
          </h2>
          <div className="space-y-1">
            {education.map((edu) => (
              <div key={edu.id} className="flex justify-between items-baseline text-black break-inside-avoid print:break-inside-avoid">
                <div>
                  <span className="font-bold">{edu.institution}</span> &mdash; {edu.degree} ({edu.fieldOfStudy})
                </div>
                <span>{formatDate(edu.startDate)} – {formatDate(edu.endDate)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

export const ResumeUniversalRenderer = React.memo(function ResumeUniversalRenderer({
  template,
  data,
  resume,
  liveData,
}: {
  template: "modern" | "minimal" | "professional" | "ats";
  data?: ResumeData;
  resume?: ResumeItem;
  liveData?: {
    profile: ProfileData;
    education: EducationData[];
    skills: SkillData[];
    projects: ProjectData[];
    experience: ExperienceData[];
    certifications: CertificationData[];
  };
}) {
  const resolvedData: ResumeData =
    data || (resume ? resolveResumeData(resume, liveData) : ({} as ResumeData));

  switch (template) {
    case "minimal":
      return <ResumeMinimalTemplate data={resolvedData} />;
    case "ats":
    case "professional":
      return <ResumeAtsTemplate data={resolvedData} />;
    case "modern":
    default:
      return <ResumeModernTemplate data={resolvedData} />;
  }
});

