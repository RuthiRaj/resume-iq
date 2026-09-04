import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.variant import (
    TargetedResumeVariant,
    ChangeRecord,
    RequirementProgression,
    FitComparisonResponse,
    CreateTargetedVariantRequest,
    ApplyVariantChangeRequest,
    RevertChangeResponse,
    ExportTargetedResumeResponse,
)
from app.schemas.requirement_match import RequirementMatch
from app.services.resume_service import ResumeService
from app.ai.remediation_engine import generate_source_evidence_id


def _parse_candidate_evidence_from_snapshot(snap_raw: Optional[Dict[str, Any]]) -> CandidateEvidence:
    """Parses raw Firestore resume snapshot into a strongly-typed CandidateEvidence model."""
    if not isinstance(snap_raw, dict):
        return CandidateEvidence()

    profile = snap_raw.get("profile") or {}
    experiences = [ExperienceItem.model_validate(e) for e in snap_raw.get("experience", [])]
    projects = [ProjectItem.model_validate(p) for p in snap_raw.get("projects", [])]
    skills = [SkillItem.model_validate(s) for s in snap_raw.get("skills", [])]
    education = [EducationItem.model_validate(ed) for ed in snap_raw.get("education", [])]
    certifications = [CertificationItem.model_validate(c) for c in snap_raw.get("certifications", [])]

    headline = profile.get("headline", "") if isinstance(profile, dict) else snap_raw.get("headline", "")
    summary = snap_raw.get("customSummary") or (profile.get("summary", "") if isinstance(profile, dict) else snap_raw.get("summary", ""))

    return CandidateEvidence(
        headline=headline or "",
        summary=summary or "",
        experience=experiences,
        projects=projects,
        skills=skills,
        education=education,
        certifications=certifications,
    )


