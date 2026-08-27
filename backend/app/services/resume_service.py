from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from app.core.firebase import get_firestore_client
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
    EducationItem,
    CertificationItem,
)
from app.schemas.analyze import AnalyzeResponse


async def load_master_profile(uid: str) -> CandidateEvidence:
    """Loads the master Career Profile from Firestore subcollections."""
    db = get_firestore_client()
    user_ref = db.collection("users").document(uid)

    profile_snap = user_ref.collection("profile").document("main").get()
    profile_data = profile_snap.to_dict() if profile_snap.exists else {}

    exp_snaps = user_ref.collection("experience").stream()
    experience = [
        ExperienceItem(
            role=d.get("role", ""),
            company=d.get("company", ""),
            location=d.get("location", ""),
            start_date=d.get("startDate", ""),
            end_date="Present" if d.get("isCurrent") else d.get("endDate", ""),
            bullets=d.get("bullets", []),
            technologies=d.get("technologies", []),
        )
        for d in (s.to_dict() for s in exp_snaps)
    ]

    proj_snaps = user_ref.collection("projects").stream()
    projects = [
        ProjectItem(
            title=d.get("title", ""),
            role=d.get("role", ""),
            description=d.get("description", ""),
            highlights=d.get("highlights", []),
            tech_stack=d.get("techStack", []),
        )
        for d in (s.to_dict() for s in proj_snaps)
    ]

    skill_snaps = user_ref.collection("skills").stream()
    skills = [
        SkillItem(
            name=d.get("name", ""),
            category=d.get("category", "Technical"),
            proficiency=d.get("proficiency", "Intermediate"),
        )
        for d in (s.to_dict() for s in skill_snaps)
    ]

    edu_snaps = user_ref.collection("education").stream()
    education = [
        EducationItem(
            degree=d.get("degree", ""),
            institution=d.get("institution", ""),
            field_of_study=d.get("fieldOfStudy", ""),
        )
        for d in (s.to_dict() for s in edu_snaps)
    ]

    cert_snaps = user_ref.collection("certifications").stream()
    certifications = [
        CertificationItem(
            title=d.get("title", ""),
            issuer=d.get("issuer", ""),
        )
        for d in (s.to_dict() for s in cert_snaps)
    ]

    return CandidateEvidence(
        headline=profile_data.get("headline", ""),
        summary=profile_data.get("summary", ""),
        experience=experience,
        projects=projects,
        skills=skills,
        education=education,
        certifications=certifications,
    )


async def get_candidate_resume_data(uid: str, resume_id: str) -> CandidateEvidence:
    """
    Resolves candidate resume evidence strictly from Firestore.
    Prioritizes immutable resume.snapshot; falls back to master profile for legacy resumes.
    """
    if resume_id == "workspace":
        return await load_master_profile(uid)

    db = get_firestore_client()
    resume_doc_ref = db.collection("users").document(uid).collection("resumes").document(resume_id)
    doc_snap = resume_doc_ref.get()

    if not doc_snap.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with ID '{resume_id}' was not found or is inaccessible.",
        )

    resume_data = doc_snap.to_dict() or {}
    snapshot = resume_data.get("snapshot")

    # Priority 1: Immutable Snapshot
    if snapshot:
        profile = snapshot.get("profile", {})
        experiences = [
            ExperienceItem(
                role=e.get("role", ""),
                company=e.get("company", ""),
                location=e.get("location", ""),
                start_date=e.get("startDate", ""),
                end_date="Present" if e.get("isCurrent") else e.get("endDate", ""),
                bullets=e.get("bullets", []),
                technologies=e.get("technologies", []),
            )
            for e in snapshot.get("experience", [])
        ]
        projects = [
            ProjectItem(
                title=p.get("title", ""),
                role=p.get("role", ""),
                description=p.get("description", ""),
                highlights=p.get("highlights", []),
                tech_stack=p.get("techStack", []),
            )
            for p in snapshot.get("projects", [])
        ]
        skills = [
            SkillItem(
                name=s.get("name", ""),
                category=s.get("category", "Technical"),
                proficiency=s.get("proficiency", "Intermediate"),
            )
            for s in snapshot.get("skills", [])
        ]
        education = [
            EducationItem(
                degree=ed.get("degree", ""),
                institution=ed.get("institution", ""),
                field_of_study=ed.get("fieldOfStudy", ""),
            )
            for ed in snapshot.get("education", [])
        ]
        certifications = [
            CertificationItem(
                title=c.get("title", ""),
                issuer=c.get("issuer", ""),
            )
            for c in snapshot.get("certifications", [])
        ]

        return CandidateEvidence(
            headline=profile.get("headline", ""),
            summary=snapshot.get("customSummary") or profile.get("summary", ""),
            experience=experiences,
            projects=projects,
            skills=skills,
            education=education,
            certifications=certifications,
        )

    # Priority 2: Legacy fallback
    return await load_master_profile(uid)


async def persist_analysis_results(
    uid: str, resume_id: str, analysis: AnalyzeResponse
) -> None:
    """Persists analysis results to Firestore document."""
    if resume_id == "workspace":
        return

    db = get_firestore_client()
    resume_doc_ref = db.collection("users").document(uid).collection("resumes").document(resume_id)

    update_payload = {
        "score": analysis.ats_score,
        "atsScore": analysis.ats_score,
        "scoreBreakdown": analysis.score_breakdown.model_dump(by_alias=True),
        "lastAnalyzedAt": analysis.metadata.analyzed_at,
        "targetRole": analysis.metadata.target_role,
        "targetCompany": analysis.metadata.target_company or "",
        "analysisResults": {
            "summaryFeedback": analysis.summary_feedback,
            "matchingSkills": [s.model_dump(by_alias=True) for s in analysis.matching_skills],
            "missingSkills": [s.model_dump(by_alias=True) for s in analysis.missing_skills],
            "partialSkills": [s.model_dump(by_alias=True) for s in analysis.partial_skills],
            "metadata": analysis.metadata.model_dump(by_alias=True),
        },
    }

    resume_doc_ref.update(update_payload)
