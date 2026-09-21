"""
ResumeIQ MCP Server — Phase 5.5

Implements 15 MCP tools and 6 MCP resources as a thin authorized interface
over the existing FastAPI service layer.

Architecture:
  MCP Tool / Resource
      │  (Bearer Firebase ID Token)
      ▼
  resolve_mcp_user()   ← same JWT validation as REST layer
      │
      ▼
  Existing service layer (ProfileService, ResumeService, VariantService, etc.)
      │
      ▼
  Firestore / AI providers

Security invariants:
- UID always derived from verified JWT 'sub' claim — never from a parameter.
- All IDs validated with _validate_safe_id() before use.
- Rate limiters shared with REST layer (per-user, in-memory).
- No stack traces, API keys, or credentials in MCP error messages.
- Firestore paths are always users/{uid}/... (tenant isolation).
"""

import json
import re
from typing import Optional

from mcp.server.mcpserver import MCPServer, Context
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR
from fastapi import HTTPException

from app.mcp.auth import resolve_mcp_user
from app.schemas.profile import ProfileDTO
from app.schemas.variant import (
    CreateTargetedVariantRequest,
    GenerateResumeRequest,
    ApplyVariantChangeRequest,
    AiEditVariantRequest,
    RevertChangeRequest,
)
from app.schemas.remediation import SynthesizeBulletRequest
from app.services.profile_service import ProfileService
from app.services.resume_service import (
    ResumeService,
    get_candidate_resume_data,
    persist_analysis_results,
    _validate_safe_id as _rs_validate_id,
)
from app.services.variant_service import VariantService, _validate_safe_id as _vs_validate_id
from app.services.resume_generation_service import ResumeGenerationService
from app.ai.orchestrator import run_ats_analysis
from app.ai.claim_validator import validate_claims_against_source
from app.core.rate_limiter import (
    ai_analysis_limiter,
    ai_synthesis_limiter,
    mutation_limiter,
    resume_generation_limiter,
    ai_edit_limiter,
)
from app.core.config import settings
from app.core.security import sanitize_error_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_VALID_EXPORT_FORMATS = {"markdown", "plain_text", "json", "pdf"}

MAX_JD_LEN = 50_000
MAX_BULLET_FACT_LEN = 1_000
MAX_JOB_CONTEXT_LEN = 2_000


def _validate_id(val: str, name: str) -> str:
    """Validates that an identifier is safe (alphanumeric, underscore, hyphen only)."""
    if not val or not _SAFE_ID_RE.match(val):
        raise MCPError(
            INVALID_PARAMS,
            f"Invalid {name}: must contain only alphanumeric characters, underscores, or hyphens.",
        )
    return val


def _http_to_mcp(exc: HTTPException, context: str = "") -> MCPError:
    """Converts an HTTPException from the service layer into a structured MCPError."""
    msg = sanitize_error_message(exc.status_code, exc.detail or "")
    if exc.status_code == 404:
        return MCPError(INVALID_PARAMS, msg or f"{context} not found.")
    if exc.status_code == 409:
        return MCPError(INVALID_PARAMS, exc.detail or "Version conflict. Refresh and retry.")
    if exc.status_code == 429:
        return MCPError(INVALID_PARAMS, exc.detail or "Rate limit exceeded. Please retry later.")
    if exc.status_code in (401, 403):
        return MCPError(INVALID_PARAMS, msg or "Unauthorized.")
    if exc.status_code == 400:
        return MCPError(INVALID_PARAMS, exc.detail or "Invalid request parameters.")
    return MCPError(INTERNAL_ERROR, msg or "An internal error occurred.")


def _guard_len(value: str, max_len: int, field: str) -> str:
    """Rejects oversized string inputs before passing to service layer."""
    if len(value) > max_len:
        raise MCPError(
            INVALID_PARAMS,
            f"'{field}' exceeds maximum allowed length of {max_len} characters.",
        )
    return value


# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="ResumeIQ",
    title="ResumeIQ AI Career Platform",
    description=(
        "MCP interface for the ResumeIQ AI career platform. "
        "Provides tools for managing professional profiles, resumes, "
        "AI-powered ATS analysis, remediation, targeted resume variants, "
        "and multi-format export. All operations require a valid Firebase ID token."
    ),
    version="1.0.0",
)


