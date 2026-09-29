import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

async function extractTextFromPdfBuffer(buffer: Buffer): Promise<string> {
  const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
  const doc = await pdfjs.getDocument({ data: new Uint8Array(buffer) }).promise;
  let fullText = "";
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const content = await page.getTextContent();
    const strings = content.items.map((item: any) => item.str);
    fullText += strings.join(" ") + "\n";
  }
  return fullText;
}

const mockCandidateEvidence = {
  profile: {
    fullName: "Alexandra Chen",
    headline: "Staff Cloud Systems Architect & Distributed Systems Specialist",
    email: "alexandra.chen@example.com",
    phone: "+1 (555) 839-2041",
    location: "San Francisco, CA",
    website: "https://alexandrachen.dev",
    linkedin: "https://linkedin.com/in/alexandrachen",
    github: "https://github.com/alexandrachen",
    summary:
      "Accomplished Cloud Systems Architect with 8+ years designing high-throughput distributed microservices, multi-region Kubernetes clusters, and low-latency data pipelines handling 100M+ daily events.",
    targetRoles: ["Staff Cloud Architect", "Principal Distributed Systems Engineer"],
  },
  experience: [
    {
      id: "exp_cloud_1",
      company: "Apex Cloud Infrastructure",
      role: "Staff Cloud Architect",
      location: "San Francisco, CA",
      startDate: "2022-01",
      endDate: "Present",
      isCurrent: true,
      bullets: [
        "Architected multi-region Kubernetes control plane reducing cluster failover latency from 4.2 minutes to 180 milliseconds.",
        "Engineered zero-trust service mesh routing 120M+ API requests per day with 99.999% availability SLA.",
        "Spearheaded cloud cost governance framework saving $1.4M annually across AWS and GCP infrastructure.",
      ],
      technologies: ["Kubernetes", "Go", "AWS", "Terraform", "gRPC", "Istio"],
    },
    {
      id: "exp_cloud_2",
      company: "HyperScale Networks",
      role: "Senior Distributed Systems Engineer",
      location: "Palo Alto, CA",
      startDate: "2019-03",
      endDate: "2021-12",
      isCurrent: false,
      bullets: [
        "Led core team of 6 engineers developing distributed transaction coordinator with Raft consensus protocol.",
        "Optimized Redis cache invalidation layer, lowering P99 response times from 85ms to 12ms under peak load.",
      ],
      technologies: ["Python", "Rust", "Redis", "Kafka", "PostgreSQL", "Docker"],
    },
  ],
  education: [
    {
      id: "edu_1",
      institution: "Stanford University",
      degree: "Master of Science",
      fieldOfStudy: "Computer Science (Distributed Systems)",
      startDate: "2017-09",
      endDate: "2019-06",
      grade: "3.94 / 4.0 GPA",
    },
  ],
  skills: [
    { id: "sk_1", name: "Distributed Systems", category: "Domain", proficiency: "Expert" },
    { id: "sk_2", name: "Kubernetes & Containers", category: "Cloud & DevOps", proficiency: "Expert" },
    { id: "sk_3", name: "Go (Golang)", category: "Languages", proficiency: "Expert" },
    { id: "sk_4", name: "Python & FastAPI", category: "Frameworks & Libraries", proficiency: "Advanced" },
    { id: "sk_5", name: "AWS & Multi-Cloud", category: "Cloud & DevOps", proficiency: "Expert" },
    { id: "sk_6", name: "Terraform & IaC", category: "Tools", proficiency: "Advanced" },
  ],
  projects: [
    {
      id: "proj_1",
      title: "RaftKv Distributed Key-Value Store",
      role: "Lead Architect & Creator",
      startDate: "2023-01",
      endDate: "2023-06",
      description: "Fault-tolerant linearized key-value storage engine implementing full Raft consensus and snapshotting.",
      highlights: [
        "Implemented linearizable read lease protocol sustaining 45,000 writes/sec per cluster shard.",
        "Integrated dynamic node rebalancing with automatic zero-downtime membership changes.",
      ],
      techStack: ["Go", "Raft", "gRPC", "Protobuf", "Docker"],
    },
  ],
  certifications: [
    {
      id: "cert_1",
      title: "AWS Certified Solutions Architect — Professional",
      issuer: "Amazon Web Services (AWS)",
      issueDate: "2023-05",
    },
  ],
};

