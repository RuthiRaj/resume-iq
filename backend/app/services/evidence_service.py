import re
from typing import List, Optional, Set
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
    AchievementItem,
    InternshipItem,
    PublicationItem,
    AwardItem,
    VolunteeringItem,
)
from app.schemas.evidence import (
    EvidenceItem,
    EvidenceSourceType,
    VerificationStatus,
    EvidenceProvenanceDetail,
)
from app.ai.grounding import METRIC_PATTERNS
from app.ai.skills import normalize_skill_name, normalize_skill_category
from app.services.resume_service import ResumeService


def extract_metrics_from_text(text: str) -> List[str]:
    """
    Deterministically extracts quantifiable metric substrings (percentages, dollar scale, numbers)
    from candidate evidence text using verified regex patterns.
    """
    if not text:
        return []
    matches = METRIC_PATTERNS.finditer(text)
    metrics: Set[str] = set()
    for m in matches:
        matched_str = m.group(0).strip()
        if matched_str and len(matched_str) > 1:
            metrics.add(matched_str)
    return sorted(list(metrics))


class EvidenceService:
    """
    Evidence Normalization Service for ResumeIQ.
    Converts raw workspace sub-collection items into unified EvidenceItem records
    while strictly preserving source provenance (source_type + source_item_id + source_document_id).
    """

    @classmethod
    def normalize_candidate_evidence(
        cls, user_id: str, evidence: CandidateEvidence
    ) -> List[EvidenceItem]:
        """
        Converts a hydrated CandidateEvidence object into a list of normalized EvidenceItems.
        No LLM hallucinations; 100% deterministic transformation.
        """
        items: List[EvidenceItem] = []

        # 1. Profile / Summary Evidence
        if evidence.summary or evidence.headline:
            summary_metrics = extract_metrics_from_text(f"{evidence.headline} {evidence.summary}")
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_prof_{user_id[:8]}",
                    userId=user_id,
                    sourceType="profile",
                    sourceItemId="profile_main",
                    title=evidence.headline or "Professional Summary",
                    description=evidence.summary,
                    skills=[],
                    technologies=[],
                    responsibilities=[],
                    achievements=[],
                    metrics=summary_metrics,
                    dates="",
                    role=evidence.headline or "",
                    domain="General",
                    sourceDocumentId=None,
                    sourceDocumentName=None,
                    verificationStatus="verified",
                    confidence=0.95,
                )
            )

        # 2. Experience Items
        for idx, exp in enumerate(evidence.experience):
            item_id = exp.id or f"exp_{idx}"
            all_text = f"{exp.company} {exp.role} {' '.join(exp.bullets)} {' '.join(exp.technologies)}"
            metrics = extract_metrics_from_text(all_text)
            norm_techs = [normalize_skill_name(t) for t in exp.technologies if t]

            dates_str = f"{exp.start_date} - {exp.end_date}".strip(" -")
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="experience",
                    sourceItemId=item_id,
                    title=f"{exp.role} at {exp.company}",
                    description="\n".join(exp.bullets),
                    skills=norm_techs,
                    technologies=norm_techs,
                    responsibilities=exp.bullets,
                    achievements=exp.bullets,
                    metrics=metrics,
                    dates=dates_str,
                    role=exp.role,
                    domain="Engineering",
                    sourceDocumentId=exp.source_document_id,
                    sourceDocumentName=exp.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 3. Project Items
        for idx, proj in enumerate(evidence.projects):
            item_id = proj.id or f"proj_{idx}"
            all_text = f"{proj.title} {proj.description} {' '.join(proj.highlights)} {' '.join(proj.tech_stack)}"
            metrics = extract_metrics_from_text(all_text)
            norm_techs = [normalize_skill_name(t) for t in proj.tech_stack if t]

            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="projects",
                    sourceItemId=item_id,
                    title=proj.title,
                    description=proj.description,
                    skills=norm_techs,
                    technologies=norm_techs,
                    responsibilities=proj.highlights,
                    achievements=proj.highlights,
                    metrics=metrics,
                    dates="",
                    role=proj.role or "Creator",
                    domain="Projects",
                    sourceDocumentId=proj.source_document_id,
                    sourceDocumentName=proj.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 4. Skills Items
        for idx, skill in enumerate(evidence.skills):
            item_id = skill.id or f"skill_{idx}"
            norm_name = normalize_skill_name(skill.name)
            norm_cat = normalize_skill_category(norm_name, skill.category or "Other")
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="skills",
                    sourceItemId=item_id,
                    title=norm_name,
                    description=f"{skill.proficiency} proficiency in {norm_name} ({norm_cat})",
                    skills=[norm_name],
                    technologies=[norm_name] if norm_cat in ("Language", "Framework", "Database", "Cloud", "DevOps", "Tool") else [],
                    responsibilities=[],
                    achievements=[],
                    metrics=[],
                    dates="",
                    role="",
                    domain=norm_cat,
                    sourceDocumentId=skill.source_document_id,
                    sourceDocumentName=skill.source_document_name,
                    verificationStatus="verified",
                    confidence=0.85,  # Standalone skill tags have slightly lower depth confidence than narrative evidence
                )
            )

        # 5. Education Items
        for idx, edu in enumerate(evidence.education):
            item_id = edu.id or f"edu_{idx}"
            edu_title = f"{edu.degree} in {edu.field_of_study}" if edu.field_of_study else edu.degree
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="education",
                    sourceItemId=item_id,
                    title=f"{edu_title} at {edu.institution}",
                    description=f"Studied {edu.field_of_study} at {edu.institution}",
                    skills=[normalize_skill_name(edu.field_of_study)] if edu.field_of_study else [],
                    technologies=[],
                    responsibilities=[],
                    achievements=[],
                    metrics=[],
                    dates="",
                    role="Student / Alumnus",
                    domain="Academic",
                    sourceDocumentId=edu.source_document_id,
                    sourceDocumentName=edu.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 6. Certifications
        for idx, cert in enumerate(evidence.certifications):
            item_id = cert.id or f"cert_{idx}"
            cert_name = normalize_skill_name(cert.title)
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="certifications",
                    sourceItemId=item_id,
                    title=f"{cert.title} ({cert.issuer})",
                    description=f"Certified by {cert.issuer}",
                    skills=[cert_name],
                    technologies=[cert_name],
                    responsibilities=[],
                    achievements=[],
                    metrics=[],
                    dates="",
                    role="",
                    domain="Certification",
                    sourceDocumentId=cert.source_document_id,
                    sourceDocumentName=cert.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 7. Achievements
        for idx, ach in enumerate(evidence.achievements):
            item_id = ach.id or f"ach_{idx}"
            all_text = f"{ach.title} {ach.description}"
            metrics = extract_metrics_from_text(all_text)

            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="achievements",
                    sourceItemId=item_id,
                    title=ach.title,
                    description=ach.description or "",
                    skills=[],
                    technologies=[],
                    responsibilities=[],
                    achievements=[ach.title, ach.description] if ach.description else [ach.title],
                    metrics=metrics,
                    dates=ach.date or "",
                    role="",
                    domain="Achievement",
                    sourceDocumentId=ach.source_document_id,
                    sourceDocumentName=ach.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 8. Internships
        for idx, intern in enumerate(evidence.internships):
            item_id = intern.id or f"intern_{idx}"
            all_text = f"{intern.company} {intern.role} {' '.join(intern.bullets)} {' '.join(intern.technologies)}"
            metrics = extract_metrics_from_text(all_text)
            norm_techs = [normalize_skill_name(t) for t in intern.technologies if t]
            dates_str = f"{intern.start_date} - {intern.end_date}".strip(" -")

            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="internships",
                    sourceItemId=item_id,
                    title=f"Internship: {intern.role} at {intern.company}",
                    description="\n".join(intern.bullets),
                    skills=norm_techs,
                    technologies=norm_techs,
                    responsibilities=intern.bullets,
                    achievements=intern.bullets,
                    metrics=metrics,
                    dates=dates_str,
                    role=intern.role,
                    domain="Engineering",
                    sourceDocumentId=intern.source_document_id,
                    sourceDocumentName=intern.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 9. Publications
        for idx, pub in enumerate(evidence.publications):
            item_id = pub.id or f"pub_{idx}"
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="publications",
                    sourceItemId=item_id,
                    title=pub.title,
                    description=f"{pub.publisher} ({pub.publication_date}): {pub.description}".strip(" :"),
                    skills=[],
                    technologies=[],
                    responsibilities=[],
                    achievements=[pub.title],
                    metrics=[],
                    dates=pub.publication_date or "",
                    role="Author",
                    domain="Academic",
                    sourceDocumentId=pub.source_document_id,
                    sourceDocumentName=pub.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 10. Awards
        for idx, award in enumerate(evidence.awards):
            item_id = award.id or f"award_{idx}"
            all_text = f"{award.title} {award.description}"
            metrics = extract_metrics_from_text(all_text)

            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="awards",
                    sourceItemId=item_id,
                    title=f"{award.title} by {award.issuer}" if award.issuer else award.title,
                    description=award.description or "",
                    skills=[],
                    technologies=[],
                    responsibilities=[],
                    achievements=[award.title],
                    metrics=metrics,
                    dates=award.date or "",
                    role="Recipient",
                    domain="Recognition",
                    sourceDocumentId=award.source_document_id,
                    sourceDocumentName=award.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        # 11. Volunteering
        for idx, vol in enumerate(evidence.volunteering):
            item_id = vol.id or f"vol_{idx}"
            dates_str = f"{vol.start_date} - {vol.end_date}".strip(" -")
            items.append(
                EvidenceItem(
                    evidenceId=f"ev_{item_id}",
                    userId=user_id,
                    sourceType="volunteering",
                    sourceItemId=item_id,
                    title=f"{vol.role} at {vol.organization}",
                    description=f"{vol.description} {' '.join(vol.highlights)}".strip(),
                    skills=[],
                    technologies=[],
                    responsibilities=vol.highlights,
                    achievements=vol.highlights,
                    metrics=extract_metrics_from_text(f"{vol.description} {' '.join(vol.highlights)}"),
                    dates=dates_str,
                    role=vol.role,
                    domain="Community",
                    sourceDocumentId=vol.source_document_id,
                    sourceDocumentName=vol.source_document_name,
                    verificationStatus="verified",
                    confidence=1.0,
                )
            )

        return items

    @classmethod
    async def get_user_evidence(cls, user: AuthenticatedUser) -> List[EvidenceItem]:
        """
        Loads the candidate's live master workspace and returns all normalized EvidenceItems.
        Guarantees tenant isolation via user.uid.
        """
        evidence = await ResumeService.get_candidate_resume_data(user, "workspace")
        return cls.normalize_candidate_evidence(user.uid, evidence)

    @classmethod
    async def resolve_evidence_provenance(
        cls, user: AuthenticatedUser, evidence_id: str
    ) -> EvidenceProvenanceDetail:
        """
        Traces a normalized evidence item back to its underlying workspace entity and original
        uploaded document draft with full tenant isolation.
        """
        all_items = await cls.get_user_evidence(user)
        matched = next((it for it in all_items if it.evidence_id == evidence_id), None)
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence item '{evidence_id}' not found in user workspace.",
            )

        draft_status = None
        file_url = None

        if matched.source_document_id:
            try:
                from app.services.ingestion_service import IngestionService
                draft = await IngestionService.get_ingestion_draft(user, matched.source_document_id)
                draft_status = draft.status
                file_url = draft.file_url
            except Exception:
                # Draft may have been removed or unavailable; graceful fallback
                pass

        return EvidenceProvenanceDetail(
            evidence_id=matched.evidence_id,
            user_id=user.uid,
            source_type=matched.source_type,
            source_item_id=matched.source_item_id,
            title=matched.title,
            source_document_id=matched.source_document_id,
            source_document_name=matched.source_document_name,
            ingestion_draft_status=draft_status,
            file_url=file_url,
            verification_status=matched.verification_status,
            confidence=matched.confidence,
        )
