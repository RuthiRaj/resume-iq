import { test, expect } from "@playwright/test";
import { filterResumes } from "@/lib/resume-filter";

/**
 * PR1-H7 regression: /resumes search filter must not crash on null/undefined
 * title, targetRole, or targetCompany.
 * Runs in Node (pure function, no page, no browser needed).
 */
test.describe("Resumes null-field filter (PR1-H7)", () => {
  const resumes = [
    { id: "null-1", title: null, targetRole: null, targetCompany: null, tags: [] },
    { id: "null-2", title: "Senior Frontend Engineer", targetRole: undefined, tags: [] },
    { id: "null-3", tags: [] },
  ] as any[];

  test("null fields never throw and empty query returns all items", () => {
    let result: any[];
    expect(() => {
      result = filterResumes(resumes as any, "");
    }).not.toThrow();
    expect(result!.map((r) => r.id).sort()).toEqual(["null-1", "null-2", "null-3"]);
  });

  test("null title / null targetRole / null targetCompany never throw on match", () => {
    let result: any[];
    expect(() => {
      result = filterResumes(resumes as any, "senior");
    }).not.toThrow();
    // Only the valid resume matches; null fields are treated as "".
    expect(result!.map((r) => r.id)).toEqual(["null-2"]);
  });

  test("normal match is case-insensitive across title, role, and company", () => {
    const rows = [
      { id: "a", title: "Staff Cloud Architect", targetRole: "Infra", targetCompany: "Acme" },
      { id: "b", title: "Designer", targetRole: "Senior Frontend Engineer", targetCompany: "Beta" },
      { id: "c", title: "PM", targetRole: "Growth", targetCompany: "Senior Capital" },
    ] as any[];
    expect(filterResumes(rows as any, "SENIOR").map((r) => r.id).sort()).toEqual(["b", "c"]);
    expect(filterResumes(rows as any, "acme").map((r) => r.id)).toEqual(["a"]);
    expect(filterResumes(rows as any, "zzz").map((r) => r.id)).toEqual([]);
  });
});