class VariantService:

    @staticmethod
    async def create_targeted_variant(
        user: AuthenticatedUser,
        req: CreateTargetedVariantRequest,
    ) -> TargetedResumeVariant:
        """
        Creates an independent, immutable snapshot fork of a master resume for a specific job target.
        Enforces user ownership and prevents variant-of-variant chaining.
        """
        # 1. Fetch and verify ownership of source master resume
        source_doc = await ResumeService.get_resume_document(user, req.master_resume_id)
        if not source_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Master resume with ID '{req.master_resume_id}' not found or inaccessible.",
            )

        # Prevent variant-of-variant chaining: resolve back to root master resume
        root_master_id = req.master_resume_id
        if source_doc.get("isTargetedVariant") and source_doc.get("masterResumeId"):
            root_master_id = source_doc["masterResumeId"]

        # 2. Extract strongly-typed candidate snapshot
        snapshot_dict = source_doc.get("snapshot") or {}
        candidate_evidence = _parse_candidate_evidence_from_snapshot(snapshot_dict)

        # 3. Derive deterministic job description hash
        jd_hash = hashlib.sha256(req.job_description.strip().encode("utf-8")).hexdigest()

        # 4. Generate stable variant ID
        variant_id = f"var_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Baseline scores and matches from source doc analysis
        baseline_score = source_doc.get("atsScore") or source_doc.get("score")
        baseline_breakdown = source_doc.get("scoreBreakdown")
        analysis_res = source_doc.get("analysisResults") or {}
        raw_matches = analysis_res.get("requirementMatches") or []
        baseline_matches = [
            RequirementMatch.model_validate(m) for m in raw_matches if isinstance(m, dict) and m.get("requirementName")
        ]

        title = f"Targeted: {req.target_role}" + (f" @ {req.target_company}" if req.target_company else "")

        variant = TargetedResumeVariant(
            variant_id=variant_id,
            master_resume_id=root_master_id,
            title=title,
            target_role=req.target_role,
            target_company=req.target_company or "",
            job_description_hash=jd_hash,
            version=1,
            is_targeted_variant=True,
            baseline_score=baseline_score,
            baseline_breakdown=baseline_breakdown,
            baseline_matches=baseline_matches,
            current_score=baseline_score,
            current_breakdown=baseline_breakdown,
            current_matches=baseline_matches,
            score_delta=0 if baseline_score is not None else None,
            snapshot=candidate_evidence,
            change_ledger=[],
            created_at=now_iso,
            updated_at=now_iso,
        )

        # 5. Persist to Firestore under users/{uid}/resumes/{variant_id}
        doc_payload = variant.model_dump(by_alias=True)
        # Also include top-level compatibility fields expected by frontend
        doc_payload["score"] = baseline_score or 0
        doc_payload["atsScore"] = baseline_score or 0
        doc_payload["template"] = source_doc.get("template", "ats")
        doc_payload["lastEdited"] = now_iso

        saved = await ResumeService.save_resume_snapshot(user, variant_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist targeted resume variant to database.",
            )

        return variant

    @staticmethod
    async def get_targeted_variant(
        user: AuthenticatedUser,
        variant_id: str,
    ) -> TargetedResumeVariant:
        """Loads and strongly-types a targeted resume variant owned by the authenticated user."""
        doc = await ResumeService.get_resume_document(user, variant_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Targeted variant '{variant_id}' not found.",
            )
        if not doc.get("isTargetedVariant"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Resume '{variant_id}' is a base resume, not a targeted variant.",
            )

        # Parse snapshot into strongly-typed CandidateEvidence
        doc["snapshot"] = _parse_candidate_evidence_from_snapshot(doc.get("snapshot"))
        return TargetedResumeVariant.model_validate(doc)

    @staticmethod
    async def apply_change_to_variant(
        user: AuthenticatedUser,
        variant_id: str,
        req: ApplyVariantChangeRequest,
    ) -> Tuple[TargetedResumeVariant, ChangeRecord]:
        """
        Applies an approved modification to a targeted resume variant.
        Enforces stable source anchor, increments version (v1 -> v2), and records to change ledger.
        """
        variant = await VariantService.get_targeted_variant(user, variant_id)
        candidate_evidence = variant.snapshot
        now_iso = datetime.now(timezone.utc).isoformat()

        original_text = ""
        target_bullet_idx = req.target_bullet_index

        # 1. Modify Experience or Project in snapshot
        if req.section == "Experience":
            if not candidate_evidence.experience:
                candidate_evidence.experience.append(
                    ExperienceItem(
                        role=variant.target_role or "Software Engineer",
                        company=variant.target_company or "Professional Experience",
                        bullets=[req.approved_bullet],
                    )
                )
                target_bullet_idx = 0
            else:
                exp_item = candidate_evidence.experience[0]
                if target_bullet_idx is not None and target_bullet_idx < len(exp_item.bullets):
                    current_bullet = exp_item.bullets[target_bullet_idx]
                    # Verify source evidence anchor if provided
                    if req.source_evidence_id:
                        expected_id = generate_source_evidence_id(req.section, req.target_item_id, current_bullet)
                        if req.source_evidence_id != expected_id:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail="Stale change: target bullet has been modified since analysis. Please re-analyze before applying.",
                            )
                    original_text = current_bullet
                    exp_item.bullets[target_bullet_idx] = req.approved_bullet
                else:
                    target_bullet_idx = len(exp_item.bullets)
                    exp_item.bullets.append(req.approved_bullet)

        elif req.section == "Project":
            if not candidate_evidence.projects:
                candidate_evidence.projects.append(
                    ProjectItem(
                        title=f"{variant.target_role} Project",
                        highlights=[req.approved_bullet],
                    )
                )
                target_bullet_idx = 0
            else:
                proj_item = candidate_evidence.projects[0]
                if target_bullet_idx is not None and target_bullet_idx < len(proj_item.highlights):
                    original_text = proj_item.highlights[target_bullet_idx]
                    proj_item.highlights[target_bullet_idx] = req.approved_bullet
                else:
                    target_bullet_idx = len(proj_item.highlights)
                    proj_item.highlights.append(req.approved_bullet)

        # 2. Increment Version & Create Change Record
        new_version = variant.version + 1
        change_id = f"chg_{uuid.uuid4().hex[:10]}"

        change_record = ChangeRecord(
            id=change_id,
            remediation_id=req.remediation_id,
            action_type="ApplyRemediation",
            requirement_name=req.requirement_name,
            section=req.section,
            target_item_id=req.target_item_id,
            target_bullet_index=target_bullet_idx,
            original_text=original_text,
            proposed_text=req.approved_bullet,
            approved_text=req.approved_bullet,
            status="Applied",
            version_introduced=new_version,
            applied_at=now_iso,
        )

        variant.version = new_version
        variant.updated_at = now_iso
        variant.change_ledger.append(change_record)

        # 3. Persist updated variant document
        doc_payload = variant.model_dump(by_alias=True)
        doc_payload["lastEdited"] = now_iso
        doc_payload["score"] = variant.current_score or variant.baseline_score or 0
        doc_payload["atsScore"] = variant.current_score or variant.baseline_score or 0

        saved = await ResumeService.save_resume_snapshot(user, variant_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist updated variant to database.",
            )

        return variant, change_record

    @staticmethod
    async def revert_change_on_variant(
        user: AuthenticatedUser,
        variant_id: str,
        change_id: str,
    ) -> RevertChangeResponse:
        """
        Reverts an applied change deterministically and idempotently.
        Restores original evidence text, increments version (v2 -> v3), and preserves full ledger history.
        """
        variant = await VariantService.get_targeted_variant(user, variant_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Find the target change record
        target_change: Optional[ChangeRecord] = None
        for record in variant.change_ledger:
            if record.id == change_id:
                target_change = record
                break

        if not target_change:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Change record '{change_id}' not found in variant change ledger.",
            )

        # Idempotency check
        if target_change.status == "Reverted":
            return RevertChangeResponse(
                success=True,
                variant_id=variant_id,
                change_id=change_id,
                revert_change_id=target_change.reverted_change_id or change_id,
                new_version=variant.version,
                message="Change was already reverted.",
            )

        # 2. Restore the original text in the snapshot
        candidate_evidence = variant.snapshot

        if target_change.section == "Experience" and candidate_evidence.experience:
            exp_item = candidate_evidence.experience[0]
            if target_change.target_bullet_index is not None and target_change.target_bullet_index < len(exp_item.bullets):
                if target_change.original_text:
                    exp_item.bullets[target_change.target_bullet_index] = target_change.original_text
                else:
                    # If this was an added bullet with no original text, remove the appended bullet
                    exp_item.bullets.pop(target_change.target_bullet_index)

        elif target_change.section == "Project" and candidate_evidence.projects:
            proj_item = candidate_evidence.projects[0]
            if target_change.target_bullet_index is not None and target_change.target_bullet_index < len(proj_item.highlights):
                if target_change.original_text:
                    proj_item.highlights[target_change.target_bullet_index] = target_change.original_text
                else:
                    proj_item.highlights.pop(target_change.target_bullet_index)

        # 3. Increment Version and create Revert audit record in ledger
        new_version = variant.version + 1
        revert_record_id = f"rev_{uuid.uuid4().hex[:10]}"

        # Mark original change as Reverted
        target_change.status = "Reverted"
        target_change.version_reverted = new_version
        target_change.reverted_at = now_iso
        target_change.reverted_change_id = revert_record_id

        # Add Revert event record to ledger
        revert_ledger_entry = ChangeRecord(
            id=revert_record_id,
            remediation_id=target_change.remediation_id,
            action_type="RevertChange",
            requirement_name=target_change.requirement_name,
            section=target_change.section,
            target_item_id=target_change.target_item_id,
            target_bullet_index=target_change.target_bullet_index,
            original_text=target_change.approved_text,
            proposed_text=target_change.original_text,
            approved_text=target_change.original_text,
            status="Reverted",
            version_introduced=new_version,
            applied_at=now_iso,
        )

        variant.version = new_version
        variant.updated_at = now_iso
        variant.change_ledger.append(revert_ledger_entry)

        # 4. Persist to Firestore
        doc_payload = variant.model_dump(by_alias=True)
        doc_payload["lastEdited"] = now_iso

        saved = await ResumeService.save_resume_snapshot(user, variant_id, doc_payload)
        if not saved:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist reverted state to database.",
            )

        return RevertChangeResponse(
            success=True,
            variant_id=variant_id,
            change_id=change_id,
            revert_change_id=revert_record_id,
            new_version=new_version,
            message="Change reverted successfully to baseline state.",
        )

    @staticmethod
    async def get_fit_comparison(
        user: AuthenticatedUser,
        variant_id: str,
    ) -> FitComparisonResponse:
        """
        Computes the before / after fit progression from stored baseline & current analysis snapshots.
        Never estimates scores; strictly uses persisted analysis results.
        """
        variant = await VariantService.get_targeted_variant(user, variant_id)

        baseline_score = variant.baseline_score or 0
        current_score = variant.current_score or baseline_score
        score_delta = current_score - baseline_score

        baseline_map = {m.requirement_name.lower(): m for m in variant.baseline_matches}
        current_map = {m.requirement_name.lower(): m for m in variant.current_matches}

        all_req_names = list(set(list(baseline_map.keys()) + list(current_map.keys())))
        progressions: List[RequirementProgression] = []
        resolved_count = 0
        remaining_count = 0

        for r_name in all_req_names:
            b_match = baseline_map.get(r_name)
            c_match = current_map.get(r_name)

            name = c_match.requirement_name if c_match else (b_match.requirement_name if b_match else r_name)
            category = c_match.category if c_match else (b_match.category if b_match else "Other")
            importance = c_match.importance if c_match else (b_match.importance if b_match else "Preferred")
            b_status = b_match.match_status if b_match else "Missing"
            c_status = c_match.match_status if c_match else b_status
            evidence = c_match.resume_evidence if c_match else (b_match.resume_evidence if b_match else "")

            # Deterministic progression classification
            if b_status in ("Missing", "PartialMatch") and c_status == "StrongMatch":
                prog = "Resolved"
                resolved_count += 1
            elif b_status == "Missing" and c_status == "PartialMatch":
                prog = "Improved"
                resolved_count += 1
            elif b_match and b_match.gap_type == "InsufficientExperienceYears":
                prog = "UnresolvedHardGap"
                remaining_count += 1
            elif c_status in ("Missing", "PartialMatch"):
                prog = "Unchanged"
                remaining_count += 1
            else:
                prog = "Unchanged"

            progressions.append(
                RequirementProgression(
                    requirement_name=name,
                    category=category,
                    importance=importance,
                    baseline_status=b_status,
                    current_status=c_status,
                    progression=prog,
                    verified_evidence=evidence,
                )
            )

        from app.schemas.common import ScoreBreakdown
        b_breakdown = variant.baseline_breakdown or ScoreBreakdown(relevance=0, keywords=0, metrics=0, formatting=0)
        c_breakdown = variant.current_breakdown or b_breakdown

        return FitComparisonResponse(
            variant_id=variant_id,
            target_role=variant.target_role,
            target_company=variant.target_company or "",
            baseline_score=baseline_score,
            current_score=current_score,
            score_delta=score_delta,
            baseline_breakdown=b_breakdown,
            current_breakdown=c_breakdown,
            requirement_progressions=progressions,
            total_gaps_resolved=resolved_count,
            total_gaps_remaining=remaining_count,
        )

    @staticmethod
    async def export_targeted_variant_snapshot(
        user: AuthenticatedUser,
        variant_id: str,
        fmt: str = "markdown",
    ) -> ExportTargetedResumeResponse:
        """
        Read-only export generator reading strictly from the stored targeted variant snapshot.
        Guarantees 0 mutations, 0 version increments, and 0 ledger alterations.
        """
        variant = await VariantService.get_targeted_variant(user, variant_id)
        candidate = variant.snapshot
        now_iso = datetime.now(timezone.utc).isoformat()

        if fmt == "json":
            content = candidate.model_dump_json(indent=2)
        elif fmt == "plain_text":
            lines = [
                variant.title,
                f"Target Role: {variant.target_role}" + (f" @ {variant.target_company}" if variant.target_company else ""),
                f"Version: {variant.version} | ATS Score: {variant.current_score or 'Unanalyzed'}",
                "=" * 50,
                "",
            ]
            if candidate.summary:
                lines.extend(["PROFESSIONAL SUMMARY", candidate.summary, ""])
            if candidate.experience:
                lines.append("EXPERIENCE")
                for exp in candidate.experience:
                    lines.append(f"{exp.role} - {exp.company} ({exp.start_date} - {exp.end_date})")
                    for b in exp.bullets:
                        lines.append(f"  • {b}")
                    lines.append("")
            if candidate.projects:
                lines.append("PROJECTS")
                for proj in candidate.projects:
                    lines.append(f"{proj.title}")
                    for hl in proj.highlights:
                        lines.append(f"  • {hl}")
                    lines.append("")
            if candidate.skills:
                lines.append("TECHNICAL SKILLS")
                lines.append(", ".join([s.name for s in candidate.skills]))
                lines.append("")
            content = "\n".join(lines)
        else:
            # Markdown format
            lines = [
                f"# {variant.title}",
                f"**Target Role:** {variant.target_role}" + (f" | **Target Company:** {variant.target_company}" if variant.target_company else ""),
                f"*Version {variant.version} — ATS Readiness Score: {variant.current_score or 'N/A'}%*",
                "",
                "---",
                "",
            ]
            if candidate.summary:
                lines.extend(["## Professional Summary", candidate.summary, ""])
            if candidate.experience:
                lines.append("## Professional Experience")
                for exp in candidate.experience:
                    lines.append(f"### {exp.role} — *{exp.company}*")
                    if exp.start_date or exp.end_date:
                        lines.append(f"*{exp.start_date} – {exp.end_date}*")
                    lines.append("")
                    for b in exp.bullets:
                        lines.append(f"- {b}")
                    lines.append("")
            if candidate.projects:
                lines.append("## Key Projects")
                for proj in candidate.projects:
                    lines.append(f"### {proj.title}")
                    if proj.description:
                        lines.append(f"{proj.description}")
                    for hl in proj.highlights:
                        lines.append(f"- {hl}")
                    lines.append("")
            if candidate.skills:
                lines.append("## Core Technical Competencies")
                lines.append(", ".join([f"`{s.name}`" for s in candidate.skills]))
                lines.append("")

            content = "\n".join(lines)

        return ExportTargetedResumeResponse(
            variant_id=variant_id,
            title=variant.title,
            target_role=variant.target_role,
            target_company=variant.target_company or "",
            version=variant.version,
            format=fmt,
            content=content,
            exported_at=now_iso,
        )
