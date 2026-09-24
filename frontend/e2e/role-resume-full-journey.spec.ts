import { test, expect } from "@playwright/test";

test.describe("Full End-to-End Role Resume Creation & Targeted Editing Journey", () => {
  let currentVersion = 1;
  let currentSummary = "Experienced distributed systems architect specializing in high-scale cloud platforms.";
  let currentBullet = "Engineered distributed streaming pipeline processing 10M+ daily events.";

  test.beforeEach(async ({ page }) => {
    currentVersion = 1;
    currentSummary = "Experienced distributed systems architect specializing in high-scale cloud platforms.";
    currentBullet = "Engineered distributed streaming pipeline processing 10M+ daily events.";

    // Set auth bypass in localStorage
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });

    // Mock Profile API
    await page.route("**/api/profile", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          profile: {
            fullName: "Jane Doe",
            headline: "Senior Distributed Systems Engineer",
            email: "jane.doe@example.com",
            phone: "+1-555-019-2834",
            location: "San Francisco, CA",
            summary: currentSummary,
            targetRoles: ["Senior Distributed Systems Engineer"],
          },
        }),
      });
    });

    // Mock Generate Role Resume API
    await page.route("**/api/variants/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_full_journey_1",
          title: "Targeted Resume - Senior Distributed Systems Engineer",
          targetRole: "Senior Distributed Systems Engineer",
          targetCompany: "Stripe",
          version: 1,
          snapshot: {
            headline: "Senior Distributed Systems Engineer",
            summary: currentSummary,
            experience: [
              {
                id: "exp_1",
                role: "Staff Infrastructure Engineer",
                company: "Tech Corp",
                startDate: "2021",
                endDate: "Present",
                isCurrent: true,
                bullets: [currentBullet],
                technologies: ["Go", "Kubernetes", "Kafka"],
              },
            ],
            projects: [],
            skills: [{ name: "Distributed Systems" }, { name: "Go" }],
            education: [],
            certifications: [],
            achievements: [],
          },
        }),
      });
    });

    // Mock GET Variant API
    await page.route("**/api/variants/var_full_journey_1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_full_journey_1",
          isTargetedVariant: true,
          masterResumeId: "master_1",
          title: "Targeted Resume - Senior Distributed Systems Engineer",
          targetRole: "Senior Distributed Systems Engineer",
          targetCompany: "Stripe",
          version: currentVersion,
          baselineScore: 82,
          currentScore: 94,
          snapshot: {
            headline: "Senior Distributed Systems Engineer",
            summary: currentSummary,
            experience: [
              {
                id: "exp_1",
                role: "Staff Infrastructure Engineer",
                company: "Tech Corp",
                startDate: "2021",
                endDate: "Present",
                isCurrent: true,
                bullets: [currentBullet],
                technologies: ["Go", "Kubernetes", "Kafka"],
              },
            ],
            projects: [],
            skills: [{ name: "Distributed Systems" }, { name: "Go" }],
            education: [],
            certifications: [],
            achievements: [],
          },
          changeLedger: currentVersion > 1 ? [
            {
              id: "chg_1",
              actionType: "ManualEdit",
              status: "Applied",
              section: "Summary",
              requirementName: "Manual Executive Summary Edit",
              approvedText: currentSummary,
              timestamp: new Date().toISOString(),
            }
          ] : [],
          createdAt: "2026-09-22T00:00:00Z",
          updatedAt: new Date().toISOString(),
        }),
      });
    });

    // Mock Fit Comparison API
    await page.route("**/api/variants/var_full_journey_1/fit-comparison", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_full_journey_1",
          targetRole: "Senior Distributed Systems Engineer",
          targetCompany: "Stripe",
          baselineScore: 82,
          currentScore: 94,
          scoreDelta: 12,
          totalGapsResolved: 2,
          requirementProgressions: [],
        }),
      });
    });

    // Mock Apply Change API
    await page.route("**/api/variants/var_full_journey_1/apply-change", async (route) => {
      const postData = route.request().postDataJSON();
      currentVersion += 1;
      if (postData.section === "Summary") {
        currentSummary = postData.approvedBullet;
      } else if (postData.section === "Experience") {
        currentBullet = postData.approvedBullet;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_full_journey_1",
          newVersion: currentVersion,
          status: "Applied",
          appliedChange: {
            id: `chg_${currentVersion}`,
            actionType: postData.actionType || "ManualEdit",
            section: postData.section,
            approvedText: postData.approvedBullet,
            status: "Applied",
            timestamp: new Date().toISOString(),
          },
        }),
      });
    });

    // Mock AI Edit Proposals
    await page.route("**/api/variants/var_full_journey_1/ai-edit", async (route) => {
      const postData = route.request().postDataJSON();
      const instruction = postData.instruction.toLowerCase();

      if (instruction.includes("shorter")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            originalText: currentBullet,
            proposedText: "Built streaming pipeline handling 10M+ daily events.",
            diff: "- Engineered distributed streaming pipeline processing 10M+ daily events.\n+ Built streaming pipeline handling 10M+ daily events.",
            validation: {
              isValid: true,
              status: "Validated",
              unsupportedClaims: [],
            },
            requiresConfirmation: false,
            userAttestedFacts: [],
            targetItemId: postData.targetItemId,
            targetBulletIndex: postData.targetBulletIndex,
            version: currentVersion,
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            originalText: currentBullet,
            proposedText: "Engineered distributed Kafka streaming pipeline with Redis clustering processing 10M+ daily events.",
            diff: "- Engineered distributed streaming pipeline processing 10M+ daily events.\n+ Engineered distributed Kafka streaming pipeline with Redis clustering processing 10M+ daily events.",
            validation: {
              isValid: false,
              status: "RequiresConfirmation",
              unsupportedClaims: [{ claimText: "Redis clustering", claimType: "tool" }],
            },
            requiresConfirmation: true,
            userAttestedFacts: ["Redis clustering"],
            targetItemId: postData.targetItemId,
            targetBulletIndex: postData.targetBulletIndex,
            version: currentVersion,
          }),
        });
      }
    });

    // Mock Export PDF API
    await page.route("**/api/variants/var_full_journey_1/export/pdf*", async (route) => {
      const pdfHeader = "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF";
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: {
          "Content-Disposition": 'attachment; filename="Senior_Distributed_Systems_Engineer_v2.pdf"',
        },
        body: Buffer.from(pdfHeader),
      });
    });

    // Mock Export Text / Markdown / JSON API
    await page.route("**/api/variants/var_full_journey_1/export?*", async (route) => {
      const url = route.request().url();
      const fmt = url.includes("plain_text") ? "plain_text" : "markdown";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          variantId: "var_full_journey_1",
          version: currentVersion,
          format: fmt,
          content: fmt === "markdown"
            ? `# Jane Doe\n\n## Summary\n${currentSummary}\n\n## Experience\n- ${currentBullet}`
            : `JANE DOE\n\nSUMMARY\n${currentSummary}\n\nEXPERIENCE\n- ${currentBullet}`,
          exportedAt: new Date().toISOString(),
        }),
      });
    });
  });

  test("Primary Product Flow: Workspace -> Generate Role Resume -> Review -> Edit -> AI Proposal (Reject/Accept) -> Persist -> Export", async ({ page }) => {
    // 1. LOGIN / WORKSPACE - verify career data
    await page.goto("/workspace/profile", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Personal & Contact Profile")).toBeVisible();
    await expect(page.getByPlaceholder("e.g. Alex Morgan")).toBeVisible();
    await expect(page.getByRole("button", { name: /Save Profile Changes/i })).toBeVisible();

    // 2. RESUMES - Open Saved Resumes page
    await page.goto("/resumes", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("My Saved Resumes")).toBeVisible();

    // 3. Generate Role Resume - Click trigger button & enter target role
    const generateRoleBtn = page.getByRole("button", { name: /AI Generate Resume/i }).first();
    await expect(generateRoleBtn).toBeVisible();
    await generateRoleBtn.click();

    // Fill generate modal inputs
    await expect(page.getByText("AI Generate Role-Targeted Resume")).toBeVisible();
    const roleInput = page.locator('input[placeholder="e.g. Senior Distributed Systems Engineer"]');
    await roleInput.fill("Senior Distributed Systems Engineer");

    const companyInput = page.locator('input[placeholder="e.g. Stripe, OpenAI, Google"]');
    await companyInput.fill("Stripe");

    // Click Generate Targeted Resume
    const submitGenBtn = page.getByRole("button", { name: /Generate Targeted Resume/i });
    await submitGenBtn.click();

    // 4. TARGETED RESUME OPENS - verify metadata and content
    await page.waitForURL("**/resumes/targeted/var_full_journey_1");
    await expect(page.getByText("Targeted Resume - Senior Distributed Systems Engineer").first()).toBeVisible();
    await expect(page.getByText("Role:").first()).toBeVisible();
    await expect(page.getByText("Company: Stripe")).toBeVisible();
    await expect(page.getByText("v1", { exact: true })).toBeVisible();
    await expect(page.getByText(currentSummary)).toBeVisible();

    // 5. MANUAL EDIT - Edit summary manually and save
    const editSummaryBtn = page.getByTitle("Manually edit executive summary");
    await editSummaryBtn.click();
    await expect(page.getByText("Manual Content Edit")).toBeVisible();

    const summaryTextarea = page.locator("textarea");
    const updatedSummaryText = "Principal distributed systems architect leading high-scale cloud platforms.";
    await summaryTextarea.fill(updatedSummaryText);

    const saveManualEditBtn = page.getByRole("button", { name: /Save & Increment to v2/i });
    await saveManualEditBtn.click();

    // Verify manual edit toast and updated text
    await expect(page.getByText("Manual edit saved!")).toBeVisible();
    await expect(page.getByText("v2", { exact: true })).toBeVisible();

    // 6. REFRESH - Verify edit persists across page reload
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByText(updatedSummaryText)).toBeVisible();
    await expect(page.getByText("v2", { exact: true })).toBeVisible();

    // 7. REQUEST AI EDIT & REJECT PROPOSAL
    const aiRefineBtn = page.getByTitle("AI rewrite / refine bullet").first();
    await aiRefineBtn.click();
    await expect(page.getByText("AI Bullet & Section Editor")).toBeVisible();

    const aiInstructionInput = page.locator('input[placeholder*="Make shorter"]');
    await aiInstructionInput.fill("Make shorter");

    const proposeBtn = page.getByRole("button", { name: /Propose Edit/i });
    await proposeBtn.click();

    // Verify AI proposal card appears with diff
    await expect(page.getByText("AI Edit Proposal")).toBeVisible();
    await expect(page.getByText("Fact Validated")).toBeVisible();
    await expect(page.getByText("Built streaming pipeline handling 10M+ daily events.", { exact: true })).toBeVisible();

    // Reject proposal
    const rejectBtn = page.getByRole("button", { name: /Reject Proposal/i });
    await rejectBtn.click();
    await expect(page.getByText("AI Bullet & Section Editor")).not.toBeVisible();

    // Verify resume text did NOT change after rejection
    await expect(page.getByText(currentBullet).first()).toBeVisible();

    // 8. REQUEST ANOTHER AI EDIT WITH USER ATTESTATION & ACCEPT
    await aiRefineBtn.click();
    await expect(page.getByText("AI Bullet & Section Editor")).toBeVisible();
    await aiInstructionInput.fill("Add Redis clustering details");
    await proposeBtn.click();

    // Verify proposal with ungrounded fact requires attestation
    await expect(page.getByText("Requires Confirmation")).toBeVisible();
    await expect(page.getByText("New User-Attested Facts Detected")).toBeVisible();
    await expect(page.getByText("Redis clustering").first()).toBeVisible();

    // Accept button should be disabled until attestation checked
    const acceptBtn = page.getByRole("button", { name: /Accept & Save v3/i });
    await expect(acceptBtn).toBeDisabled();

    // Check attestation checkbox
    const attestationCheckbox = page.locator('input[type="checkbox"]');
    await attestationCheckbox.check();
    await expect(acceptBtn).toBeEnabled();

    // Accept and save proposal
    await acceptBtn.click();
    await expect(page.getByText("AI proposal accepted and applied!")).toBeVisible();
    await expect(page.getByText("v3", { exact: true })).toBeVisible();

    // 9. EXPORT VERIFICATION - Open Export modal and verify ATS PDF / Markdown
    const exportBtn = page.getByRole("button", { name: /Export/i });
    await exportBtn.click();
    await expect(page.getByText("Export Targeted Resume")).toBeVisible();

    // Switch to Markdown format tab
    const markdownTab = page.getByRole("button", { name: /Markdown/i });
    await markdownTab.click();
    await expect(page.getByText("Format: markdown")).toBeVisible();
    await expect(page.locator("textarea[readonly]")).toContainText("Principal distributed systems architect");

    // Switch to Plain Text format tab
    const textTab = page.getByRole("button", { name: /Plain Text/i });
    await textTab.click();
    await expect(page.getByText("Format: plain_text")).toBeVisible();

    // Switch to ATS PDF tab and download
    const pdfTab = page.getByRole("button", { name: /ATS PDF/i });
    await pdfTab.click();
    const downloadPdfBtn = page.getByRole("button", { name: /Download ATS PDF/i }).first();
    await expect(downloadPdfBtn).toBeVisible({ timeout: 10000 });

    const downloadPromise = page.waitForEvent("download");
    await downloadPdfBtn.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain(".pdf");
  });
});
