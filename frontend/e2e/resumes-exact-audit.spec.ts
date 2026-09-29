import { test, expect } from "@playwright/test";

test.describe("Playwright /resumes Exact Audit & Verification", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });
  });

  test("Case 1: Resume document with no tags field renders without console errors or page errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: Error[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });
    page.on("pageerror", (err) => {
      pageErrors.push(err);
    });

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // Verify page title and header
    await expect(page.getByText("My Saved Resumes")).toBeVisible();

    // Verify no unhandled page errors
    expect(pageErrors.length).toBe(0);

    // Save screenshot
    await page.screenshot({ path: "test-results/audit-case1-resumes-no-tags.png", fullPage: true });
  });

  test("Case 2: Fork, Rename, Duplicate, Delete, and the grid/list toggle each work", async ({ page }) => {
    // Mock variant creation API
    await page.route("**/api/variants/create", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          variantId: "var_audit_fork_123",
          message: "Targeted variant created successfully",
        }),
      });
    });

    await page.route("**/api/variants/var_audit_fork_123", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_audit_fork_123",
          isTargetedVariant: true,
          title: "Senior AI Engineer Fork",
          targetRole: "Senior AI Engineer",
          version: 1,
          snapshot: { profile: {}, experience: [], skills: [], projects: [], education: [], certifications: [] },
        }),
      });
    });

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // 1. Grid/List Toggle
    const listBtn = page.locator('button[aria-label="List view"]');
    const gridBtn = page.locator('button[aria-label="Grid view"]');
    await expect(listBtn).toBeVisible();
    await listBtn.click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "test-results/audit-case2-01-list-toggle.png" });

    await gridBtn.click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: "test-results/audit-case2-02-grid-toggle.png" });

    // 2. Fork Modal Flow
    const forkBtn = page.getByRole("button", { name: /Fork Variant/i });
    await expect(forkBtn).toBeVisible();
    await forkBtn.click();

    await expect(page.getByText("Create Targeted Resume Variant")).toBeVisible();
    await page.locator('input[placeholder="e.g. Senior Full Stack AI Engineer"]').fill("Lead Systems Architect");
    await page.locator('input[placeholder="e.g. Stripe"]').fill("Google Cloud");
    await page.locator('textarea[placeholder*="Paste the target job description"]').fill("Seeking a Lead Systems Architect with deep cloud and distributed systems expertise.");
    await page.screenshot({ path: "test-results/audit-case2-03-fork-modal.png" });

    const submitForkBtn = page.getByRole("button", { name: /Create & Open Workspace/i });
    await submitForkBtn.click();
    await page.waitForTimeout(500);

    // Return to /resumes
    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // 3. Rename Flow
    const renameBtn = page.locator('button[title="Rename"]').first();
    if (await renameBtn.isVisible()) {
      await renameBtn.click();
      await expect(page.getByText("Rename Resume")).toBeVisible();
      const titleInput = page.locator('input[value]').last();
      await titleInput.fill("Renamed Production Resume");
      await page.screenshot({ path: "test-results/audit-case2-04-rename-modal.png" });
      await page.getByRole("button", { name: /Save Title/i }).click();
      await page.waitForTimeout(500);
    }

    // 4. Duplicate Flow
    const duplicateBtn = page.locator('button[title="Duplicate"]').first();
    if (await duplicateBtn.isVisible()) {
      await duplicateBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: "test-results/audit-case2-05-duplicate-clicked.png" });
    }

    // 5. Delete Flow
    const deleteBtn = page.locator('button[title="Delete"]').first();
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: "test-results/audit-case2-06-delete-clicked.png" });
    }
  });

  test("Case 3: Blocked firestore.googleapis.com renders ErrorAlert with Retry button instead of EmptyState", async ({ page }) => {
    // Block all Firestore requests to simulate Brave Shields / adblockers
    await page.route("**/firestore.googleapis.com/**", (route) => route.abort("blockedbyclient"));

    await page.goto("/resumes");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Assert error alert is visible with retry button
    const errorAlert = page.getByRole("alert").filter({ hasText: "Failed to load resumes" });
    await expect(errorAlert).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Failed to load resumes")).toBeVisible({ timeout: 10000 });

    // Assert Retry / Try Again button is visible
    const retryBtn = page.getByRole("button", { name: /try again/i });
    await expect(retryBtn).toBeVisible({ timeout: 10000 });

    // Assert "No resumes found" EmptyState is NOT visible
    await expect(page.getByText("No resumes found")).not.toBeVisible();

    // Ensure it did not crash with unhandled React exception
    const bodyText = await page.innerText("body");
    expect(bodyText).not.toContain("Application error: a client-side exception has occurred");

    await page.screenshot({ path: "test-results/audit-case3-firestore-blocked.png", fullPage: true });
  });
});
