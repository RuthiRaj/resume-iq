"""
Career Intelligence Service (Phase 5.0)

Orchestrates:
1. Career Gap Analysis & Transferable Bridge Discovery
2. Candidate Attestation Processing with strict ClaimValidator Gating
3. Change Ledger Integration & Provenance Tracking
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any
from fastapi import HTTPException, status

from app.core.auth import AuthenticatedUser
from app.schemas.career_intelligence import (
    AnalyzeGapsRequest,
    AnalyzeGapsResponse,
    CandidateAttestationRequest,
    CandidateAttestationRecord,
    AttestSkillResponse,
    TransferableSkillBridge,
    GapRemediationStrategy,
)
from app.schemas.variant import (
    TargetedResumeVariant,
    ApplyVariantChangeRequest,
    ChangeRecord,
)
from app.schemas.remediation import ValidationResult, UnsupportedClaim
from app.ai.skills import normalize_skill_name, normalize_skill_category
from app.ai.career.bridge_engine import BridgeEngine
from app.ai.career.remediation_blueprints import GapRemediationEngine
from app.ai.claim_validator import validate_claims_against_source
from app.services.variant_service import VariantService, _resolve_target_item, _validate_safe_id
from app.services.resume_service import (
    _get_firestore_base_url,
    get_http_client,
    _decode_firestore_doc,
    _encode_firestore_fields,
)
from app.core.logging import get_logger

logger = get_logger("app.services.career_intelligence")


class CareerIntelligenceService:
    """
    Service Layer for Career Intelligence & Experiential Gap Bridging.
    Guarantees 100% tenant isolation, zero root workspace contamination, and strict claim validation.
    """

    @classmethod
    async def analyze_gaps(
        cls,
        user: AuthenticatedUser,
        req: AnalyzeGapsRequest,
    ) -> AnalyzeGapsResponse:
        """
        Analyzes a targeted resume variant for missing requirements, discoveries candidate-grounded
        transferable bridges, and constructs honest remediation strategies for structural gaps.
        """
        variant = await VariantService.get_targeted_variant(user, req.variant_id)
        
        # Extract requirements from variant matches (current or baseline)
        matches = variant.current_matches or variant.baseline_matches or []
        total_reqs = len(matches)

        matched_count = sum(1 for m in matches if m.match_status == "StrongMatch")
        missing_reqs = [m for m in matches if m.match_status in ("Missing", "PartialMatch")]

        # 1. Discover transferable skill bridges
        transferable_bridges: List[TransferableSkillBridge] = BridgeEngine.find_transferable_bridges(
            missing_requirements=missing_reqs,
            candidate_evidence=variant.snapshot,
        )

        # 2. Identify remaining hard gaps that have no transferable bridges
        bridged_req_names = {normalize_skill_name(b.required_skill).lower() for b in transferable_bridges}
        hard_gap_remediations: List[GapRemediationStrategy] = []

        for req_item in missing_reqs:
            norm_name = normalize_skill_name(req_item.requirement_name).lower()
            # If not bridged by existing candidate skill, generate actionable remediation strategy
            if norm_name not in bridged_req_names:
                strat = GapRemediationEngine.generate_remediation_strategy(req_item)
                hard_gap_remediations.append(strat)

        return AnalyzeGapsResponse(
            variantId=req.variant_id,
            totalRequirements=total_reqs,
            matchedCount=matched_count,
            transferableBridgesCount=len(transferable_bridges),
            hardGapsCount=len(hard_gap_remediations),
            transferableBridges=transferable_bridges,
            hardGapRemediations=hard_gap_remediations,
        )

    @classmethod
    async def process_attestation(
        cls,
        user: AuthenticatedUser,
        req: CandidateAttestationRequest,
    ) -> AttestSkillResponse:
        """
        Validates a candidate's real-world attestation, gates claims with ClaimValidator,
        creates an auditable attestation record, and applies the change to the variant change ledger.
        """
        # 1. Verify User & Variant Ownership (Tenant Isolation)
        variant = await VariantService.get_targeted_variant(user, req.variant_id)

        # Optimistic concurrency check
        if req.expected_version is not None and variant.version != req.expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrency conflict: variant is at version {variant.version}, but expected version was {req.expected_version}.",
            )

        # 2. Validate Attestation Substantiveness
        ctx = req.attested_context.strip()
        acts = req.attested_actions.strip()
        if len(ctx) < 5 or len(acts) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attestation requires substantive context (where) and specific implementation actions (what).",
            )

        # 3. Resolve Original Target Item in Variant Snapshot
        candidate_evidence = variant.snapshot
        target_item_id = req.target_item_id
        original_bullet = ""

        # Determine section and retrieve original bullet text
        section = "Experience"
        if target_item_id.startswith("proj"):
            section = "Project"
            proj_item, _ = _resolve_target_item(candidate_evidence.projects, target_item_id, "Project")
            bullet_idx = req.target_bullet_index if req.target_bullet_index is not None else 0
            if proj_item.highlights and 0 <= bullet_idx < len(proj_item.highlights):
                original_bullet = proj_item.highlights[bullet_idx]
            elif proj_item.highlights:
                original_bullet = proj_item.highlights[0]
            item_techs = set(proj_item.tech_stack)
            item_title = proj_item.title
        else:
            section = "Experience"
            exp_item, _ = _resolve_target_item(candidate_evidence.experience, target_item_id, "Experience")
            bullet_idx = req.target_bullet_index if req.target_bullet_index is not None else 0
            if exp_item.bullets and 0 <= bullet_idx < len(exp_item.bullets):
                original_bullet = exp_item.bullets[bullet_idx]
            elif exp_item.bullets:
                original_bullet = exp_item.bullets[0]
            item_techs = set(exp_item.technologies)
            item_title = f"{exp_item.role} at {exp_item.company}" if exp_item.company else exp_item.role

        # 4. Construct Proposed Attested Bullet
        # Build syntactically clean bullet containing the attested facts and required skill
        scale_clause = f" ({req.duration_or_scale.strip()})" if req.duration_or_scale and req.duration_or_scale.strip() else ""
        proposed_bullet = f"{acts.rstrip('.')}{scale_clause} utilizing {req.requirement_name}."

        # 5. Gate with ClaimValidator
        # Allowed candidate skills include verified skills + explicitly attested requirement name + adjacent skill
        allowed_skills = [s.name for s in candidate_evidence.skills]
        allowed_skills.append(req.requirement_name)
        if req.adjacent_skill_used:
            allowed_skills.append(req.adjacent_skill_used)

        # Extract tokens from attested context & actions & duration as valid item context
        item_context_tokens: Set[str] = set()
        item_context_tokens.update(ctx.split())
        item_context_tokens.update(acts.split())
        if req.duration_or_scale:
            item_context_tokens.update(req.duration_or_scale.split())

        # Source evidence includes original bullet and candidate's attested context & duration
        # (Attested actions are validated against this source to prevent ungrounded metric/scope inflation)
        duration_str = req.duration_or_scale.strip() if req.duration_or_scale else ""
        source_evidence = f"{original_bullet} {ctx} {duration_str}".strip() if (ctx or duration_str) else original_bullet

        val_res = validate_claims_against_source(
            proposed_bullet=proposed_bullet,
            source_evidence=source_evidence,
            item_context_tokens=item_context_tokens,
            candidate_skills=allowed_skills,
        )

        # If claim validation rejected ungrounded metrics or builder verbs, abort with 400
        if not val_res.is_valid:
            reasons = [u.reason for u in val_res.unsupported_claims]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attestation failed claim validation: {'; '.join(reasons)}",
            )

        # 6. Generate SHA-256 Provenance Anchor & Attestation ID
        now_iso = datetime.now(timezone.utc).isoformat()
        attestation_id = f"att_{uuid.uuid4().hex[:10]}"
        provenance_source = f"{user.uid}:{req.variant_id}:{req.requirement_name}:{proposed_bullet}:{now_iso}"
        provenance_hash = hashlib.sha256(provenance_source.encode("utf-8")).hexdigest()

        # 7. Apply Change to Variant via VariantService Gateway
        apply_req = ApplyVariantChangeRequest(
            requirementName=req.requirement_name,
            section=section,
            targetItemId=req.target_item_id,
            targetBulletIndex=req.target_bullet_index,
            approvedBullet=proposed_bullet,
            remediationId=attestation_id,
            expectedVersion=req.expected_version,
            actionType="UserAttested",
            confirmUserAttested=True,
        )

        updated_variant, change_rec = await VariantService.apply_change_to_variant(
            user=user,
            variant_id=req.variant_id,
            req=apply_req,
        )

        # 8. Synchronize to Master Workspace if explicitly requested by candidate
        workspace_updated = False
        if req.apply_to_workspace:
            workspace_updated = await cls._sync_attestation_to_workspace(
                user=user,
                req=req,
                attestation_id=attestation_id,
                proposed_bullet=proposed_bullet,
                section=section,
            )

        return AttestSkillResponse(
            success=True,
            attestationId=attestation_id,
            status="Applied",
            requirementName=req.requirement_name,
            changeRecord=change_rec,
            newVersion=updated_variant.version,
            validation=val_res,
            workspaceUpdated=workspace_updated,
            message=f"Successfully attested and applied '{req.requirement_name}' to variant v{updated_variant.version}."
            + (" Synced to Master Workspace." if workspace_updated else ""),
        )

    @classmethod
    async def _sync_attestation_to_workspace(
        cls,
        user: AuthenticatedUser,
        req: CandidateAttestationRequest,
        attestation_id: str,
        proposed_bullet: str,
        section: str,
    ) -> bool:
        """
        Synchronizes an approved candidate attestation into the authenticated user's Master Career Workspace.
        Guarantees:
        - 100% tenant isolation (paths strictly under users/{user.uid})
        - Never promotes attestation to 'verified' (skill is 'user_confirmed', provenance='user_attestation')
        - Never downgrades existing 'verified' skills
        - Does NOT invent fake proficiency ("Intermediate") or fake years (1 year)
        - Preserves existing experience/project evidence and attributes new content to attestation_id
        - Idempotent against duplicate sync requests
        """
        base_url = f"{_get_firestore_base_url()}/users/{user.uid}"
        headers = {"Authorization": f"Bearer {user.token}", "Content-Type": "application/json"}
        client = get_http_client()
        norm_req_name = normalize_skill_name(req.requirement_name)

        # 1. Synchronize Skill into users/{uid}/skills
        try:
            skills_res = await client.get(f"{base_url}/skills", headers=headers, timeout=25.0)
            existing_skills: List[Dict[str, Any]] = []
            if skills_res.status_code == 200:
                docs = skills_res.json().get("documents", [])
                existing_skills = [_decode_firestore_doc(d) for d in docs]

            matched_skill = None
            for s in existing_skills:
                if normalize_skill_name(s.get("name", "")) == norm_req_name:
                    matched_skill = s
                    break

            if matched_skill:
                # Skill already exists in workspace
                cur_status = matched_skill.get("verificationStatus", "verified")
                if cur_status == "verified":
                    # PRESERVE VERIFIED STATUS: never downgrade verified to user_confirmed
                    pass
                else:
                    # Update status to user_confirmed and set provenance, preserving existing proficiency/years
                    skill_id = matched_skill.get("id") or matched_skill.get("name", "").split("/")[-1]
                    patch_payload: Dict[str, Any] = {
                        "name": matched_skill.get("name") or req.requirement_name,
                        "verificationStatus": "user_confirmed",
                        "provenance": "user_attestation",
                        "confidence": 0.70,
                        "sourceDocumentId": attestation_id,
                        "sourceContext": f"{req.attested_context}: {req.attested_actions}",
                    }
                    if req.category:
                        patch_payload["category"] = req.category
                    elif matched_skill.get("category"):
                        patch_payload["category"] = matched_skill["category"]
                    else:
                        patch_payload["category"] = normalize_skill_category(norm_req_name, "Other")

                    if req.proficiency:
                        patch_payload["proficiency"] = req.proficiency
                    elif matched_skill.get("proficiency"):
                        patch_payload["proficiency"] = matched_skill["proficiency"]

                    if matched_skill.get("yearsOfExperience") is not None:
                        patch_payload["yearsOfExperience"] = matched_skill["yearsOfExperience"]

                    doc_url = f"{base_url}/skills/{skill_id}"
                    fields_body = {"fields": _encode_firestore_fields(patch_payload)}
                    await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)
            else:
                # Create new skill with ONLY supported info (NO fabricated Intermediate, NO fabricated 1 year)
                new_skill_id = f"skill_{uuid.uuid4().hex[:8]}"
                new_payload: Dict[str, Any] = {
                    "name": req.requirement_name,
                    "verificationStatus": "user_confirmed",
                    "provenance": "user_attestation",
                    "confidence": 0.70,
                    "sourceDocumentId": attestation_id,
                    "sourceContext": f"{req.attested_context}: {req.attested_actions}",
                    "category": req.category or normalize_skill_category(norm_req_name, "Other"),
                }
                if req.proficiency:
                    new_payload["proficiency"] = req.proficiency

                doc_url = f"{base_url}/skills/{new_skill_id}"
                fields_body = {"fields": _encode_firestore_fields(new_payload)}
                await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)

        except Exception as e:
            logger.warning(f"Failed to synchronize skill '{req.requirement_name}' to workspace: {e}")

        # 2. Synchronize Experience or Project Item
        try:
            target_id = req.target_item_id.strip()
            _validate_safe_id(target_id, "target_item_id")

            if section == "Project" or target_id.startswith("proj"):
                proj_res = await client.get(f"{base_url}/projects", headers=headers, timeout=25.0)
                if proj_res.status_code == 200:
                    docs = proj_res.json().get("documents", [])
                    existing_proj = [_decode_firestore_doc(d) for d in docs]
                    matched_proj = next((p for p in existing_proj if p.get("id") == target_id), None)
                    if not matched_proj and target_id.startswith("proj_"):
                        try:
                            idx = int(target_id.split("_")[1])
                            if 0 <= idx < len(existing_proj):
                                matched_proj = existing_proj[idx]
                        except Exception:
                            pass

                    if matched_proj:
                        proj_id = matched_proj.get("id")
                        highlights = list(matched_proj.get("highlights", []))
                        tech_stack = list(matched_proj.get("techStack", matched_proj.get("technologies", [])))
                        attestation_ids = list(matched_proj.get("attestationIds", matched_proj.get("remediationIds", [])))

                        updated = False
                        if proposed_bullet not in highlights:
                            highlights.append(proposed_bullet)
                            updated = True
                        if req.requirement_name not in tech_stack:
                            tech_stack.append(req.requirement_name)
                            updated = True
                        if attestation_id not in attestation_ids:
                            attestation_ids.append(attestation_id)
                            updated = True

                        if updated:
                            patch_proj = {
                                "title": matched_proj.get("title", ""),
                                "role": matched_proj.get("role", ""),
                                "description": matched_proj.get("description", ""),
                                "highlights": highlights,
                                "techStack": tech_stack,
                                "attestationIds": attestation_ids,
                            }
                            if matched_proj.get("sourceDocumentId"):
                                patch_proj["sourceDocumentId"] = matched_proj["sourceDocumentId"]
                            if matched_proj.get("verificationStatus"):
                                patch_proj["verificationStatus"] = matched_proj["verificationStatus"]

                            doc_url = f"{base_url}/projects/{proj_id}"
                            fields_body = {"fields": _encode_firestore_fields(patch_proj)}
                            await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)

            elif section == "Experience" or target_id.startswith("exp"):
                exp_res = await client.get(f"{base_url}/experience", headers=headers, timeout=25.0)
                if exp_res.status_code == 200:
                    docs = exp_res.json().get("documents", [])
                    existing_exp = [_decode_firestore_doc(d) for d in docs]
                    matched_exp = next((e for e in existing_exp if e.get("id") == target_id), None)
                    if not matched_exp and target_id.startswith("exp_"):
                        try:
                            idx = int(target_id.split("_")[1])
                            if 0 <= idx < len(existing_exp):
                                matched_exp = existing_exp[idx]
                        except Exception:
                            pass

                    if matched_exp:
                        exp_id = matched_exp.get("id")
                        bullets = list(matched_exp.get("bullets", []))
                        technologies = list(matched_exp.get("technologies", []))
                        attestation_ids = list(matched_exp.get("attestationIds", matched_exp.get("remediationIds", [])))

                        updated = False
                        if proposed_bullet not in bullets:
                            bullets.append(proposed_bullet)
                            updated = True
                        if req.requirement_name not in technologies:
                            technologies.append(req.requirement_name)
                            updated = True
                        if attestation_id not in attestation_ids:
                            attestation_ids.append(attestation_id)
                            updated = True

                        if updated:
                            patch_exp = {
                                "company": matched_exp.get("company", ""),
                                "role": matched_exp.get("role", ""),
                                "location": matched_exp.get("location", ""),
                                "startDate": matched_exp.get("startDate", ""),
                                "endDate": matched_exp.get("endDate", ""),
                                "bullets": bullets,
                                "technologies": technologies,
                                "attestationIds": attestation_ids,
                            }
                            if matched_exp.get("sourceDocumentId"):
                                patch_exp["sourceDocumentId"] = matched_exp["sourceDocumentId"]
                            if matched_exp.get("verificationStatus"):
                                patch_exp["verificationStatus"] = matched_exp["verificationStatus"]

                            doc_url = f"{base_url}/experience/{exp_id}"
                            fields_body = {"fields": _encode_firestore_fields(patch_exp)}
                            await client.patch(doc_url, headers=headers, json=fields_body, timeout=25.0)

        except Exception as e:
            logger.warning(f"Failed to synchronize experience/project to workspace: {e}")

        # 3. Invalidate workspace analysis cache so subsequent analysis authoritatively re-evaluates fresh workspace evidence
        try:
            await client.delete(f"{base_url}/analyses/workspace", headers=headers, timeout=10.0)
        except Exception:
            pass

        return True
