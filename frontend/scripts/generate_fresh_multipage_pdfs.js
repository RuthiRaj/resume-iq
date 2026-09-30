const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

async function generateFreshPdfs() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const artifactDir = "C:\\Users\\gosul\\.gemini\\antigravity\\brain\\7f7638eb-8698-4666-af73-e8d95afc5bd1";

  // Mock 2+ page resume payload
  const longResumeState = {
    profile: {
      fullName: "Ruthiraj Gosula",
      headline: "Senior Cloud & Distributed Systems Architect | AI Infrastructure Lead",
      email: "gosulanani1@gmail.com",
      phone: "+91 99514 35696",
      location: "Hyderabad, Telangana, India",
      website: "https://ruthiraj.dev",
      linkedin: "https://www.linkedin.com/in/gosula-ruthiraj/",
      github: "https://github.com/RuthiRaj",
      summary: "Computer Science and AI/ML engineer with deep experience architecting high-throughput distributed systems, event-driven microservices, and AI-assisted workflow engines. Proven record delivering low-latency APIs, automated verification pipelines, and scalable cloud-native architectures.",
    },
    experience: [
      {
        id: "exp_1",
        company: "Stripe",
        role: "Staff Software Engineer - Infrastructure",
        location: "San Francisco, CA",
        startDate: "2023",
        endDate: "Present",
        bullets: [
          "Architected real-time event streaming pipeline processing 100k+ events/sec with sub-50ms p99 latency across distributed Kubernetes clusters.",
          "Designed zero-downtime database migration strategy reducing failover latency by 85% across multi-region active-active datastores.",
          "Led team of 8 engineers delivering core telemetry and observability primitives with OpenTelemetry and Prometheus.",
          "Implemented strict automated reliability tests preventing regression outages in mission-critical payment settlement paths.",
        ],
      },
      {
        id: "exp_2",
        company: "Google Cloud",
        role: "Senior Cloud Engineer",
        location: "Sunnyvale, CA",
        startDate: "2021",
        endDate: "2023",
        bullets: [
          "Built high-performance container orchestration tooling saving $1.2M annually in idle cloud compute costs.",
          "Engineered distributed caching layer utilizing Redis and gRPC, reducing backend database read load by 74%.",
          "Automated cross-region disaster recovery runbooks with automated rollback and multi-zone health checks.",
          "Authored comprehensive architectural documentation and mentoring guidelines adopted across the division.",
        ],
      },
      {
        id: "exp_3",
        company: "Amazon Web Services",
        role: "Software Development Engineer II",
        location: "Seattle, WA",
        startDate: "2019",
        endDate: "2021",
        bullets: [
          "Developed serverless asynchronous execution engine handling 50M+ requests daily with 99.999% availability.",
          "Optimized cold-start performance in AWS Lambda runtime microVMs, decreasing initiation overhead by 40%.",
          "Refactored relational persistence schemas to DynamoDB single-table design with sub-10ms predictable read latencies.",
        ],
      },
    ],
    projects: [
      {
        id: "proj_1",
        title: "ResumeIQ - Autonomous Career Intelligence Engine",
        role: "Lead Architect",
        description: "Built end-to-end multi-tier career platform featuring grounded LLM resume tailoring and deterministic document parsers.",
        highlights: [
          "Engineered token-budgeted AI provider chain with zero-data-loss fallback across Groq, Gemini, and NVIDIA NIM.",
          "Designed vector-precise PDF export engine with strict A4 pagination, uniform print margins, and ATS parsing compliance.",
          "Constructed isolated end-to-end Playwright test suite verifying resilient client state transitions under client network shield blocking.",
        ],
        techStack: ["Next.js", "TypeScript", "FastAPI", "Python", "Playwright", "Tailwind CSS"],
      },
      {
        id: "proj_2",
        title: "Distributed Fault-Tolerant Consensus Protocol",
        role: "Creator & Maintainer",
        description: "Open-source Raft implementation featuring dynamic cluster reconfiguration, snapshotting, and log compaction.",
        highlights: [
          "Benchmarked throughput exceeding 25,000 replicated state machine commits/sec under high network jitter simulation.",
          "Implemented automated chaos testing framework injecting network partitions, process pauses, and corrupt RPC frames.",
        ],
        techStack: ["Go", "gRPC", "Protobuf", "Docker"],
      },
      {
        id: "proj_3",
        title: "SpotSync - Real-time Social Fitness Matching",
        role: "Full-Stack Developer",
        description: "Full-stack mobile-responsive application connecting fitness athletes across shared geographical training centers.",
        highlights: [
          "Built responsive UI with optimistic updates and offline state persistence.",
          "Integrated Firebase Realtime Database with sub-second synchronization across client instances.",
        ],
        techStack: ["React", "TypeScript", "Tailwind CSS", "Firebase"],
      },
    ],
    skills: [
      { id: "sk_1", name: "TypeScript", category: "Languages", proficiency: "Expert" },
      { id: "sk_2", name: "Python", category: "Languages", proficiency: "Expert" },
      { id: "sk_3", name: "Go", category: "Languages", proficiency: "Advanced" },
      { id: "sk_4", name: "Next.js", category: "Frameworks", proficiency: "Expert" },
      { id: "sk_5", name: "FastAPI", category: "Frameworks", proficiency: "Expert" },
      { id: "sk_6", name: "React", category: "Frameworks", proficiency: "Expert" },
      { id: "sk_7", name: "Kubernetes", category: "Cloud & DevOps", proficiency: "Advanced" },
      { id: "sk_8", name: "Docker", category: "Cloud & DevOps", proficiency: "Expert" },
      { id: "sk_9", name: "PostgreSQL", category: "Databases", proficiency: "Expert" },
      { id: "sk_10", name: "Redis", category: "Databases", proficiency: "Advanced" },
      { id: "sk_11", name: "Distributed Systems", category: "Architecture", proficiency: "Expert" },
      { id: "sk_12", name: "CI/CD & Automation", category: "DevOps", proficiency: "Expert" },
    ],
    education: [
      {
        id: "edu_1",
        institution: "CMR College of Engineering & Technology",
        degree: "B.Tech in Computer Science Engineering (AIML)",
        fieldOfStudy: "Artificial Intelligence & Machine Learning",
      },
      {
        id: "edu_2",
        institution: "Samskruti College of Engineering and Technology",
        degree: "Diploma in Artificial Intelligence & Machine Learning",
        fieldOfStudy: "AI/ML",
      },
    ],
    certifications: [
      {
        id: "cert_1",
        title: "AWS Certified Solutions Architect - Professional",
        issuer: "Amazon Web Services",
      },
      {
        id: "cert_2",
        title: "Google Professional Cloud Architect",
        issuer: "Google Cloud",
      },
    ],
  };

  const templates = ["modern", "minimal", "ats"];

  for (const t of templates) {
    await page.addInitScript(({ state, template }) => {
      window.localStorage.setItem("e2e_bypass_auth", "true");
      window.__E2E_MOCK_CAREER_STATE__ = state;
      window.__E2E_MOCK_RESUMES__ = [
        {
          id: "res_multipage_export",
          title: "Multi-Page Production Resume",
          targetRole: "Senior Cloud & Distributed Systems Architect",
          template: template,
          score: 95,
          tags: ["Production"],
          lastEdited: "2026-09-29",
          sections: {
            summary: state.profile.summary,
            experiences: state.experience.map((e) => e.id),
            projects: state.projects.map((p) => p.id),
            education: state.education.map((e) => e.id),
            skills: state.skills.map((s) => s.id),
            certifications: state.certifications.map((c) => c.id),
          },
          snapshot: state,
        },
      ];
    }, { state: longResumeState, template: t });

    await page.goto(`http://localhost:3000/builder?resumeId=res_multipage_export`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);

    // Emulate print media
    await page.emulateMedia({ media: "print" });

    const pdfFilename = `resume-export-multipage-${t}-fresh.pdf`;
    const pdfPath = path.join(artifactDir, pdfFilename);

    await page.pdf({
      path: pdfPath,
      format: "A4",
      margin: {
        top: "12mm",
        right: "14mm",
        bottom: "12mm",
        left: "14mm",
      },
      displayHeaderFooter: false,
      printBackground: true,
    });

    console.log(`[Generated PDF] Saved ${pdfFilename} (${fs.statSync(pdfPath).size} bytes)`);
  }

  await browser.close();
  console.log("All 3 fresh multi-page PDFs generated successfully.");
}

generateFreshPdfs().catch((err) => {
  console.error("PDF generation failed:", err);
  process.exit(1);
});
