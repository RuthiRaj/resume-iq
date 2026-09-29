import { test, expect } from "@playwright/test";

test.describe("Builder Page Guard Reproduction & Verification", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_RESUMES__ = [
        {
          id: "res_no_sections_123",
          title: "Senior Cloud Architect - Master",
          targetRole: "Senior Cloud Architect",
          targetCompany: "Google Cloud",
          template: "modern",
          score: 88,
          tags: ["Production", "GCP"],
          lastEdited: "2026-09-28",
          // Intentionally omitting sections field to test missing sections guard
        },
        {
          id: "res_partial_sections_456",
          title: "AI Infrastructure Lead",
          targetRole: "AI Infrastructure Lead",
          template: "ats",
          score: 92,
          tags: ["AI"],
          lastEdited: "2026-09-28",
          sections: {
            summary: "Experienced AI Systems Engineer specializing in distributed training clusters.",
            // experiences and projects intentionally omitted
          },
        },
      ];
    });
  });

  test("1. Opens master resume with completely omitted sections field without crashing", async ({ page }) => {
    const pageErrors: Error[] = [];
    const consoleErrors: string[] = [];

    page.on("pageerror", (err) => {
      pageErrors.push(err);
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/builder?resumeId=res_no_sections_123");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // Verify header and page content render cleanly
    await expect(page.getByText("Resume Builder & Live Editor")).toBeVisible();

    // Verify no unhandled page errors
    expect(pageErrors.length).toBe(0);

    const bodyText = await page.innerText("body");
    expect(bodyText).not.toContain("Application error: a client-side exception has occurred");
    expect(bodyText).not.toContain("Cannot read properties of undefined");

    await page.screenshot({ path: "test-results/builder-guard-no-sections.png", fullPage: true });
  });

  test("2. Opens master resume with partial sections field without crashing", async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => {
      pageErrors.push(err);
    });

    await page.goto("/builder?resumeId=res_partial_sections_456");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    await expect(page.getByText("Resume Builder & Live Editor")).toBeVisible();
    expect(pageErrors.length).toBe(0);

    const bodyText = await page.innerText("body");
    expect(bodyText).not.toContain("Application error: a client-side exception has occurred");
    expect(bodyText).not.toContain("Cannot read properties of undefined");

    await page.screenshot({ path: "test-results/builder-guard-partial-sections.png", fullPage: true });
  });
});
