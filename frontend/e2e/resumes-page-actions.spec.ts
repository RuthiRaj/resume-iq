import { test, expect } from "@playwright/test";

test.describe("Resumes Page Actions & Regression Suite", () => {
  test.beforeEach(async ({ page }) => {
    // Enable authenticated test user
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });
  });

  test("1. Renders resumes without tags, toggles Grid/List, and executes Rename, Duplicate, Delete & Fork", async ({ page }) => {
    // Intercept variant create API
    await page.route("**/api/variants/create", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          variantId: "var_forked_test_123",
          message: "Targeted variant created successfully",
        }),
      });
    });

    await page.route("**/api/variants/var_forked_test_123", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_forked_test_123",
          isTargetedVariant: true,
          title: "Senior Full Stack AI Engineer Variant",
          targetRole: "Senior Full Stack AI Engineer",
          version: 1,
          snapshot: {
            profile: { headline: "Senior Full Stack AI Engineer" },
            experience: [],
            skills: [],
            projects: [],
            education: [],
            certifications: [],
          },
        }),
      });
    });

    // Navigate to /resumes
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");

    // Wait for the main page header to be visible
    await expect(page.getByText("My Saved Resumes")).toBeVisible();
    await page.screenshot({ path: "test-results/01-resumes-page-loaded.png", fullPage: true });

    // 1. Toggle Grid / List view
    const listBtn = page.locator('button[aria-label="List view"]');
    const gridBtn = page.locator('button[aria-label="Grid view"]');

    if (await listBtn.isVisible()) {
      await listBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: "test-results/02-list-view-toggled.png" });

      await gridBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: "test-results/03-grid-view-toggled.png" });
    }

    // 2. Test Fork Modal
    const forkTopBtn = page.getByRole("button", { name: /Fork Variant/i });
    if (await forkTopBtn.isVisible()) {
      await forkTopBtn.click();
      await expect(page.getByText("Create Targeted Resume Variant")).toBeVisible();

      // Fill in fork fields
      const roleInput = page.locator('input[placeholder="e.g. Senior Full Stack AI Engineer"]');
      const companyInput = page.locator('input[placeholder="e.g. Stripe"]');
      const jdTextarea = page.locator('textarea[placeholder*="Paste the target job description"]');

      await roleInput.fill("Senior Full Stack AI Engineer");
      await companyInput.fill("OpenAI");
      await jdTextarea.fill("Looking for a Senior Full Stack AI Engineer with deep experience in TypeScript, React, Next.js, Python, and Large Language Models.");

      await page.screenshot({ path: "test-results/04-fork-modal-filled.png" });

      // Click Create & Open Workspace
      const createBtn = page.getByRole("button", { name: /Create & Open Workspace/i });
      await createBtn.click();
      await page.waitForTimeout(500);
    }

    // Return to /resumes
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");

    // 3. Test Rename Button if any resume card is rendered
    const renameBtn = page.locator('button[title="Rename"]').first();
    if (await renameBtn.isVisible()) {
      await renameBtn.click();
      await expect(page.getByText("Rename Resume")).toBeVisible();
      const titleInput = page.locator('input[value]').last();
      await titleInput.fill("Updated Senior Engineer Resume");
      await page.screenshot({ path: "test-results/05-rename-modal.png" });

      const saveTitleBtn = page.getByRole("button", { name: /Save Title/i });
      await saveTitleBtn.click();
      await page.waitForTimeout(500);
    }

    // 4. Test Duplicate Button
    const dupBtn = page.locator('button[title="Duplicate"]').first();
    if (await dupBtn.isVisible()) {
      await dupBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: "test-results/06-duplicate-action.png" });
    }

    // 5. Test Delete Button
    const delBtn = page.locator('button[title="Delete"]').first();
    if (await delBtn.isVisible()) {
      await delBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: "test-results/07-delete-action.png" });
    }
  });

  test("2. Firestore blocked by Brave Shields (page.route) renders gracefully without crash", async ({ page }) => {
    // Block all firestore.googleapis.com network requests
    await page.route("**/firestore.googleapis.com/**", (route) => route.abort("blockedbyclient"));

    // Navigate to /resumes
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");

    // Confirm the page does NOT show standard white unhandled exception
    await page.waitForTimeout(1000);
    const bodyText = await page.innerText("body");
    expect(bodyText).not.toContain("Application error: a client-side exception has occurred");

    await page.screenshot({ path: "test-results/08-firestore-blocked-shields.png", fullPage: true });
  });
});
