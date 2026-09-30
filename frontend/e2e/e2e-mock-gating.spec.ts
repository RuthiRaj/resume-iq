import { test, expect } from "@playwright/test";

/**
 * PR1-C1 regression: E2E mock data must be gated on the build-time
 * NEXT_PUBLIC_E2E / NEXT_PUBLIC_E2E_TEST_MODE flag.
 *
 * - Without mocks, /resumes renders the real empty state (no mock leak).
 * - With bypass + injected window mocks, the gated path applies them
 *   (proves the flag-gated path works in an E2E-flagged build).
 * In a production build made WITHOUT the flag, the second case can never
 * happen because isE2EMockEnabled() compiles to false.
 */
test.describe("E2E mock gating (PR1-C1)", () => {
  test("bypass without mocks: empty state, no leaked mock resumes", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));

    // Authenticated (bypass) but no window mocks injected: the real empty
    // state must render. (Without bypass the page redirects to login, so
    // bypass isolates exactly the "no mock leak" assertion.)
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    await expect(page.getByText("My Saved Resumes")).toBeVisible();
    await expect(page.getByText("No resumes found")).toBeVisible();
    expect(pageErrors.length).toBe(0);
  });

  test("flagged build: bypass + window mocks are applied", async ({ page }) => {
    // NOTE: NEXT_PUBLIC_E2E is baked into the *server* bundle env here
    // (playwright webServer), not the worker process env, so no
    // process.env assertion — reaching the mock title below proves the
    // flag-gated path works in an E2E-flagged build.
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_RESUMES__ = [
        {
          id: "mock-gating-1",
          title: "Mock Gating Resume",
          targetRole: "QA Engineer",
          targetCompany: "Acme",
          tags: [],
        },
      ];
    });

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByText("Mock Gating Resume")).toBeVisible({ timeout: 10000 });
  });
});
