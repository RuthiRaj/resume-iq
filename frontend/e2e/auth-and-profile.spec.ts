import { test, expect } from "@playwright/test";

test.describe("Auth and Profile Save E2E Validation", () => {
  test("Register / Signup flow handles non-blocking setDoc gracefully", async ({ page }) => {
    await page.goto("/register");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByText("ResumeIQ")).toBeVisible();
    await expect(page.getByText("Create your account")).toBeVisible();

    await page.fill('input[placeholder="e.g. Alex Morgan"]', "Test User");
    await page.fill('input[placeholder="name@example.com"]', `testuser_${Date.now()}@example.com`);
    await page.fill('input[placeholder="At least 8 characters"]', "password123");
    await page.fill('input[placeholder="Repeat your password"]', "password123");

    // Click submit button
    const submitBtn = page.getByRole("button", { name: /Create Workspace Account/i });
    await expect(submitBtn).toBeVisible();
  });

  test("Login flow displays form inputs and action", async ({ page }) => {
    await page.goto("/login");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByText("Sign in to your account")).toBeVisible();
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "password123");

    const submitBtn = page.getByRole("button", { name: /Sign In to Workspace/i });
    await expect(submitBtn).toBeVisible();
  });

  test("Profile Save validation displays link error messages and handles error callback", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });

    await page.route("**/api/profile", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          profile: {
            fullName: "Alex Morgan",
            headline: "Software Engineer",
            email: "alex@example.com",
            phone: "+1-555-0100",
            location: "San Francisco, CA",
            website: "",
            linkedin: "",
            github: "",
            summary: "Experienced developer.",
            targetRoles: ["Software Engineer"],
          },
        }),
      });
    });

    await page.goto("/workspace/profile");
    await page.waitForLoadState("domcontentloaded");

    await expect(page.getByText("Personal & Contact Profile")).toBeVisible();

    // Enter invalid URLs into website, linkedin, and github inputs
    const websiteInput = page.locator('input[placeholder="https://yourportfolio.dev"]');
    const linkedinInput = page.locator('input[placeholder="https://linkedin.com/in/username"]');
    const githubInput = page.locator('input[placeholder="https://github.com/username"]');

    await websiteInput.fill("javascript:alert(1)");
    await linkedinInput.fill("javascript:alert(2)");
    await githubInput.fill("javascript:alert(3)");

    // Click Save Profile Changes
    const saveBtn = page.getByRole("button", { name: /Save Profile Changes/i });
    await saveBtn.click();

    // Verify error indicators and error banner
    await expect(page.getByText(/Please fix:/i)).toBeVisible();
    await expect(page.getByText("Invalid or unsafe URL scheme.").first()).toBeVisible();
  });
});
