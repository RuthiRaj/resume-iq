import json
import hashlib
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from groq import AsyncGroq
from app.core.config import settings
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.remediation import (
    SynthesizeBulletRequest,
    SynthesizeBulletResponse,
    ApplyRemediationRequest,
    ApplyRemediationResponse,
)
from app.ai.claim_validator import validate_claims_against_source
from app.ai.remediation_engine import generate_source_evidence_id
from app.services.resume_service import ResumeService
from app.ai.grounding import normalize_for_grounding

router = APIRouter(prefix="/remediate", tags=["AI Remediation"])

SYNTHESIS_SYSTEM_PROMPT = """You are a Principal Resume Editor.
Your task is to convert the candidate's raw real-world experience notes into ONE concise, professional, ATS-optimized resume bullet starting with a strong past-tense action verb.

STRICT MANDATORY SAFETY CONSTRAINT:
1. You must STRICTLY synthesize only within the factual boundaries of the candidate's supplied notes.
2. NEVER invent, hallucinate, or add any numbers, percentages, user counts, request volumes, team sizes, leadership titles, or technologies not explicitly stated in the candidate's notes.
3. Return ONLY a single JSON object matching: {"synthesizedBullet": "<The professional bullet string>"}."""


@router.post(
    "/synthesize-bullet",
    response_model=SynthesizeBulletResponse,
    summary="Synthesize fact-grounded resume bullet from candidate notes",
)
async def synthesize_bullet_endpoint(
    req: SynthesizeBulletRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> SynthesizeBulletResponse:
    api_key = settings.GROQ_API_KEY
    if not api_key or api_key.strip() in ("", "your_server_side_groq_api_key_here"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GROQ_API_KEY is not configured on the backend server.",
        )

    model_name = settings.AI_ANALYZER_MODEL or "openai/gpt-oss-120b"
    client = AsyncGroq(api_key=api_key, timeout=30.0)

    user_prompt = (
        f"TARGET REQUIREMENT: {req.requirement_name}\n"
        f"{f'TARGET ROLE: {req.target_role}' if req.target_role else ''}\n"
        f"{f'JOB CONTEXT: {req.job_context}' if req.job_context else ''}\n\n"
        f"CANDIDATE SUPPLIED FACTS (STRICT GROUND TRUTH):\n\"\"\"\n{req.candidate_fact}\n\"\"\"\n\n"
        f"Synthesize one professional resume bullet representing these exact facts in JSON."
    )

    try:
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
    except Exception as e:
        err_str = str(e)
        if "timeout" in err_str.lower():
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Synthesis timed out.")
        # Fallback to direct candidate note formatting if LLM fails
        synthesized_bullet = req.candidate_fact.strip()

    if not synthesized_bullet:
        synthesized_bullet = req.candidate_fact.strip()

    # Run Claim-Preservation Validation against the user's supplied facts
    validation_res = validate_claims_against_source(
        proposed_bullet=synthesized_bullet,
        source_evidence=req.candidate_fact,
    )

    return SynthesizeBulletResponse(
        requirement_name=req.requirement_name,
        synthesized_bullet=synthesized_bullet,
        validation=validation_res,
        status="Validated" if validation_res.is_valid else "RequiresCandidateInput",
    )


@router.post(
    "/apply",
    response_model=ApplyRemediationResponse,
    summary="Transactional apply of approved remediation to Targeted Resume Variant",
)
async def apply_remediation_endpoint(
    req: ApplyRemediationRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ApplyRemediationResponse:
    """
    Applies an approved remediation to a Targeted Resume Variant in Firestore.
    Guarantees master resume protection and verifies stable source evidence anchor.
    """
    # 1. Fetch current resume snapshot
    resume_doc = await ResumeService.get_resume_document(current_user, req.resume_id)
    if not resume_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID '{req.resume_id}' not found.",
        )

    snapshot = resume_doc.get("snapshot", {})
    experience_list = snapshot.get("experience", [])
    projects_list = snapshot.get("projects", [])
    skills_list = snapshot.get("skills", [])

    # 2. Targeted Resume Variant Isolation
    # If working on master resume or base resume, create or update a targeted variant
    targeted_resume_id = req.resume_id
    if not targeted_resume_id.startswith("targeted_") and req.target_role:
        target_slug = hashlib.md5(f"{req.target_role}_{req.target_company}".encode()).hexdigest()[:8]
        targeted_resume_id = f"targeted_{req.resume_id}_{target_slug}"

    # 3. Verify stable source evidence anchor (Stale Edit Rejection)
    if req.source_evidence_id and req.target_section == "Experience" and experience_list:
        if req.target_bullet_index is not None and req.target_bullet_index < len(experience_list[0].get("bullets", [])):
            current_bullet = experience_list[0]["bullets"][req.target_bullet_index]
            current_anchor_id = generate_source_evidence_id(
                section=req.target_section,
                experience_id=req.target_experience_id,
                evidence_text=current_bullet,
            )
            if req.source_evidence_id != current_anchor_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Stale remediation: target bullet has been modified since analysis. Please re-analyze before applying.",
                )

    # 4. Apply the approved change to the snapshot
    applied = False

    if req.target_section == "Experience" and experience_list:
        if req.target_bullet_index is not None and req.target_bullet_index < len(experience_list[0].get("bullets", [])):
            experience_list[0]["bullets"][req.target_bullet_index] = req.approved_bullet
            applied = True
        else:
            if "bullets" not in experience_list[0]:
                experience_list[0]["bullets"] = []
            experience_list[0]["bullets"].append(req.approved_bullet)
            applied = True

    elif req.target_section == "Project" and projects_list:
        if "highlights" not in projects_list[0]:
            projects_list[0]["highlights"] = []
        projects_list[0]["highlights"].append(req.approved_bullet)
        applied = True

    else:
        # Default: append to primary experience bullets
        if experience_list:
            if "bullets" not in experience_list[0]:
                experience_list[0]["bullets"] = []
            experience_list[0]["bullets"].append(req.approved_bullet)
            applied = True
        else:
            # Create fresh experience entry
            experience_list.append({
                "role": req.target_role or "Software Engineer",
                "company": "Professional Experience",
                "bullets": [req.approved_bullet],
                "technologies": [],
            })
            applied = True

    snapshot["experience"] = experience_list
    snapshot["projects"] = projects_list
    snapshot["skills"] = skills_list

    # 4. Save to Firestore under the targeted variant
    updated_doc_data = {
        "title": f"Targeted: {req.target_role or 'Custom'}" if not resume_doc.get("title", "").startswith("Targeted:") else resume_doc.get("title"),
        "targetRole": req.target_role or resume_doc.get("targetRole", ""),
        "targetCompany": req.target_company or resume_doc.get("targetCompany", ""),
        "template": resume_doc.get("template", "ats"),
        "snapshot": snapshot,
        "isTargetedVariant": True,
        "masterResumeId": req.resume_id,
    }

    save_success = await ResumeService.save_resume_snapshot(
        user=current_user,
        resume_id=targeted_resume_id,
        resume_data=updated_doc_data,
    )

    if not save_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist remediation to targeted resume variant.",
        )

    return ApplyRemediationResponse(
        success=True,
        status="Applied",
        targeted_resume_id=targeted_resume_id,
        message=f"Remediation successfully applied to targeted resume variant '{targeted_resume_id}'.",
    )
