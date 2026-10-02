import type { ResumeItem } from "@/lib/store";

/**
 * PR1-H7: pure search filter for /resumes.
 *
 * Null/undefined title, targetRole, or targetCompany are treated as empty
 * strings so filtering never throws. Behavior is identical to the inline
 * filter previously in `resumes/page.tsx`.
 */
export function filterResumes(resumes: ResumeItem[], searchQuery: string): ResumeItem[] {
  const query = (searchQuery ?? "").toLowerCase();
  return resumes.filter((r) => {
    return (
      (r.title ?? "").toLowerCase().includes(query) ||
      (r.targetRole ?? "").toLowerCase().includes(query) ||
      (r.targetCompany ?? "").toLowerCase().includes(query)
    );
  });
}
