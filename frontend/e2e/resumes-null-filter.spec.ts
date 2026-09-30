import { test, expect } from "@playwright/test";

/**
 * PR1-H7 regression: /resumes search filter must not crash on null/undefined
 * title, targetRole, or targetCompany.
 */
test.describe("Resumes null-field filter (PR1-H7)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_RESUMES__ = [
        { id: "null-1", title: null, targetRole: null, targetCompany: null, tags: [] },
        { id: "null-2", title: "Senior Frontend Engineer", targetRole: undefined, tags: [] },
        { id: "null-3", tags: [] },
      ];
    });
  });

  test("typing in search with null fields renders without page errors", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByText("My Saved Resumes")).toBeVisible({ timeout: 10000 });

    // Type a query — the old `(r.title ?? missing).toLowerCase()` path threw here.
    await page.getByPlaceholder(/search/i).fill("senior");
    await page.waitForTimeout(500);

    // Null-field resumes are treated as empty strings; the valid one still matches.
    await expect(page.getByText("Senior Frontend Engineer")).toBeVisible();
    expect(pageErrors.length).toBe(0);

    // Clearing the query shows all rows without crashing.
    await page.getByPlaceholder(/search/i).fill("");
    await page.waitForTimeout(500);
    expect(pageErrors.length).toBe(0);
  });
});
