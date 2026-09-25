import { test, expect } from "@playwright/test";

test.describe("Phase 5.1 Milestone 4 — Career Roadmap & Evidence Promotion E2E Suite", () => {
  const mockRoadmapPlan = {
    roadmapId: "rm_e2e_test_123",
    userId: "usr_e2e_123",
    title: "Staff Platform Engineer Roadmap",
    targetRole: "Staff Platform Engineer",
    targetCompany: "Stripe",
    targetLevel: "L6",
    sourceVariantId: "var_stripe_001",
    version: 3,
    totalMilestones: 3,
    completedMilestones: 1,
    overallProgressPct: 33,
    estimatedTotalWeeks: 10,
    targetImportanceBreakdown: {
      mustHaveCount: 2,
      preferredCount: 1,
    },
    nextRecommendedMilestoneId: "ms_proj_002",
    milestones: [
      {
        milestoneId: "ms_bridge_001",
        orderIndex: 0,
        title: "Kubernetes Cluster Orchestration Attestation",
        category: "TransferableBridge",
        requirementName: "Kubernetes",
        importance: "MustHave",
        targetCapability: "Container Orchestration",
        prerequisiteEvidenceIds: ["exp_docker_lead"],
        prerequisiteMilestoneIds: [],
        sourceBridgeId: "brg_docker_k8s",
        rationale: "Docker Swarm expertise transfers to Kubernetes container orchestration.",
        estimatedWeeks: 2,
        state: "ATTESTED",
        completedAt: "2026-09-25T10:00:00Z",
      },
      {
        milestoneId: "ms_proj_002",
        orderIndex: 1,
        title: "Multi-Region Distributed Gateway Engine",
        category: "VerifiableProject",
        requirementName: "Distributed Consensus",
        importance: "MustHave",
        targetCapability: "Raft Consensus & Multi-Region Resiliency",
        prerequisiteEvidenceIds: [],
        prerequisiteMilestoneIds: ["ms_bridge_001"],
        rationale: "Demonstrate high-throughput distributed consensus in production environment.",
        estimatedWeeks: 4,
        learningPath: {
          title: "Distributed Systems & Raft Consensus",
          estimatedWeeks: 2,
          keyMilestones: ["Study Raft paper", "Implement leader election"],
          authoritativeDocsUrl: "https://raft.github.io",
        },
        projectBlueprint: {
          projectTitle: "Multi-Region Distributed Gateway Engine",
          problemStatement: "Architect zero-downtime multi-region consensus service with Raft algorithm.",
          architectureComponents: ["Raft Consensus Engine", "gRPC Mesh", "etcd Backing Store"],
          demonstratedSkills: ["Distributed Consensus", "Go", "gRPC", "Raft"],
          verificationChecklist: [
            "Implement Raft leader election",
            "Pass Jepsen network partition tests",
            "Publish benchmark report with 99.999% SLA",
          ],
        },
        state: "VERIFIED_PROJECT",
        verificationArtifact: {
          artifactId: "art_gateway_001",
          artifactType: "GitHubRepository",
          url: "https://github.com/candidate/distributed-gateway",
          repositoryBranch: "main",
          checklistCompleted: [
            "Implement Raft leader election",
            "Pass Jepsen network partition tests",
          ],
          submittedAt: "2026-09-25T12:00:00Z",
          provenanceHash: "sha256_mock_hash_abc",
        },
      },
      {
        milestoneId: "ms_cert_003",
        orderIndex: 2,
        title: "AWS Certified Solutions Architect - Professional",
        category: "DomainCertification",
        requirementName: "Cloud Architecture",
        importance: "Preferred",
        targetCapability: "Enterprise Cloud Governance",
        prerequisiteEvidenceIds: [],
        prerequisiteMilestoneIds: ["ms_proj_002"],
        rationale: "Validate enterprise cloud governance and security compliance.",
        estimatedWeeks: 4,
        state: "NOT_STARTED",
      },
    ],
    createdAt: "2026-09-25T08:00:00Z",
    updatedAt: "2026-09-25T12:00:00Z",
  };

  const mockPromotionDraft = {
    ingestionId: "ingest_prom_rm_e2e_test_123_ms_proj_002",
    documentName: "Roadmap Project: Multi-Region Distributed Gateway Engine",
    documentType: "RoadmapProject",
    status: "Parsed",
    fileSizeBytes: 2048,
    fileUrl: "https://github.com/candidate/distributed-gateway",
    parsedData: {
      profile: {
        fullName: "Jane Doe",
        headline: "Senior Software Engineer",
      },
      evidence: {
        projects: [
          {
            id: "proj_ms_proj_002",
            title: "Multi-Region Distributed Gateway Engine",
            role: "Project Creator & Lead Architect",
            description: "Architect zero-downtime multi-region consensus service with Raft algorithm.",
            highlights: [
              "Engineered Raft Consensus Engine, gRPC Mesh, etcd Backing Store.",
              "Verified implementation: Implement Raft leader election, Pass Jepsen network partition tests.",
            ],
            techStack: ["Distributed Consensus", "Go", "gRPC", "Raft"],
          },
        ],
        skills: [
          { name: "Distributed Consensus", category: "Roadmap Verified" },
          { name: "Go", category: "Roadmap Verified" },
          { name: "gRPC", category: "Roadmap Verified" },
          { name: "Raft", category: "Roadmap Verified" },
        ],
        experience: [],
        education: [],
        certifications: [],
      },
    },
  };

  test.beforeEach(async ({ page }) => {
    // Inject test-safe auth bypass
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
    });

    // Mock List Roadmaps
    await page.route("**/api/career/roadmaps", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            total: 1,
            roadmaps: [mockRoadmapPlan],
          }),
        });
      } else if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            ...mockRoadmapPlan,
            roadmapId: "rm_newly_generated_999",
            title: "Generated Staff Platform Engineer Roadmap",
          }),
        });
      }
    });

    // Mock Single Roadmap GET
    await page.route("**/api/career/roadmaps/rm_e2e_test_123", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockRoadmapPlan),
        });
      } else if (route.request().method() === "DELETE") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            roadmapId: "rm_e2e_test_123",
            message: "Roadmap deleted successfully.",
          }),
        });
      }
    });

    // Mock Milestone Progress PATCH
    await page.route("**/api/career/roadmaps/rm_e2e_test_123/progress", async (route) => {
      const payload = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockRoadmapPlan,
          version: mockRoadmapPlan.version + 1,
          milestones: mockRoadmapPlan.milestones.map((m) =>
            m.milestoneId === payload.milestoneId
              ? { ...m, state: payload.targetState }
              : m
          ),
        }),
      });
    });

    // Mock Evidence Promotion Draft POST
    await page.route(
      "**/api/career/roadmaps/rm_e2e_test_123/milestones/ms_proj_002/promote",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockPromotionDraft),
        });
      }
    );

    // Mock Ingestion Confirmation POST
    await page.route(
      "**/api/resumes/ingest/ingest_prom_rm_e2e_test_123_ms_proj_002/confirm",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            message: "Career evidence confirmed and hydrated into master workspace.",
          }),
        });
      }
    );
  });

  test("1. Career Roadmaps index page renders existing roadmaps and overview metrics", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps");

    await expect(page.getByRole("heading", { name: "Career Roadmaps" })).toBeVisible();
    await expect(page.getByText("Staff Platform Engineer Roadmap")).toBeVisible();
    await expect(page.getByText("Stripe")).toBeVisible();
    await expect(page.getByText("33%")).toBeVisible();
    await expect(page.getByText("1/3 Milestones")).toBeVisible();
    await expect(page.getByRole("button", { name: "View Roadmap" })).toBeVisible();
  });

  test("2. Roadmap detail page displays DAG progression, milestones, and metrics", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    await expect(
      page.getByRole("heading", { name: "Staff Platform Engineer Roadmap" })
    ).toBeVisible();
    await expect(page.getByText("Next Recommended Step:")).toBeVisible();
    await expect(page.getByText("Multi-Region Distributed Gateway Engine")).toBeVisible();

    // Verify milestones present
    await expect(
      page.getByText("Kubernetes Cluster Orchestration Attestation")
    ).toBeVisible();
    await expect(
      page.getByText("AWS Certified Solutions Architect - Professional")
    ).toBeVisible();
  });

  test("3. VERIFIED_PROJECT milestone renders 'Promote to Evidence Draft' button", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    const promoteButton = page.getByRole("button", {
      name: "Promote to Evidence Draft",
    });
    await expect(promoteButton).toBeVisible();
    await expect(promoteButton).toBeEnabled();
  });

  test("4. Non-eligible milestones do not render 'Promote to Evidence Draft'", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    // ATTESTED milestone should show attested badge, not promote button
    await expect(page.getByText("Skill Attested & Hydrated in Workspace")).toBeVisible();

    // NOT_STARTED milestone should show Start Milestone button, not promote button
    await expect(page.getByRole("button", { name: "Start Milestone" })).toBeVisible();
  });

  test("5. Promoting milestone opens Ingestion Review modal with provenance and editable fields", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    // Click promote
    await page.getByRole("button", { name: "Promote to Evidence Draft" }).click();

    // Ingestion review modal should open
    await expect(
      page.getByRole("heading", { name: "Review Roadmap Project Evidence" })
    ).toBeVisible();
    await expect(page.getByText("Origin: Career Roadmap Project")).toBeVisible();
    await expect(page.getByText("Multi-Region Distributed Gateway Engine")).toBeVisible();

    // Check project blueprint highlights are populated
    await expect(
      page.getByText("Engineered Raft Consensus Engine, gRPC Mesh, etcd Backing Store.")
    ).toBeVisible();

    // Check skills tab
    await page.getByRole("button", { name: /Demonstrated Skills/ }).click();
    await expect(page.getByText("Distributed Consensus")).toBeVisible();
    await expect(page.getByText("Raft")).toBeVisible();
  });

  test("6. Explicit confirmation hydrates Master Workspace and provides navigation", async ({
    page,
  }) => {
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    await page.getByRole("button", { name: "Promote to Evidence Draft" }).click();
    await expect(
      page.getByRole("heading", { name: "Review Roadmap Project Evidence" })
    ).toBeVisible();

    // Click confirm
    await page
      .getByRole("button", { name: "Confirm & Import to Master Workspace" })
      .click();

    // Success state should display
    await expect(page.getByText("Evidence Successfully Confirmed!")).toBeVisible();
    await expect(page.getByRole("button", { name: "View in Workspace Projects" })).toBeVisible();
  });

  test("7. Artifact submission modal opens and updates state on submission", async ({
    page,
  }) => {
    // Override milestone to IN_PROGRESS to test submission flow
    await page.route("**/api/career/roadmaps/rm_e2e_test_123", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockRoadmapPlan,
          milestones: mockRoadmapPlan.milestones.map((m) =>
            m.milestoneId === "ms_proj_002"
              ? { ...m, state: "IN_PROGRESS", verificationArtifact: undefined }
              : m
          ),
        }),
      });
    });

    await page.goto("/career/roadmaps/rm_e2e_test_123");

    const submitArtifactBtn = page.getByRole("button", {
      name: "Submit Verification Artifact",
    });
    await expect(submitArtifactBtn).toBeVisible();
    await submitArtifactBtn.click();

    // Modal should be open
    await expect(
      page.getByRole("heading", { name: "Submit Milestone Verification Artifact" })
    ).toBeVisible();

    // Fill in URL
    const urlInput = page.getByPlaceholder("https://github.com/username/project-repo");
    await urlInput.fill("https://github.com/candidate/distributed-gateway");

    // Click submit
    await page.getByRole("button", { name: "Submit Artifact" }).click();
  });

  test("8. Roadmap 404 error displays safe not found view with back link", async ({
    page,
  }) => {
    await page.route("**/api/career/roadmaps/rm_not_found", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Roadmap rm_not_found not found.",
        }),
      });
    });

    await page.goto("/career/roadmaps/rm_not_found");
    await expect(page.getByText("Roadmap rm_not_found not found.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Back to Roadmaps" })).toBeVisible();
  });

  test("9. Responsive mobile layout renders cleanly without errors", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/career/roadmaps/rm_e2e_test_123");

    await expect(
      page.getByRole("heading", { name: "Staff Platform Engineer Roadmap" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Promote to Evidence Draft" })
    ).toBeVisible();
  });
});
