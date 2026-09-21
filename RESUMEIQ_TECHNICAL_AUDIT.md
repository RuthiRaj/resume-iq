# ResumeIQ — Comprehensive Technical Audit & System Architecture Map

> **Audit Date:** September 9, 2026
> **Repository:** [https://github.com/RuthiRaj/resume-iq.git](https://github.com/RuthiRaj/resume-iq.git)
> **Auditor Role:** Staff Software Engineer / Principal Systems Auditor
> **Status:** READ-ONLY Technical Map & System Audit Report

---

## Executive Summary

**ResumeIQ** is an AI-powered Career Intelligence and Targeted Resume Optimization platform designed to bridge candidate credentials with Job Description (JD) Applicant Tracking System (ATS) requirements.

This technical audit provides a full system architectural blueprint of the current ResumeIQ platform. The codebase employs a hybrid decoupled architecture: Next.js 15 (React 19, App Router) serving as the User Interface and Backend-For-Frontend (BFF) proxy, FastAPI (Python 3.11+) powering the core AI orchestration, ATS scoring, document extraction, and PDF rendering engine, and Google Cloud Firestore providing multi-tenant persistence.

Key architectural highlights of the current implementation:
1. **Deterministic & Grounded AI ATS Engine:** ATS Readiness Scoring (0–100) is governed by a strict deterministic math formula (40% Relevance, 30% Keywords, 15% Metrics, 15% Formatting). AI LLM outputs are bounded by zero-hallucination substring grounding and automated claim validation.
2. **Master Profile / Targeted Variant Snapshot Immutability:** Candidate master workspace data is strictly isolated from targeted resume variants. Ingested documents and job-specific optimizations exist in isolated staging/snapshot structures without mutating the candidate's canonical master history.
3. **Multi-Tenant Cryptographic Auth:** API endpoints enforce RSA256 public key verification of Firebase ID tokens against Google’s official JWKS certificates, guaranteeing tenant isolation across all Firestore collections.

---

## Current Architecture

```
                                    +-------------------------------------------------+
                                    |                User Browser (UI)                |
                                    +-------------------------------------------------+
                                                             |
                                            HTTPS / REST / Next.js Client Route
                                                             v
                                    +-------------------------------------------------+
                                    |        Next.js BFF Proxy (Port 3000)            |
                                    |    - Auth Token Forwarding & App Router         |
                                    |    - Live In-Browser PDF Previewing             |
                                    +-------------------------------------------------+
                                                             |
                                           Internal HTTP / Bearer Auth Header
                                                             v
                                    +-------------------------------------------------+
                                    |          FastAPI AI Engine (Port 8000)          |
                                    |    - CORS & Security Headers Middleware         |
                                    |    - PyJWKClient Firebase Auth Verification    |
                                    |    - In-Memory Sliding Window Rate Limiting     |
                                    +-------------------------------------------------+
                                       |             |               |              |
                    +------------------+             |               |              +------------------+
                    |                                v               v                                 |
+-----------------------+              +------------------+ +-------------------+             +------------------+
| Document Extractor    |              |  AI Provider     | | ATS Scoring Engine|             | ReportLab Engine |
| - pypdf (PDF)         |              |  - Groq Llama-70b| | - Deterministic   |             | - ATS Vector PDF |
| - python-docx (DOCX)  |              |  - Gemini 2.5    | |   Formula (40/30/ |             | - Snapshot Only  |
| - UTF-8 / Text (TXT)  |              +------------------+ |   15/15)          |             +------------------+
+-----------------------+                        |          +-------------------+                      |
            |                                    v                    |                                |
            |                          +-------------------+          |                                |
            |                          | Grounding & Claim |          |                                |
            |                          | Validator Engine  |          |                                |
            |                          +-------------------+          |                                |
            |                                    |                    |                                |
            v                                    v                    v                                v
+--------------------------------------------------------------------------------------------------------------+
|                                       Google Cloud Firestore Database                                        |
|  - users/{uid}/profile/main                                                                                  |
|  - users/{uid}/experience/* , education/* , skills/* , projects/* , certifications/*                         |
|  - users/{uid}/ingestion_drafts/{ingestion_id}                                                                |
|  - users/{uid}/variants/{variant_id}                                                                         |
+--------------------------------------------------------------------------------------------------------------+
```

---

## Backend Components

### 1. Application Entry Point & Server Lifecycle
- **Component:** FastAPI Application Entrypoint
- **Location:** `backend/app/main.py`
- **Purpose:** Initializes FastAPI application, attaches CORS middleware, security headers, global error handlers, route registration, lifespan connection management, and mounts the Model Context Protocol (MCP) server.
- **Input:** ASGI HTTP/WebSocket requests on port 8000.
- **Output:** JSON HTTP responses, error handling payloads, streaming MCP endpoints.
- **Dependencies:** `fastapi`, `starlette`, `app.core.config`, `app.api.router`, `app.mcp.mcp_server`, `app.services.resume_service`, `app.ai.providers.groq_provider`.
- **Current Status:** Operational. Clean lifespan context manager closes HTTP client pools on shutdown.
- **Issues:** None.

---

### 2. Cryptographic Authentication Dependency
- **Component:** JWT Public Key Authentication Dependency
- **Location:** `backend/app/core/auth.py`
- **Purpose:** Cryptographically verifies incoming Firebase Bearer ID Tokens against Google's public JWKS certificates (`https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com`). Extracts and returns `AuthenticatedUser(uid, email, token)`.
- **Input:** `Authorization: Bearer <Firebase_ID_Token>` HTTP header.
- **Output:** Verified `AuthenticatedUser` object or FastAPI HTTP 401 Unauthorized exception.
- **Dependencies:** `PyJWKClient`, `jwt`, `app.core.config.settings`.
- **Current Status:** Operational. Fully verifies RSA256 signature, expiration, issuer, and audience without depending on local service account private key files.
- **Issues:** Network latency on initial JWKS certificate fetch (mitigated by singleton `PyJWKClient` caching with 1-hour lifespan).

---

### 3. In-Memory Rate Limiter
- **Component:** Sliding Window Rate Limiter
- **Location:** `backend/app/core/rate_limiter.py`
- **Purpose:** Prevents denial-of-service and LLM quota exhaustion by tracking user request timestamps per UID using an `asyncio.Lock` sliding window.
- **Input:** Request identifier (`UID`).
- **Output:** None if allowed; HTTP 429 Too Many Requests with `Retry-After` header if exceeded.
- **Dependencies:** `fastapi.HTTPException`, `asyncio`, `time`.
- **Current Status:** Operational. Configured limits: ATS Analysis (25 req/min), Synthesis (35 req/min), Mutations (50 req/min). Auto-prunes stale callers when dictionary exceeds 2,000 keys.
- **Issues:** In-memory storage resets on server restart and is not shared across multi-process workers (fine for current single-instance deployment).

---

### 4. Firebase Admin SDK Manager
- **Component:** Firestore Database Client Provider
- **Location:** `backend/app/core/firebase.py`
- **Purpose:** Initializes Firebase Admin SDK singleton app and yields authenticated Firestore client instances.
- **Input:** Environment configuration (`FIREBASE_PROJECT_ID`, optional `FIREBASE_CREDENTIALS_PATH`).
- **Output:** `google.cloud.firestore.Client` instance.
- **Dependencies:** `firebase_admin`, `app.core.config.settings`.
- **Current Status:** Operational. Automatically falls back to Google Default Application Credentials if service account file is unspecified.
- **Issues:** None.

---

### 5. Document Extractor Service
- **Component:** Document Extraction & Parsing Engine
- **Location:** `backend/app/services/document_extractor.py`
- **Purpose:** Extracts clean text from uploaded binary documents (PDF, DOCX, TXT), enforcing strict security boundaries (15MB max file size, prohibited extension blocklists, filename sanitization, character limit clamping).
- **Input:** Document filename and raw bytes payload.
- **Output:** Cleaned, whitespace-normalized plain text string (max 150,000 characters).
- **Dependencies:** `pypdf.PdfReader`, `docx.Document`, `re`, `fastapi.HTTPException`.
- **Current Status:** Operational. Fully unit-tested.
- **Issues:** OCR for scanned image-only PDFs is not supported (returns HTTP 422 with clear user error message).

---

### 6. Resume Ingestion Service
- **Component:** Document Ingestion & Staging Service
- **Location:** `backend/app/services/ingestion_service.py`
- **Purpose:** Handles end-to-end resume ingestion: validates binary upload, extracts text, calls AI ingestion parser to generate `ParsedCandidateProfile`, persists `IngestionDraft` in Firestore, and executes master workspace hydration upon explicit user confirmation.
- **Input:** Document binary, filename, UID, and user confirmation payload.
- **Output:** Staged `IngestionDraft` or `HydrationResult`.
- **Dependencies:** `app.services.document_extractor`, `app.ai.ingestion_parser`, `app.services.resume_service`, `app.core.firebase`.
- **Current Status:** Operational. Idempotent master hydration prevents duplicate experience/education records.
- **Issues:** None.

---

### 7. Master Resume Service
- **Component:** Master Workspace Data Access Layer
- **Location:** `backend/app/services/resume_service.py`
- **Purpose:** Reads and updates canonical master profile data (profile, experience, education, skills, projects, certifications, achievements) across Firestore collections under `users/{uid}/`.
- **Input:** UID, structured candidate models (`CandidateProfile`, `ExperienceItem`, etc.).
- **Output:** Hydrated `CandidateEvidence` object.
- **Dependencies:** `app.core.firebase.get_firestore_client`, `asyncio`, `app.schemas.candidate`.
- **Current Status:** Operational. Uses `asyncio.gather` for parallel Firestore sub-collection fetching.
- **Issues:** None.

---

### 8. Targeted Variant Service
- **Component:** Variant Lifecycle & Ledger Service
- **Location:** `backend/app/services/variant_service.py`
- **Purpose:** Creates targeted resume variants by snapshotting candidate master evidence and tying it to a job description hash. Manages version increments, bullet rewrites, change ledgers, and revert operations.
- **Input:** UID, Master Evidence, Job Description, Variant ID, Change Operations.
- **Output:** `TargetedVariant` object, fit comparison data.
- **Dependencies:** `app.core.firebase`, `app.ai.orchestrator`, `app.schemas.variant`.
- **Current Status:** Operational. Enforces strict snapshot isolation (edits to targeted variants never mutate master workspace).
- **Issues:** Nesting variants of variants is prohibited.

---

### 9. Professional ATS PDF Renderer Service
- **Component:** ReportLab Vector PDF Generator
- **Location:** `backend/app/services/pdf_renderer.py`
- **Purpose:** Generates single-page/multi-page professional ATS-friendly PDFs directly from targeted variant snapshots. Produces selectable vector text, standard ATS section headings, bullet formatting, and precise metric margins.
- **Input:** `ResumeViewModel` extracted strictly from `TargetedVariant` snapshot.
- **Output:** Raw PDF binary bytes (`application/pdf`).
- **Dependencies:** `reportlab.platypus`, `reportlab.lib.styles`, `reportlab.lib.pagesizes`.
- **Current Status:** Operational. Read-only generator; does not mutate Firestore.
- **Issues:** Single default ATS template currently supported; multi-template styling planned for future releases.

---

### 10. Model Context Protocol (MCP) Server
- **Component:** ResumeIQ MCP Server Interface
- **Location:** `backend/app/mcp/mcp_server.py`
- **Purpose:** Exposes ResumeIQ career workspace capabilities to external AI agents via standard MCP protocol tools (`get_master_profile`, `get_targeted_variant`, `analyze_resume_ats`, `apply_bullet_remediation`).
- **Input:** MCP JSON-RPC protocol requests with Firebase Bearer token.
- **Output:** MCP tool results containing structured candidate data and ATS scores.
- **Dependencies:** `mcp.server.fastmcp`, `app.mcp.auth`, `app.services.*`.
- **Current Status:** Operational. Mounted at `/mcp` on main FastAPI application.
- **Issues:** None.

---

## Frontend Components

### 1. Application Shell & Root Layout
- **Component:** Next.js App Router Shell
- **Location:** `frontend/src/app/(app)/layout.tsx`
- **Purpose:** Renders the main application navigation sidebar, header, global providers (`AuthProvider`, `CareerProvider`), and responsive layout wrapper.
- **Input:** React children nodes, router state.
- **Output:** Rendered HTML DOM with responsive sidebar navigation.
- **Dependencies:** `@/lib/auth-context`, `@/lib/store`, `@/components/layout/sidebar`.
- **Current Status:** Operational.
- **Issues:** None.

---

### 2. Authentication Context Provider
- **Component:** Firebase Client Auth State Manager
- **Location:** `frontend/src/lib/auth-context.tsx`
- **Purpose:** Manages user authentication state (`user`, `loading`), email/password sign-in, registration, password resets, and test-safe E2E authentication bypass mode (`e2e_bypass_auth`).
- **Input:** Firebase Auth SDK events, user credentials.
- **Output:** React Auth Context exposing `user`, `signIn`, `signUp`, `logout`.
- **Dependencies:** `firebase/auth`, `@/lib/firebase`.
- **Current Status:** Operational. Uses `useEffect` state initialization to prevent SSR React hydration mismatches.
- **Issues:** None.

---

### 3. Global Career State Store
- **Component:** Client-Side Workspace State & Cache
- **Location:** `frontend/src/lib/store.tsx`
- **Purpose:** Provides reactive React state and real-time Firestore listeners for candidate master workspace sections (profile, experience, education, skills, projects, certifications, documents).
- **Input:** Firestore real-time snapshot events.
- **Output:** `useCareer()` hook supplying reactive workspace arrays and mutation methods (`addExperience`, `deleteDocument`, etc.).
- **Dependencies:** `firebase/firestore`, `@/lib/auth-context`.
- **Current Status:** Operational.
- **Issues:** Non-fatal permission errors caught cleanly when operating in offline/test-bypass environments.

---

### 4. Ingestion & Evidence Review View
- **Component:** Document Ingestion Page
- **Location:** `frontend/src/app/(app)/workspace/documents/page.tsx`
- **Purpose:** Provides document upload dropzone, triggers backend text extraction and parsing, displays interactive evidence review modal tabs, and submits explicit workspace hydration confirmation.
- **Input:** User document file upload (PDF/DOCX/TXT).
- **Output:** Staged draft review modal, workspace hydration triggering, success CTAs ("View Master Workspace", "Run ATS Audit").
- **Dependencies:** `/api/resumes/ingest`, `@/lib/store`, `@/components/ui/modal`.
- **Current Status:** Operational. Safeguarded against missing array properties using optional chaining.
- **Issues:** None.

---

### 5. ATS Analysis & Gap Audit View
- **Component:** Job Description ATS Analyzer Page
- **Location:** `frontend/src/app/(app)/analyzer/page.tsx`
- **Purpose:** Allows candidates to select job titles, input target company names, paste raw job descriptions, and execute real-time ATS scoring audits. Renders overall match score breakdown (0–100), requirement match tables, missing skills, and remediation suggestions.
- **Input:** Target role, target company, raw job description text.
- **Output:** ATS score breakdown cards, requirement match status badges, missing skill lists, variant creation trigger.
- **Dependencies:** `/api/ai/analyze`, `/api/variants/create`, `@/lib/store`.
- **Current Status:** Operational.
- **Issues:** None.

---

### 6. Targeted Resume Workspace & Export Modal
- **Component:** Variant Workspace & PDF Exporter Page
- **Location:** `frontend/src/app/(app)/resumes/targeted/[variantId]/page.tsx`
- **Purpose:** Displays isolated targeted resume variant snapshot, requirement match progression, version history ledger, bullet remediation interface, and export modal with live in-browser PDF preview.
- **Input:** `variantId` route parameter.
- **Output:** Interactive variant editor, live `<object data={pdfPreviewUrl} type="application/pdf">` preview, ATS PDF binary download.
- **Dependencies:** `/api/variants/[variantId]`, `/api/variants/[variantId]/export/pdf`, `@/lib/store`.
- **Current Status:** Operational. Handles Blob URL generation and lifecycle cleanup.
- **Issues:** None.

---

### 7. Interactive Resume Builder View
- **Component:** Reactive Master Resume Builder
- **Location:** `frontend/src/app/(app)/builder/page.tsx`
- **Purpose:** Interactive resume builder displaying live candidate resume preview alongside master evidence control panels. Features reactive `useEffect` synchronization listening to `useCareer()` updates.
- **Input:** Candidate master profile state from `useCareer()`.
- **Output:** Rendered resume DOM preview, section edit drawers.
- **Dependencies:** `@/lib/store`, `@/components/ui/card`.
- **Current Status:** Operational. Real-time updates without page refresh.
- **Issues:** None.

---

## AI/LLM Architecture

ResumeIQ uses a **decoupled, provider-agnostic AI orchestration architecture**. LLM calls are strictly isolated behind provider interfaces, enforcing strict JSON output schemas, zero-hallucination substring grounding, and factual claim validation.

```
                                    +-----------------------------------------+
                                    |         run_ats_analysis()              |
                                    |     (app/ai/orchestrator.py)            |
                                    +-----------------------------------------+
                                                         |
                                       Generate SHA-256 Job Description Hash
                                                         v
                                    +-----------------------------------------+
                                    |       get_ai_analyzer_provider()        |
                                    |       (app/ai/factory.py)               |
                                    +-----------------------------------------+
                                                         |
                                 +-----------------------+-----------------------+
                                 |                                               |
                                 v                                               v
              +-------------------------------------+         +-------------------------------------+
              |        GroqAnalyzerProvider         |         |       GeminiAnalyzerProvider        |
              |     (app/ai/providers/groq.py)      |         |     (app/ai/providers/gemini.py)    |
              |  - Model: llama-3.3-70b-versatile   |         |  - Model: gemini-2.5-flash          |
              |  - Response Format: json_object     |         |  - Response MIME: application/json  |
              +-------------------------------------+         +-------------------------------------+
                                 |                                               |
                                 +-----------------------+-----------------------+
                                                         |
                                           Raw JSON Structured Response
                                                         v
                                    +-----------------------------------------+
                                    |  verify_and_ground_requirement_matches  |
                                    |        (app/ai/grounding.py)            |
                                    +-----------------------------------------+
                                                         |
                                       - Verify Substring Grounding in Resume
                                       - Determine Section Provenance
                                       - Enforce SkillTag Depth Restrictions
                                                         v
                                    +-----------------------------------------+
                                    |    calculate_deterministic_ats_score    |
                                    |         (app/ai/scoring.py)             |
                                    |  Score = 40%Rel + 30%KW + 15%Met + 15%Fmt|
                                    +-----------------------------------------+
                                                         |
                                           Final Grounded AnalyzeResponse
```

### LLM Call Flow & Provider Abstraction
1. **Invocation:** User submits ATS audit request $\rightarrow$ `run_ats_analysis()` calculates SHA-256 hash of job description text.
2. **Factory Selection:** `get_ai_analyzer_provider()` inspects `AI_ANALYZER_PROVIDER` env variable (`groq` or `gemini`) and instantiates `GroqAnalyzerProvider` or `GeminiAnalyzerProvider`.
3. **Prompt Construction:** User job description and serialized `CandidateEvidence` JSON are injected into system instruction templates featuring anti-injection directives.
4. **Structured JSON Output:** `Groq` requests set `response_format={"type": "json_object"}` with `temperature=0.1`. `Gemini` requests configure `response_mime_type="application/json"`.
5. **Post-Processing Pipeline:** Model output parsed into Pydantic schemas $\rightarrow$ passed to `reconcile_requirement_coverage()` $\rightarrow$ passed to `verify_and_ground_requirement_matches()` $\rightarrow$ passed to `calculate_deterministic_ats_score()`.

---

## Resume Ingestion Pipeline

ResumeIQ processes candidate document uploads through a secure server-side ingestion pipeline:

```
Upload Binary (PDF/DOCX/TXT)
  ↓
validate_document_upload() [Size <= 15MB, Extension Check, Filename Sanitization]
  ↓
extract_document_text()
  ├─ PDF: pypdf (Extracts native vector text, checks encryption & scanned image status)
  ├─ DOCX: python-docx (Extracts paragraphs & table cells)
  └─ TXT: Multi-encoding decoder (utf-8 -> latin-1 -> cp1252)
  ↓
Text Normalization (Collapses whitespace, caps at 150,000 characters)
  ↓
parse_resume_text_with_ai() [Groq/Gemini JSON Extraction]
  ↓
ParsedCandidateProfile Created
  ↓
IngestionDraft Persisted -> Firestore: users/{uid}/ingestion_drafts/{ingestion_id}
  ↓
[ Master Workspace Left Untouched ]
  ↓
User Reviews Evidence Modal Tabs (Profile, Experience, Education, Skills, Projects)
  ↓
User Clicks "Confirm & Import to Master Workspace"
  ↓
confirm_and_hydrate_ingestion()
  ├─ Idempotent check on existing Experience / Education entries
  ├─ Batch Write -> Firestore users/{uid}/...
  └─ Update IngestionDraft Status -> "Completed"
```

### Resume Section Representation
- **Profile:** Full Name, Headline, Email, Phone, Location, Portfolio Links, Target Roles, Professional Summary.
- **Experience:** Role, Company, Location, Start/End Dates, Accomplishment Bullets (Array of strings), Technologies Used.
- **Education:** Degree, Institution, Field of Study, Graduation Year.
- **Skills:** Canonicalized Skill Name, Taxonomy Category (`Language`, `Framework`, `Database`, `Cloud`, `DevOps`, `Tool`, `SoftSkill`, `Domain`).
- **Projects:** Title, Role, Description, Highlights, Tech Stack.
- **Certifications:** Certificate Title, Issuing Organization.

---

## Job Description Pipeline

```
Raw Job Description Text
  ↓
hash_job_description() -> SHA-256 Hex Digest (Whitespace & Casing Normalized)
  ↓
extract_job_description_intelligence()
  ↓
AI Extraction -> StructuredJobDescription
  ├─ title: Target Role Title
  ├─ company: Target Company Name
  ├─ experience_years_required: Optional integer
  ├─ must_have_skills: Array[SkillRequirement(name, category, importance, source_evidence)]
  ├─ preferred_skills: Array[SkillRequirement(name, category, importance, source_evidence)]
  └─ core_responsibilities: Array[string]
  ↓
normalize_and_deduplicate_skill_requirements()
  ├─ Canonical skill name dictionary lookup (e.g. "react.js" -> "React")
  ├─ Industry taxonomy category resolution
  └─ Source evidence text retention (prioritizes longer context)
```

---

## Matching and Scoring Pipeline

> [!IMPORTANT]
> ATS Readiness Scores (0–100) in ResumeIQ are **100% deterministic**. They are NOT generated by LLM estimation.

### 1. Deterministic ATS Score Calculation Formula
$$\text{ATS Score} = \text{round}\left(0.40 \times \text{Relevance} + 0.30 \times \text{Keywords} + 0.15 \times \text{Metrics} + 0.15 \times \text{Formatting}\right)$$

Implementation (`app/ai/scoring.py`):
```python
def calculate_deterministic_ats_score(relevance, keywords, metrics, formatting) -> int:
    rel = max(0.0, min(100.0, float(relevance)))
    kw  = max(0.0, min(100.0, float(keywords)))
    met = max(0.0, min(100.0, float(metrics)))
    fmt = max(0.0, min(100.0, float(formatting)))

    weighted_total = (rel * 0.40) + (kw * 0.30) + (met * 0.15) + (fmt * 0.15)
    return int(round(weighted_total))
```

### 2. Skill Match & Requirement Reconciliation Logic
1. **Match Status Classification:**
   - **StrongMatch:** Requirement is verified in candidate evidence. Must be grounded in `Experience`, `Project`, `Education`, or `Summary`.
   - **PartialMatch:** Requirement exists as standalone `SkillTag`, adjacent technology, or lacks quantified metrics for Must-Have skills.
   - **Missing:** No verified evidence found in candidate resume.
2. **Deterministic Section Provenance Hierarchy:**
   $$\text{Experience} \succ \text{Project} \succ \text{Certification} \succ \text{Education} \succ \text{Summary} \succ \text{SkillTag} \succ \text{None}$$
3. **SkillTag Depth Restriction:** If a job requirement demands production experience or multi-year depth, a skill appearing solely in the candidate's `SkillTag` list is automatically downgraded from `StrongMatch` to `PartialMatch` with `gap_type="MissingProductionExperience"`.

---

## Grounding and Security

### 1. Zero-Hallucination Grounding (`app/ai/grounding.py`)
- **Normalized Substring Matching:** Converts candidate resume text and LLM-returned evidence snippets into standardized lower-case strings (stripping quote variations and bullet glyphs). If an LLM returns evidence not present in the candidate corpus, `is_grounded_in_text()` returns `False`, automatically stripping the ungrounded evidence and setting `match_status="Missing"`.
- **Regex Metric Verification:** `METRIC_PATTERNS` regex scans candidate evidence snippets for percentage gains (`99.9%`), monetary scale (`$10M`), or resource units (`10k QPS`, `50 engineers`). Only snippets matching regex patterns receive `quantifiable_impact=True`.

### 2. Fact & Claim Validation Engine (`app/ai/claim_validator.py`)
Compares AI-rewritten accomplishment bullets against original candidate source evidence:
- **Metric Hallucination Check:** Ensures any numbers/percentages introduced in rewrites exist in source text.
- **Seniority Inflation Check:** Detects unauthorized insertion of leadership keywords (`led`, `managed`, `spearheaded`) if absent from source.
- **Team Size Validation:** Flags invented team sizes (`team of 12`).
- **Scale Term Validation:** Flags unverified infrastructure terms (`multi-region`, `petabyte`, `global`).

### 3. Prompt Injection Security
- **Strict Role Isolation:** User job descriptions and resume text are passed exclusively in the user content block inside explicit boundaries (`<JOB_DESCRIPTION>` and `<CANDIDATE_EVIDENCE>`).
- **System Directives:** System prompts contain explicit directives overriding any attempt within user text to ignore instructions, output system keys, or alter scoring logic.

---

## Database and Storage

ResumeIQ uses **Google Cloud Firestore** structured with tenant-isolated sub-collections:

```
users/{uid}                           [User Workspace Root Document]
  ├── profile/main                    [CandidateProfile: name, email, headline, targetRoles]
  ├── experience/{exp_id}             [ExperienceItem: role, company, dates, bullets, tech]
  ├── education/{edu_id}              [EducationItem: degree, institution, field, year]
  ├── skills/{skill_id}               [SkillItem: name, category, proficiency]
  ├── projects/{proj_id}              [ProjectItem: title, role, description, highlights]
  ├── certifications/{cert_id}        [CertificationItem: title, issuer]
  ├── achievements/{ach_id}           [AchievementItem: description, impact]
  ├── documents/{doc_id}              [DocumentMetadata: name, type, storagePath, size]
  ├── ingestion_drafts/{ingestion_id} [IngestionDraft: status, rawText, parsedData]
  └── variants/{variant_id}           [TargetedVariant: jobHash, snapshot, version, ledger]
```

### Security & Ownership Model
All database access is authenticated via verified Firebase UID. Security rules enforce that users can only read, write, or query documents located directly under `users/{auth.uid}/`.

---

## Testing

ResumeIQ features a dual-layer automated test suite:

### 1. Backend Test Suite (`backend/tests/`) — 186/186 Passing
- **Unit & Logic Tests:** `test_scoring.py` (verifies 40/30/15/15 weighted formula), `test_skills.py` (canonical name normalization), `test_grounding.py` (substring matching & section provenance), `test_claim_validator.py` (metric & leadership inflation detection).
- **Service & Ingestion Tests:** `test_ingestion.py` (boundary checks, 15MB limits, PDF/DOCX extraction), `test_resume_service.py` (parallel Firestore codec), `test_variants.py` (snapshot immutability, optimistic locking, ledger recording).
- **API & Security Tests:** `test_auth.py` (JWKS token verification), `test_rate_limiter.py` (sliding window enforcement), `test_prompt_security.py` (injection resistance), `test_pdf_export.py` (ReportLab vector PDF generation).

### 2. Frontend E2E Suite (`frontend/e2e/`) — 3/3 Passing Specs
- **`user-journey.spec.ts`:** Executed via Playwright Chromium.
  - **Step 1:** Dashboard Onboarding Banner & Navigation.
  - **Step 2–5:** Ingestion UI, Evidence Review Modal, Confirmation, Master Workspace Navigation.
  - **Step 6–8:** Targeted Resume Workspace, Live In-Browser PDF Preview, Export Download.

### Untested / Future Test Areas
- Live multi-user concurrency stress testing on Firestore write throughput.
- Cross-browser visual regression testing for ReportLab generated PDFs across non-standard PDF viewers.

---

## Current Strengths

1. **Mathematically Authoritative ATS Engine:** Scoring relies on deterministic formulas, eliminating AI variance and score fluctuations across identical requests.
2. **Rigorous Hallucination Protection:** Double-grounding pipeline guarantees that resume evidence snippets are genuine substrings of candidate inputs.
3. **Clean Decoupled Architecture:** FastAPI AI service and Next.js UI communicate strictly over REST APIs and standard TypeScript schemas.
4. **Snapshot Immutability:** Master career history is safely preserved when candidates create job-specific resume variants.
5. **High Automated Test Coverage:** 186 backend tests and full Playwright E2E coverage ensure regression resistance.

---

## Current Weaknesses

1. **OCR Limitations:** Image-only scanned PDFs without selectable text layers are rejected rather than optical-character-recognized.
2. **Single PDF Template:** PDF exporter currently supports a single standard ATS template.
3. **In-Memory Rate Limiting:** Rate limit state is stored in server RAM and resets upon application restart.

---

## Technical Debt

1. **Deprecated Warnings in Dependencies:** Pydantic/Starlette deprecation warnings regarding HTTP status code constants (`HTTP_413_REQUEST_ENTITY_TOO_LARGE`).
2. **Redundant Mock Utilities:** Duplicate mock utilities in frontend test files that can be consolidated into shared Playwright fixtures.

---

## Missing Capabilities

1. **Multi-Template PDF Renderer:** Ability for candidates to choose between different ATS styling templates (e.g., Modern, Classic, Compact).
2. **Async Job Processing Queue:** Document ingestion currently executes synchronously within HTTP request cycles rather than using background worker queues (Celery/Cloud Tasks).

---

## Risks

1. **Third-Party LLM API Limits:** High-volume user bursts could hit Groq/Gemini API rate limits if concurrency scales rapidly.
2. **Google JWKS Network Dependency:** Backend relies on outward HTTPS access to fetch Google's public key certificates for token verification.

---

## Recommended Development Priorities

1. **P0 — Asynchronous Ingestion Queue:** Move multi-page PDF text extraction and AI parsing to async background jobs for heavy documents.
2. **P1 — Multi-Template PDF Exporter:** Add 2–3 additional ATS-friendly layout choices to ReportLab PDF renderer.
3. **P2 — OCR Fallback Integration:** Add Tesseract/PDFocr fallback for scanned image resumes.

---

## Critical Findings

1. **ATS Score Determinism:** ATS Readiness Scores (0–100) are computed strictly via a weighted mathematical formula (40% Relevance, 30% Keywords, 15% Metrics, 15% Formatting) in `app/ai/scoring.py`. The LLM never decides the final score.
2. **Zero-Hallucination Grounding:** `app/ai/grounding.py` enforces exact normalized substring matching against candidate source text. Ungrounded claims are automatically stripped and flagged as `Missing`.
3. **Section Provenance Hierarchy:** Evidence source location is deterministically resolved using the hierarchy: $\text{Experience} \succ \text{Project} \succ \text{Certification} \succ \text{Education} \succ \text{Summary} \succ \text{SkillTag} \succ \text{None}$.
4. **SkillTag Depth Restriction:** Skills appearing only as standalone tags in a resume cannot fulfill deep production requirements and are automatically downgraded to `PartialMatch`.
5. **Snapshot Immutability:** Targeted resume variants copy master workspace evidence into immutable snapshots tied to SHA-256 job description hashes (`users/{uid}/variants/{variant_id}`). Master evidence is never mutated by targeted optimizations.
6. **Cryptographic JWKS Authentication:** `app/core/auth.py` validates Firebase ID tokens by downloading Google's public JWKS certificates, checking RSA256 signatures, expiration, and audience claims without local private key files.
7. **Idempotent Ingestion Hydration:** Master workspace hydration checks existing experience/education records before writing, preventing duplicate entries during network retries.
8. **Sliding Window Rate Limiting:** Endpoints are protected by thread-safe `InMemoryRateLimiter` sliding windows (25–50 req/min per UID).
9. **ReportLab Vector PDF Exporter:** `app/services/pdf_renderer.py` generates native vector PDF binaries with selectable text, standard margins, and ATS-compliant headings directly from variant snapshots.
10. **Test-Safe E2E Bypass:** `AuthProvider` supports a synchronous `e2e_bypass_auth` mode allowing Playwright to test protected frontend routes without exposing production Firebase credentials or causing SSR hydration mismatches.

---

## Do Not Change Yet

> [!CAUTION]
> The following core components represent foundational architectural invariants of ResumeIQ and must NOT be refactored or modified without explicit architectural authorization:

1. **`backend/app/ai/scoring.py`**: The 40/30/15/15 deterministic ATS scoring formula.
2. **`backend/app/ai/claim_validator.py`**: Automated metric and leadership claim verification logic.
3. **`backend/app/ai/grounding.py`**: Substring evidence grounding and section provenance resolution.
4. **`backend/app/core/auth.py`**: PyJWKClient RSA256 cryptographic token verification.
5. **Targeted Variant Snapshot Architecture**: Immutable fork pattern isolating master workspace data from job-specific targeted variants.
