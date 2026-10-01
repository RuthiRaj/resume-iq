import { test, expect } from "@playwright/test";

/**
 * PR1-C1 regression: E2E mock data must be gated on the build-time
 * NEXT_PUBLIC_E2E / NEXT_PUBLIC_E2E_TEST_MODE flag.
 *
 * Proven here (flagged build):
 * - Window mocks ARE applied: /builder renders the injected mock profile.
 * - Mocks NEVER leak as real data: on /resumes under a Firestore outage the
 *   error state renders and no mock resume is shown.
 * - "Failed to load resumes" is the accepted non-mock outage outcome.
 * In a production build made WITHOUT the flag, the mock path can never
 * activate because isE2EMockEnabled() compiles to false.
 *
 * NOTE on flag-off: a runtime spec cannot unset a build-time inline, so the
 * flag-off case ("no mock code without the flag") cannot be tested here.
 * It is proven by the no-flag build grep check:
 *   grep -r "__E2E_MOCK" frontend/.next/static  ->  no matches.
 *
 * NOTE on /resumes: with the bypass user (a fake uid) Firestore listeners
 * cannot succeed in this environment, so route handling (fulfill or abort)
 * always settles to the denied shape. Tests below therefore never depend on
 * real Firestore state.
 */
test.describe("E2E mock gating (PR1-C1)", () => {
  test("unreachable Firestore without mocks: error state, no leaked mock resumes", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));

    // Authenticated (bypass) but no window mocks injected.
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });
    // Isolate from real Firestore: same empty fulfill the other suites use.
    // The bypass uid has no backend grants, so listeners settle to the
    // denied shape and the error state (not an empty list) must render.
    await page.route("**/firestore.googleapis.com/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents: [] }),
      });
    });
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    await expect(page.getByText("My Saved Resumes")).toBeVisible();
    await expect(page.getByText("Failed to load resumes")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Mock Gating Resume")).not.toBeVisible();
    await expect(page.getByText("No resumes found")).not.toBeVisible();
    expect(pageErrors.length).toBe(0);
  });

  test("flagged build: bypass + window mocks are applied", async ({ page }) => {
    // NOTE: NEXT_PUBLIC_E2E is baked into the *build* (not the worker
    // process env), so no process.env assertion — reaching the mock name
    // below proves the flag-gated path works in an E2E-flagged build.
    // /builder renders the mock profile regardless of Firestore outcome,
    // while /resumes (list) cannot succeed for the bypass uid in this
    // environment, so the mock-visible assertion lives here.
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_PROFILE__ = {
        fullName: "Mock Gating User",
        headline: "QA Engineer",
        email: "mock.gating@example.com",
        phone: "",
        location: "",
        website: "",
        linkedin: "",
        github: "",
        summary: "",
        targetRoles: [],
      };
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

    // Isolate from real Firestore: same empty fulfill the other suites use.
    await page.route("**/firestore.googleapis.com/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents: [] }),
      });
    });

    await page.goto("/builder", { waitUntil: "domcontentloaded" });
    await expect(page.locator("h1:has-text('Mock Gating User')")).toBeVisible({ timeout: 10000 });
  });

  test("denied Firestore: error state renders, mock data never shown", async ({ page }) => {
    // Even with mocks injected, a denied Firestore connection must surface
    // the error state — mock data must never render as if it were real.
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

    // Simulate Brave Shields / adblockers denying Firestore.
    await page.route("**/firestore.googleapis.com/**", (route) => route.abort("blockedbyclient"));

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");

    // The abort forces listener errors, so the error alert (not an empty
    // list, and never mock data) must render.
    await expect(page.getByText("Failed to load resumes")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Mock Gating Resume")).not.toBeVisible();
    await expect(page.getByText("No resumes found")).not.toBeVisible();
  });
});