# ===========================================================================
# PROFILE TOOLS
# ===========================================================================


@mcp.tool(
    name="get_profile",
    description="Retrieve the authenticated user's personal profile (name, headline, links, summary, target roles).",
)
async def get_profile(ctx: Context) -> dict:
    user = resolve_mcp_user(ctx)
    try:
        profile = await ProfileService.get_profile(user)
        return profile.model_dump(by_alias=True)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Profile") from exc
    except MCPError:
        raise
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve profile.")


@mcp.tool(
    name="update_profile",
    description=(
        "Save or update the authenticated user's personal profile. "
        "All fields are optional and validated server-side."
    ),
)
async def update_profile(
    ctx: Context,
    full_name: Optional[str] = None,
    headline: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    website: Optional[str] = None,
    linkedin: Optional[str] = None,
    github: Optional[str] = None,
    summary: Optional[str] = None,
    target_roles: Optional[list] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    try:
        profile_data = ProfileDTO(
            fullName=full_name or "",
            headline=headline or "",
            email=email or "",
            phone=phone or "",
            location=location or "",
            website=website or "",
            linkedin=linkedin or "",
            github=github or "",
            summary=summary or "",
            targetRoles=target_roles or [],
        )
        response = await ProfileService.save_profile(user, profile_data)
        return {"success": response.success, "profile": response.profile.model_dump(by_alias=True)}
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Profile") from exc
    except MCPError:
        raise
    except Exception as exc:
        raise MCPError(INTERNAL_ERROR, "Failed to save profile.") from exc


# ===========================================================================
# RESUME TOOLS
# ===========================================================================


@mcp.tool(
    name="get_master_resume",
    description=(
        "Retrieve the authenticated user's live master workspace profile "
        "(all experience, projects, skills, education, certifications)."
    ),
)
async def get_master_resume(ctx: Context) -> dict:
    user = resolve_mcp_user(ctx)
    try:
        evidence = await get_candidate_resume_data(user=user, resume_id="workspace")
        return evidence.model_dump(by_alias=True)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Master resume") from exc
    except MCPError:
        raise
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve master resume.")


@mcp.tool(
    name="get_resume_data",
    description="Retrieve candidate evidence for a specific saved resume by its ID.",
)
async def get_resume_data(ctx: Context, resume_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(resume_id, "resume_id")
    try:
        evidence = await get_candidate_resume_data(user=user, resume_id=resume_id)
        return evidence.model_dump(by_alias=True)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Resume") from exc
    except MCPError:
        raise
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve resume data.")


# ===========================================================================
# JOB ANALYSIS TOOLS
# ===========================================================================


@mcp.tool(
    name="analyze_job_description",
    description=(
        "Run a full ATS analysis of the candidate's resume against a job description. "
        "Rate-limited per user. Returns ATS score, skill gaps, and remediation suggestions."
    ),
)
async def analyze_job_description(
    ctx: Context,
    resume_id: str,
    target_role: str,
    job_description: str,
    target_company: Optional[str] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(resume_id, "resume_id")
    _guard_len(job_description, MAX_JD_LEN, "job_description")
    _guard_len(target_role, 150, "target_role")
    if target_company:
        _guard_len(target_company, 100, "target_company")

    try:
        await ai_analysis_limiter.check(user.uid)
        candidate_evidence = await get_candidate_resume_data(user=user, resume_id=resume_id)
        analysis_result = await run_ats_analysis(
            target_role=target_role,
            target_company=target_company or "",
            job_description=job_description,
            candidate_evidence=candidate_evidence,
        )
        if resume_id != "workspace":
            try:
                await persist_analysis_results(user=user, resume_id=resume_id, analysis=analysis_result)
            except Exception:
                pass  # Non-fatal: persist failure does not fail the analysis
        return analysis_result.model_dump(by_alias=True)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Analysis") from exc
    except MCPError:
        raise
    except Exception:
        raise MCPError(INTERNAL_ERROR, "ATS analysis failed.")


@mcp.tool(
    name="get_analysis_results",
    description="Retrieve the persisted ATS analysis results for a saved resume.",
)
async def get_analysis_results(ctx: Context, resume_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(resume_id, "resume_id")
    try:
        doc = await ResumeService.get_resume_document(user, resume_id)
        if not doc:
            raise MCPError(INVALID_PARAMS, f"Resume '{resume_id}' not found.")
        return {
            "resumeId": resume_id,
            "atsScore": doc.get("atsScore") or doc.get("score"),
            "scoreBreakdown": doc.get("scoreBreakdown"),
            "lastAnalyzedAt": doc.get("lastAnalyzedAt"),
            "targetRole": doc.get("targetRole"),
            "targetCompany": doc.get("targetCompany"),
            "analysisResults": doc.get("analysisResults"),
        }
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Analysis results") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve analysis results.")


# ===========================================================================
# REMEDIATION TOOLS
# ===========================================================================


@mcp.tool(
    name="get_remediation",
    description="Retrieve the AI remediation suggestions from the last analysis of a resume.",
)
async def get_remediation(ctx: Context, resume_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(resume_id, "resume_id")
    try:
        doc = await ResumeService.get_resume_document(user, resume_id)
        if not doc:
            raise MCPError(INVALID_PARAMS, f"Resume '{resume_id}' not found.")
        analysis = doc.get("analysisResults") or {}
        suggestions = analysis.get("remediationSuggestions") or []
        return {
            "resumeId": resume_id,
            "atsScore": doc.get("atsScore") or doc.get("score"),
            "remediationSuggestions": suggestions,
            "totalSuggestions": len(suggestions),
        }
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Remediation") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve remediation suggestions.")


@mcp.tool(
    name="synthesize_bullet",
    description=(
        "Synthesize a professional, fact-grounded resume bullet from candidate notes. "
        "The bullet is validated to contain only claims supported by the supplied facts. "
        "Rate-limited per user."
    ),
)
async def synthesize_bullet(
    ctx: Context,
    requirement_name: str,
    candidate_fact: str,
    target_role: Optional[str] = None,
    job_context: Optional[str] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _guard_len(requirement_name, 200, "requirement_name")
    _guard_len(candidate_fact, MAX_BULLET_FACT_LEN, "candidate_fact")
    if len(candidate_fact.strip()) < 5:
        raise MCPError(INVALID_PARAMS, "'candidate_fact' must be at least 5 characters.")
    if job_context:
        _guard_len(job_context, MAX_JOB_CONTEXT_LEN, "job_context")

    try:
        await ai_synthesis_limiter.check(user.uid)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Rate limit") from exc

    api_key = settings.GROQ_API_KEY
    if not api_key or api_key.strip() in ("", "your_server_side_groq_api_key_here"):
        raise MCPError(INTERNAL_ERROR, "AI synthesis service is not configured.")

    try:
        from groq import AsyncGroq

        SYNTHESIS_SYSTEM_PROMPT = (
            "You are a Principal Resume Editor. "
            "Convert the candidate's raw real-world experience notes into ONE concise, "
            "professional, ATS-optimized resume bullet starting with a strong past-tense action verb. "
            "STRICT: synthesize ONLY within the factual boundaries of supplied notes. "
            "NEVER invent numbers, percentages, user counts, or technologies not explicitly stated. "
            'Return ONLY a single JSON object: {"synthesizedBullet": "<bullet>"}'
        )
        user_prompt = (
            f"TARGET REQUIREMENT: {requirement_name}\n"
            f"{f'TARGET ROLE: {target_role}' if target_role else ''}\n"
            f"{f'JOB CONTEXT: {job_context}' if job_context else ''}\n\n"
            f'CANDIDATE SUPPLIED FACTS (STRICT GROUND TRUTH):\n"""\n{candidate_fact}\n"""\n\n'
            "Synthesize one professional resume bullet in JSON."
        )
        model_name = settings.AI_ANALYZER_MODEL or "llama-3.3-70b-versatile"
        client = AsyncGroq(api_key=api_key, timeout=30.0)
        completion = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        resp_text = completion.choices[0].message.content or ""
        parsed = json.loads(resp_text)
        synthesized_bullet = parsed.get("synthesizedBullet", "").strip()
    except MCPError:
        raise
    except Exception:
        synthesized_bullet = candidate_fact.strip()

    if not synthesized_bullet:
        synthesized_bullet = candidate_fact.strip()

    validation = validate_claims_against_source(
        proposed_bullet=synthesized_bullet,
        source_evidence=candidate_fact,
    )

    return {
        "requirementName": requirement_name,
        "synthesizedBullet": synthesized_bullet,
        "validation": validation.model_dump(by_alias=True),
        "status": "Validated" if validation.is_valid else "RequiresCandidateInput",
    }


@mcp.tool(
    name="apply_remediation",
    description=(
        "Apply an approved change to a targeted resume variant. "
        "Respects optimistic concurrency (expected_version). "
        "Preserves master resume immutability. Rate-limited per user."
    ),
)
async def apply_remediation(
    ctx: Context,
    variant_id: str,
    requirement_name: str,
    approved_bullet: str,
    section: str = "Experience",
    target_item_id: str = "exp_0",
    target_bullet_index: Optional[int] = None,
    remediation_id: Optional[str] = None,
    source_evidence_id: Optional[str] = None,
    expected_version: Optional[int] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    _guard_len(requirement_name, 200, "requirement_name")
    _guard_len(approved_bullet, 2000, "approved_bullet")
    _validate_id(target_item_id, "target_item_id")

    try:
        await mutation_limiter.check(user.uid)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Rate limit") from exc

    try:
        req = ApplyVariantChangeRequest(
            remediationId=remediation_id,
            requirementName=requirement_name,
            section=section,
            targetItemId=target_item_id,
            targetBulletIndex=target_bullet_index,
            approvedBullet=approved_bullet,
            sourceEvidenceId=source_evidence_id,
            expectedVersion=expected_version,
        )
        variant, change_record = await VariantService.apply_change_to_variant(user, variant_id, req)
        return {
            "success": True,
            "variantId": variant.variant_id,
            "newVersion": variant.version,
            "changeId": change_record.id,
        }
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant change") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to apply remediation change.")


# ===========================================================================
# TARGETED RESUME VARIANT TOOLS
# ===========================================================================


@mcp.tool(
    name="create_targeted_variant",
    description=(
        "Fork an immutable targeted resume variant from a master resume for a specific job. "
        "Use master_resume_id='workspace' to fork from the live workspace profile."
    ),
)
async def create_targeted_variant(
    ctx: Context,
    master_resume_id: str,
    target_role: str,
    job_description: str,
    target_company: Optional[str] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(master_resume_id, "master_resume_id")
    _guard_len(target_role, 150, "target_role")
    _guard_len(job_description, MAX_JD_LEN, "job_description")
    if target_company:
        _guard_len(target_company, 150, "target_company")

    try:
        req = CreateTargetedVariantRequest(
            masterResumeId=master_resume_id,
            targetRole=target_role,
            targetCompany=target_company or "",
            jobDescription=job_description,
        )
        variant = await VariantService.create_targeted_variant(user, req)
        return variant.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant creation") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to create targeted variant.")


@mcp.tool(
    name="generate_resume",
    description=(
        "Generate a targeted resume variant for a target role (and optional job description) "
        "by ranking workspace evidence and tailoring bullets via AI with strict anti-hallucination validation. "
        "Rate-limited."
    ),
)
async def generate_resume(
    ctx: Context,
    target_role: str,
    target_company: Optional[str] = None,
    job_description: Optional[str] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _guard_len(target_role, 150, "target_role")
    if target_company:
        _guard_len(target_company, 150, "target_company")
    if job_description:
        _guard_len(job_description, MAX_JD_LEN, "job_description")

    try:
        await resume_generation_limiter.check(user.uid)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Rate limit") from exc

    try:
        req = GenerateResumeRequest(
            targetRole=target_role,
            targetCompany=target_company or "",
            jobDescription=job_description or "",
        )
        variant = await ResumeGenerationService.generate_role_targeted_resume(user, req)
        return variant.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Resume generation") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to generate targeted resume.")


@mcp.tool(
    name="get_targeted_variant",
    description="Retrieve a targeted resume variant with its full snapshot and change ledger.",
)
async def get_targeted_variant(ctx: Context, variant_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    try:
        variant = await VariantService.get_targeted_variant(user, variant_id)
        return variant.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to retrieve targeted variant.")

@mcp.tool(
    name="ai_edit_variant",
    description=(
        "Generate an unpersisted AI edit proposal for a single resume bullet or summary in a targeted variant. "
        "Returns original text, proposed text, diff, and validation status. "
        "Does not mutate the variant in the database."
    ),
)
async def ai_edit_variant(
    ctx: Context,
    variant_id: str,
    instruction: str,
    target_item_id: str,
    target_bullet_index: Optional[int] = None,
    expected_version: Optional[int] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    _guard_len(instruction, 1000, "instruction")
    _validate_id(target_item_id, "target_item_id")

    try:
        await ai_edit_limiter.check(user.uid)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Rate limit") from exc

    try:
        req = AiEditVariantRequest(
            instruction=instruction,
            targetItemId=target_item_id,
            targetBulletIndex=target_bullet_index,
            expectedVersion=expected_version,
        )
        proposal = await VariantService.propose_ai_edit(user, variant_id, req)
        return proposal.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "AI edit") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to generate AI edit proposal.")


@mcp.tool(
    name="apply_variant_change",
    description=(
        "Apply an approved modification to a targeted resume variant, recording it to the version ledger. "
        "Supports optimistic concurrency via expected_version. Rate-limited."
    ),
)
async def apply_variant_change(
    ctx: Context,
    variant_id: str,
    requirement_name: str,
    approved_bullet: str,
    section: str = "Experience",
    target_item_id: str = "exp_0",
    target_bullet_index: Optional[int] = None,
    remediation_id: Optional[str] = None,
    source_evidence_id: Optional[str] = None,
    expected_version: Optional[int] = None,
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    _guard_len(requirement_name, 200, "requirement_name")
    _guard_len(approved_bullet, 2000, "approved_bullet")
    _validate_id(target_item_id, "target_item_id")

    try:
        await mutation_limiter.check(user.uid)
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Rate limit") from exc

    try:
        req = ApplyVariantChangeRequest(
            remediationId=remediation_id,
            requirementName=requirement_name,
            section=section,
            targetItemId=target_item_id,
            targetBulletIndex=target_bullet_index,
            approvedBullet=approved_bullet,
            sourceEvidenceId=source_evidence_id,
            expectedVersion=expected_version,
        )
        variant, change_record = await VariantService.apply_change_to_variant(user, variant_id, req)
        return {
            "success": True,
            "variantId": variant.variant_id,
            "newVersion": variant.version,
            "changeId": change_record.id,
            "message": f"Change applied. Variant is now at version {variant.version}.",
        }
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant change") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to apply variant change.")


@mcp.tool(
    name="revert_variant_change",
    description=(
        "Revert a previously applied change on a targeted resume variant. "
        "Restores the original text and appends a revert audit record. "
        "This operation is deterministic and append-only."
    ),
)
async def revert_variant_change(ctx: Context, variant_id: str, change_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    _validate_id(change_id, "change_id")
    try:
        response = await VariantService.revert_change_on_variant(user, variant_id, change_id)
        return response.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant revert") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to revert variant change.")


@mcp.tool(
    name="compare_variant_fit",
    description=(
        "Compare baseline vs. current fit scores for a targeted resume variant. "
        "Returns score delta, per-requirement progressions, and gap resolution summary."
    ),
)
async def compare_variant_fit(ctx: Context, variant_id: str) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    try:
        result = await VariantService.get_fit_comparison(user, variant_id)
        return result.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Fit comparison") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to compute fit comparison.")


# ===========================================================================
# EXPORT TOOL
# ===========================================================================


@mcp.tool(
    name="export_targeted_resume",
    description=(
        "Export a targeted resume variant in the specified format. "
        "Supported formats: 'markdown', 'plain_text', 'json', 'pdf'. "
        "Read-only — does not mutate the variant or version ledger."
    ),
)
async def export_targeted_resume(
    ctx: Context,
    variant_id: str,
    format: str = "markdown",
) -> dict:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    if format not in _VALID_EXPORT_FORMATS:
        raise MCPError(
            INVALID_PARAMS,
            f"Unsupported export format '{format}'. Must be: {', '.join(sorted(_VALID_EXPORT_FORMATS))}.",
        )
    try:
        if format == "pdf":
            pdf_bytes, filename = await VariantService.export_targeted_variant_pdf(user, variant_id, template="ats")
            import base64
            return {
                "variantId": variant_id,
                "format": "pdf",
                "filename": filename,
                "contentBase64": base64.b64encode(pdf_bytes).decode("utf-8"),
                "mimeType": "application/pdf",
            }
        result = await VariantService.export_targeted_variant_snapshot(user, variant_id, fmt=format)
        return result.model_dump(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Export") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to export targeted resume.")


# ===========================================================================
# MCP RESOURCES (read-only contextual data)
# ===========================================================================


@mcp.resource(
    "resumeiq://profile/{target}",
    name="User Profile",
    description="The authenticated user's personal profile (target can be 'me' or 'main').",
    mime_type="application/json",
)
async def resource_profile(target: str, ctx: Context) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(target, "target")
    try:
        profile = await ProfileService.get_profile(user)
        return profile.model_dump_json(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Profile resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read profile resource.")


@mcp.resource(
    "resumeiq://resume/{resume_id}",
    name="Resume Data",
    description="Candidate evidence snapshot for a specific resume (or 'workspace' for live profile).",
    mime_type="application/json",
)
async def resource_resume(ctx: Context, resume_id: str) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(resume_id, "resume_id")
    try:
        evidence = await get_candidate_resume_data(user=user, resume_id=resume_id)
        return evidence.model_dump_json(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Resume resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read resume resource.")


@mcp.resource(
    "resumeiq://variant/{variant_id}",
    name="Targeted Variant",
    description="Full targeted resume variant with snapshot and change ledger.",
    mime_type="application/json",
)
async def resource_variant(ctx: Context, variant_id: str) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    try:
        variant = await VariantService.get_targeted_variant(user, variant_id)
        return variant.model_dump_json(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Variant resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read variant resource.")


@mcp.resource(
    "resumeiq://variant/{variant_id}/fit",
    name="Variant Fit Comparison",
    description="Baseline vs. current fit comparison for a targeted resume variant.",
    mime_type="application/json",
)
async def resource_fit(ctx: Context, variant_id: str) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    try:
        result = await VariantService.get_fit_comparison(user, variant_id)
        return result.model_dump_json(by_alias=True)
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Fit comparison resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read fit comparison resource.")


@mcp.resource(
    "resumeiq://variant/{variant_id}/changes",
    name="Variant Change History",
    description="Append-only change ledger for a targeted resume variant.",
    mime_type="application/json",
)
async def resource_changes(ctx: Context, variant_id: str) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    try:
        variant = await VariantService.get_targeted_variant(user, variant_id)
        ledger = [r.model_dump(by_alias=True) for r in variant.change_ledger]
        return json.dumps({"variantId": variant_id, "changeLedger": ledger})
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Change history resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read change history resource.")


@mcp.resource(
    "resumeiq://variant/{variant_id}/export/{fmt}",
    name="Exported Resume",
    description="Exported targeted resume in markdown, plain_text, or json format.",
    mime_type="text/plain",
)
async def resource_export(ctx: Context, variant_id: str, fmt: str) -> str:
    user = resolve_mcp_user(ctx)
    _validate_id(variant_id, "variant_id")
    if fmt not in _VALID_EXPORT_FORMATS:
        raise MCPError(
            INVALID_PARAMS,
            f"Unsupported format '{fmt}'. Use: {', '.join(sorted(_VALID_EXPORT_FORMATS))}.",
        )
    try:
        result = await VariantService.export_targeted_variant_snapshot(user, variant_id, fmt=fmt)
        return result.content
    except MCPError:
        raise
    except HTTPException as exc:
        raise _http_to_mcp(exc, "Export resource") from exc
    except Exception:
        raise MCPError(INTERNAL_ERROR, "Failed to read export resource.")


# ---------------------------------------------------------------------------
# ASGI app for mounting into FastAPI (SSE transport)
# ---------------------------------------------------------------------------

mcp_app = mcp.sse_app()

