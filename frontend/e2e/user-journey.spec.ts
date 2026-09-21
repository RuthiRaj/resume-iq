import { test, expect } from "@playwright/test";

test.describe("Phase 6.0-E Production User Journey E2E Suite", () => {
  test.beforeEach(async ({ page }) => {
    // Inject test-safe auth bypass token in localStorage for authenticated app routes
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });

    // Intercept auth session & API routes for deterministic E2E execution
    await page.route("**/api/resumes/ingest", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          draft: {
            ingestionId: "ingest_e2e_999",
            documentName: "Jane_Doe_Resume.pdf",
            fileSizeBytes: 45120,
            status: "Parsed",
            rawTextSnippet: "Jane Doe - Senior Full Stack Engineer. 8+ years experience in Python & React.",
            parsedData: {
              profile: {
                fullName: "Jane Doe",
                headline: "Senior Full Stack Engineer",
                email: "jane.doe@example.com",
                phone: "+1-555-019-2834",
                location: "San Francisco, CA",
                website: "https://janedoe.dev",
                linkedin: "https://linkedin.com/in/janedoe",
                github: "https://github.com/janedoe",
                summary: "Passionate Full Stack Engineer with expertise in Python, React, and cloud architectures.",
                targetRoles: ["Senior Full Stack Engineer"],
              },
              evidence: {
                experience: [
                  {
                    id: "exp_1",
                    role: "Staff Software Engineer",
                    company: "Tech Corp",
                    location: "San Francisco, CA",
                    startDate: "2021",
                    endDate: "Present",
                    bullets: ["Engineered distributed microservices processing 10M+ daily events."],
                    technologies: ["Python", "React", "PostgreSQL"],
                  },
                ],
                education: [
                  {
                    degree: "B.S. Computer Science",
                    institution: "Stanford University",
                    fieldOfStudy: "Computer Science",
                  },
                ],
                skills: [{ name: "Python" }, { name: "React" }, { name: "PostgreSQL" }],
                projects: [
                  {
                    id: "proj_1",
                    title: "Distributed Task Processor",
                    role: "Creator",
                    description: "High-throughput asynchronous job queue.",
                    highlights: ["Achieved 99.99% uptime."],
                  },
                ],
                certifications: [],
              },
            },
          },
        }),
      });
    });

    await page.route("**/api/resumes/ingest/ingest_e2e_999/confirm", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          message: "Career evidence confirmed and hydrated into master workspace.",
        }),
      });
    });

    await page.route("**/api/variants/var_e2e_test", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_e2e_test",
          isTargetedVariant: true,
          masterResumeId: "master_1",
          title: "Targeted Resume - Lead Backend Engineer",
          targetRole: "Lead Backend Engineer",
          targetCompany: "Stripe",
          version: 2,
          baselineScore: 78,
          currentScore: 92,
          snapshot: {
            profile: { headline: "Lead Backend Engineer" },
            summary: "Experienced backend architect specializing in payment processing infrastructure.",
            experience: [
              {
                id: "exp_1",
                role: "Staff Software Engineer",
                company: "Tech Corp",
                bullets: ["Engineered distributed payment pipeline processing 10M+ daily events."],
              },
            ],
            projects: [],
            skills: [{ name: "Python" }, { name: "PostgreSQL" }],
            education: [],
            certifications: [],
          },
          changeLedger: [],
          createdAt: "2026-09-08T10:00:00Z",
          updatedAt: "2026-09-08T11:00:00Z",
        }),
      });
    });

    await page.route("**/api/variants/var_e2e_test/export/pdf*", async (route) => {
      // Mock valid %PDF-1.4 binary response
      const pdfHeader = "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF";
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: {
          "Content-Disposition": 'attachment; filename="Lead_Backend_Engineer_v2.pdf"',
        },
        body: Buffer.from(pdfHeader),
      });
    });
  });

  test("Step 1: Dashboard Onboarding Banner & Navigation", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("domcontentloaded");

    // Check dashboard heading
    const mainHeading = page.locator("h1");
    await expect(mainHeading).toContainText("Good morning");

    // Check onboarding card elements or links
    const documentsLink = page.locator('a[href="/workspace/documents"]').first();
    await expect(documentsLink).toBeVisible();
  });

  test("Step 2-5: Ingestion UI, Evidence Review, Confirmation, Workspace Navigation", async ({ page }) => {
    page.on("console", (msg) => console.log("PAGE LOG:", msg.text()));
    page.on("pageerror", (err) => console.log("PAGE ERROR:", err));

    // Mock ingestion API route
    await page.route("**/api/resumes/ingest", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          draft: {
            ingestionId: "draft_test_123",
            documentName: "Jane_Doe_Resume.pdf",
            fileSizeBytes: 12345,
            rawTextSnippet: "Mock extracted resume text",
            parsedData: {
              profile: {
                fullName: "Jane Doe",
                headline: "Senior Software Engineer",
                email: "jane@example.com",
                phone: "+1-555-0199",
                location: "San Francisco, CA",
                website: "https://janedoe.dev",
                linkedin: "https://linkedin.com/in/janedoe",
                github: "https://github.com/janedoe",
                summary: "Experienced software engineer passionate about SaaS applications.",
                targetRoles: ["Senior Software Engineer"],
              },
              evidence: {
                experience: [
                  {
                    id: "exp-1",
                    company: "Tech Corp",
                    role: "Senior Engineer",
                    startDate: "2021",
                    endDate: "Present",
                    bullets: ["Led microservices architecture."],
                    technologies: ["TypeScript", "Node.js"],
                  },
                ],
                education: [
                  {
                    institution: "Tech University",
                    degree: "B.S. Computer Science",
                    fieldOfStudy: "Computer Science",
                  },
                ],
                skills: [
                  { name: "TypeScript", category: "Languages" },
                  { name: "React", category: "Frontend" },
                ],
                projects: [],
                certifications: [],
              },
            },
          },
        }),
      });
    });

    await page.route("**/api/resumes/ingest/*/confirm", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "success",
          message: "Career evidence successfully imported into master workspace.",
        }),
      });
    });

    await page.goto("/workspace/documents");
    await page.waitForLoadState("domcontentloaded");

    // Click Upload Document button
    const uploadBtn = page.getByRole("button", { name: /Upload Document/i }).first();
    await expect(uploadBtn).toBeVisible();
    await uploadBtn.click();

    // Attach mock resume file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "Jane_Doe_Resume.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 Mock Candidate Resume Buffer"),
    });

    // Submit ingestion
    const submitBtn = page.getByRole("button", { name: /Upload & Parse/i });
    await submitBtn.click();

    // Verify Review Modal opens with parsed data
    await expect(page.getByText("Review Extracted Resume Evidence")).toBeVisible();
    await expect(page.locator('input[value="Jane Doe"]')).toBeVisible();

    // Confirm Ingestion
    const confirmBtn = page.getByRole("button", { name: /Confirm & Import to Master Workspace/i });
    await confirmBtn.click();

    // Verify Success CTA buttons appear
    await expect(page.getByText("Import Successful!")).toBeVisible();
    const workspaceCta = page.getByRole("button", { name: /View Master Workspace/i });
    await expect(workspaceCta).toBeVisible();
    const auditCta = page.getByRole("button", { name: /Run ATS Audit/i });
    await expect(auditCta).toBeVisible();
  });

  test("Step 6-8: Targeted Resume Workspace, Live PDF Preview & Export Download", async ({ page }) => {
    await page.goto("/resumes/targeted/var_e2e_test");
    await page.waitForLoadState("domcontentloaded");

    // Check title
    await expect(page.getByText("Targeted Resume - Lead Backend Engineer").first()).toBeVisible();

    // Open Export Modal
    const exportBtn = page.getByRole("button", { name: /Export/i });
    await exportBtn.click();

    // Verify Export Modal Title
    await expect(page.getByText("Export Targeted Resume")).toBeVisible();

    // Select ATS PDF tab if not already selected
    const pdfTab = page.getByRole("button", { name: "ATS PDF", exact: true });
    await pdfTab.click();

    // Verify Download ATS PDF button exists
    const downloadPdfBtn = page.getByRole("button", { name: /Download ATS PDF/i }).first();
    await expect(downloadPdfBtn).toBeVisible();

    // Listen for download event
    const downloadPromise = page.waitForEvent("download");
    await downloadPdfBtn.click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain("Lead_Backend_Engineer_v2.pdf");
  });
});
