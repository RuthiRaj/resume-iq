import { test, expect } from "@playwright/test";
import { resolveResumeData, emptyResumeProfile } from "@/components/resume-templates/resume-renderer";

/**
 * PR1-M4 regression: resolveResumeData must never return an undefined
 * profile — templates dereference profile.fullName directly.
 * Runs in Node (pure function, no browser needed).
 */
test.describe("resolveResumeData profile fallback (PR1-M4)", () => {
  const baseResume = (overrides: object = {}) => ({
    id: "r1",
    title: "T",
    targetRole: "R",
    tags: [],
    ...overrides,
  });

  test("snapshot without profile and without liveData falls back to empty profile", () => {
    const data = resolveResumeData(baseResume({ snapshot: {} }) as any);
    expect(data.profile).toBeDefined();
    expect(data.profile).toEqual(emptyResumeProfile);
  });

  test("snapshot without profile uses liveData profile when provided", () => {
    const liveProfile = { ...emptyResumeProfile, fullName: "Jane Doe" };
    const data = resolveResumeData(baseResume({ snapshot: { education: [] } }) as any, {
      profile: liveProfile,
      education: [],
      skills: [],
      projects: [],
      experience: [],
      certifications: [],
    });
    expect(data.profile.fullName).toBe("Jane Doe");
  });

  test("no snapshot and no liveData returns defined profile", () => {
    const data = resolveResumeData(baseResume({ sections: { summary: "hi" } }) as any);
    expect(data.profile).toBeDefined();
  });
});