test.describe("Bug A: Resume Print / PDF Export Quality & Chrome Suppression Suite", () => {
  test.beforeEach(async ({ page }) => {
    // 1. Authenticate with e2e bypass
    await page.addInitScript((mockData) => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      (window as any).__E2E_MOCK_PROFILE__ = mockData.profile;
      (window as any).__E2E_MOCK_EXPERIENCE__ = mockData.experience;
      (window as any).__E2E_MOCK_EDUCATION__ = mockData.education;
      (window as any).__E2E_MOCK_SKILLS__ = mockData.skills;
      (window as any).__E2E_MOCK_PROJECTS__ = mockData.projects;
      (window as any).__E2E_MOCK_CERTIFICATIONS__ = mockData.certifications;
    }, mockCandidateEvidence);

    // Mock Firestore REST endpoints if invoked
    await page.route("**/firestore.googleapis.com/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents: [] }),
      });
    });
  });

  test("Print mode cleanly renders ONLY the resume, hides all app chrome, and produces text-selectable PDF", async ({
    page,
  }) => {
    const targetDirs = [
      path.resolve(__dirname, "../test-results/print-export"),
      "C:\\Users\\gosul\\.gemini\\antigravity\\brain\\7f7638eb-8698-4666-af73-e8d95afc5bd1",
    ];
    for (const dir of targetDirs) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Navigate to Builder
    await page.goto("/builder", { waitUntil: "networkidle" });

    // Wait for the Builder page and preview renderer to be visible
    await expect(page.locator("h1:has-text('Resume Builder')")).toBeVisible({ timeout: 10000 });

    // Ensure preview is rendered
    await page.waitForSelector("h1:has-text('Alexandra Chen')", { timeout: 10000 });

    // --- 1. Screen Media Verification (Sanity Check) ---
    // In screen media, app chrome is visible
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByText("Search workspace...")).toBeVisible();
    await expect(page.locator("h1:has-text('Resume Builder & Live Editor')")).toBeVisible();
    await expect(page.getByRole("button", { name: /Print \/ Export PDF/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Save Resume/i })).toBeVisible();

    // Take screen screenshot
    for (const dir of targetDirs) {
      await page.screenshot({ path: path.join(dir, "builder-screen-view.png"), fullPage: true });
    }

    // --- 2. Print Media Emulation ---
    await page.emulateMedia({ media: "print" });

    // --- 3. Assertions in Print Media: All App Chrome MUST BE HIDDEN ---
    // (a) App Navigation Header
    await expect(page.locator("header")).toBeHidden();
    await expect(page.getByText("Search workspace...")).toBeHidden();

    // (b) App Sidebar
    await expect(page.locator("aside")).toBeHidden();

    // (c) Top Header Bar & Action Buttons
    await expect(page.locator("h1:has-text('Resume Builder & Live Editor')")).toBeHidden();
    await expect(page.getByRole("button", { name: /Print \/ Export PDF/i })).toBeHidden();
    await expect(page.getByRole("button", { name: /Save Resume/i })).toBeHidden();
    await expect(page.getByRole("button", { name: /AI Generate Role Resume/i })).toBeHidden();

    // (d) Editor controls sidebar, tabs, form fields, and "AI Tailor" button
    await expect(page.locator("input[placeholder*='Senior Frontend']")).toBeHidden();
    await expect(page.getByText("AI Tailor")).toBeHidden();
    await expect(page.getByText("Resume Title")).toBeHidden();
    await expect(page.getByText("Target Role")).toBeHidden();

    // (e) Live preview decorative banner and ATS Score tag
    await expect(page.getByText("LIVE RESUME PREVIEW • A4 SCALE")).toBeHidden();
    await expect(page.getByText("95% ATS Score")).toBeHidden();

    // --- 4. Assertions in Print Media: Resume Sections MUST ALL BE VISIBLE ---
    // (a) Header Contact Details
    await expect(page.locator("h1:has-text('Alexandra Chen')")).toBeVisible();
    await expect(page.getByText("Staff Cloud Systems Architect")).toBeVisible();
    await expect(page.getByText("alexandra.chen@example.com")).toBeVisible();
    await expect(page.getByText("San Francisco, CA").first()).toBeVisible();

    // (b) Executive Summary
    await expect(page.getByRole("heading", { name: /Executive Summary/i })).toBeVisible();
    await expect(page.getByText("Accomplished Cloud Systems Architect with 8+ years")).toBeVisible();

    // (c) Work Experience
    await expect(page.getByRole("heading", { name: /Work Experience/i })).toBeVisible();
    await expect(page.getByText("Apex Cloud Infrastructure")).toBeVisible();
    await expect(page.getByText("HyperScale Networks")).toBeVisible();
    await expect(page.getByText("Architected multi-region Kubernetes control plane")).toBeVisible();

    // (d) Featured Projects
    await expect(page.getByRole("heading", { name: /Featured Projects/i })).toBeVisible();
    await expect(page.getByText("RaftKv Distributed Key-Value Store")).toBeVisible();

    // (e) Technical Skills
    await expect(page.getByRole("heading", { name: /Technical Skills/i })).toBeVisible();
    await expect(page.getByText("Kubernetes & Containers")).toBeVisible();

    // (f) Education
    await expect(page.getByRole("heading", { name: /Education/i })).toBeVisible();
    await expect(page.getByText("Stanford University")).toBeVisible();

    // (g) Certifications
    await expect(page.getByRole("heading", { name: /Certifications/i })).toBeVisible();
    await expect(page.getByText("AWS Certified Solutions Architect — Professional")).toBeVisible();

    // Take print screenshot
    for (const dir of targetDirs) {
      await page.screenshot({ path: path.join(dir, "builder-print-modern-template.png"), fullPage: true });
    }

    // --- 5. Generate PDF and Verify Content Extraction ---
    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: true,
      margin: { top: "0mm", right: "0mm", bottom: "0mm", left: "0mm" },
    });

    for (const dir of targetDirs) {
      fs.writeFileSync(path.join(dir, "exported-resume-modern.pdf"), pdfBuffer);
    }

    // Extract text from the generated PDF
    const extractedPdfText = await extractTextFromPdfBuffer(pdfBuffer);

    // Assert that the PDF text contains the resume content
    expect(extractedPdfText).toContain("Alexandra Chen");
    expect(extractedPdfText).toContain("alexandra.chen@example.com");
    expect(extractedPdfText).toContain("Apex Cloud Infrastructure");
    expect(extractedPdfText).toContain("RaftKv Distributed Key-Value Store");
    expect(extractedPdfText).toContain("Stanford University");
    expect(extractedPdfText).toContain("AWS Certified Solutions Architect");

    // Assert that the PDF text STRICTLY DOES NOT contain app chrome or editor text
    expect(extractedPdfText).not.toContain("Search workspace");
    expect(extractedPdfText).not.toContain("AI Tailor");
    expect(extractedPdfText).not.toContain("Resume Builder & Live Editor");
    expect(extractedPdfText).not.toContain("Save Resume");
    expect(extractedPdfText).not.toContain("LIVE RESUME PREVIEW");
    expect(extractedPdfText).not.toContain("95% ATS Score");
    expect(extractedPdfText).not.toContain("Fine-tune sections");
  });

  test("Every template in Layout & Theme prints correctly (Modern, Minimal, ATS)", async ({ page }) => {
    const targetDirs = [
      path.resolve(__dirname, "../test-results/print-export"),
      "C:\\Users\\gosul\\.gemini\\antigravity\\brain\\7f7638eb-8698-4666-af73-e8d95afc5bd1",
    ];
    for (const dir of targetDirs) {
      fs.mkdirSync(dir, { recursive: true });
    }

    await page.goto("/builder", { waitUntil: "networkidle" });
    await page.waitForSelector("h1:has-text('Alexandra Chen')", { timeout: 10000 });

    const templates = [
      { id: "modern", name: "Modern Clean", headingRegex: /Executive Summary/i },
      { id: "minimal", name: "Minimal Swiss", headingRegex: /Profile/i },
      { id: "ats", name: "Universal ATS Standard", headingRegex: /PROFESSIONAL SUMMARY/i },
    ];

    for (const tmpl of templates) {
      // Switch to screen media to click template tab
      await page.emulateMedia({ media: "screen" });

      // Click Layout & Template tab
      const templateTab = page.locator("button:has-text('Layout & Template')");
      if (await templateTab.isVisible()) {
        await templateTab.click();
      }

      // Select template
      const tmplBtn = page.locator(`button:has-text('${tmpl.name}')`);
      if (await tmplBtn.isVisible()) {
        await tmplBtn.click();
      }

      // Switch to print media
      await page.emulateMedia({ media: "print" });

      // Assert template headings are rendered
      await expect(page.locator("h1:has-text('Alexandra Chen')")).toBeVisible();
      await expect(page.getByRole("heading", { name: tmpl.headingRegex })).toBeVisible();
      await expect(page.locator("header")).toBeHidden();
      await expect(page.locator("aside")).toBeHidden();
      await expect(page.getByText("Search workspace...")).toBeHidden();

      // Screenshot print view for each template
      for (const dir of targetDirs) {
        await page.screenshot({
          path: path.join(dir, `builder-print-${tmpl.id}-template.png`),
          fullPage: true,
        });
      }

      // Export PDF for each template
      const tmplPdfBuffer = await page.pdf({ format: "A4", printBackground: true });
      for (const dir of targetDirs) {
        fs.writeFileSync(path.join(dir, `exported-resume-${tmpl.id}.pdf`), tmplPdfBuffer);
      }

      const pdfText = await extractTextFromPdfBuffer(tmplPdfBuffer);
      expect(pdfText).toContain("Alexandra Chen");
      expect(pdfText).not.toContain("Search workspace");
      expect(pdfText).not.toContain("AI Tailor");
    }
  });
});
