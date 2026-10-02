import { test, expect } from "@playwright/test";

/**
 * PR1-M5 regression:
 * (a) Builder must not freeze a stale first-render snapshot — state
 * initializes to safe defaults and the sync effect populates it when the
 * async resume arrives.
 * (b) Toast timers must not fire setState after unmount.
 */
test.describe("Builder init + toast cleanup (PR1-M5)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_RESUMES__ = [
        {
          id: "mock-init-1",
          title: "Init Sync Resume",
          targetRole: "Backend Engineer",
          targetCompany: "Acme",
          jobDescription: "",
          template: "modern",
          sections: { summary: "Init summary", experiences: [], projects: [] },
          tags: [],
        },
      ];
    });
  });

  test("async resume populates builder fields (no stale init)", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));

    await page.goto("/builder?resumeId=mock-init-1");
    await page.waitForLoadState("domcontentloaded");

    // Effect must populate the title from the async-loaded resume,
    // not the "Tailored Resume" default frozen at first render.
    await expect(page.locator('input[value="Init Sync Resume"]')).toBeVisible({ timeout: 10000 });
    expect(pageErrors.length).toBe(0);
  });

  test("unmounting builder quickly causes no page errors (timer cleanup)", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));

    await page.goto("/builder?resumeId=mock-init-1");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.locator('input[value="Init Sync Resume"]')).toBeVisible({ timeout: 10000 });

    // Navigate away immediately — pending toast/timeout callbacks must be cleaned up.
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(4000);
    expect(pageErrors.length).toBe(0);
  });
});
