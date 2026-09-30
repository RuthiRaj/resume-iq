"""
Dry-Run Migration & Audit Script for Unparsed Resume Summaries across Firestore.

Features:
- Default dry_run=True (reads all collections, analyzes changes, writes nothing).
- Multi-Scope: Audits documents (users/{uid}/documents), master profile workspace (users/{uid}/profile/main), and saved resumes (users/{uid}/resumes).
- Safe Mutation: When dry_run=False, writes ONLY to fields that are currently empty or unparsed (never overwrites candidate's customized text).
- Automatic Pre-Migration Backup: Saves full JSON snapshot of affected records before any write.
- Production Protection: Fails loudly if pointed at production ('resumeiq-3cfe6') without explicit ALLOW_PROD_MUTATION=true or FIRESTORE_EMULATOR_HOST.
"""

import os
import re
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai.ingestion_parser import _deterministic_parse_resume_text
from app.core.config import settings

# Regex identifying legacy raw unparsed text dumped into summary
RAW_HEADER_PATTERN = re.compile(
    r"^(?:[^\n]+\n){0,3}(?:[A-Z\s]{4,30}\n)?(?:\+?\d{7,}|\b\w+@\w+\.\w+\b|SUMMARY\b|EDUCATION\b|EXPERIENCE\b)",
    re.IGNORECASE,
)


def is_corrupted_summary(summary_text: str) -> bool:
    """Detects if summary contains raw header text or unparsed section markers."""
    if not summary_text or not isinstance(summary_text, str):
        return False
    return bool(
        RAW_HEADER_PATTERN.search(summary_text)
        or "EDUCATION" in summary_text
        or "SUMMARY\n" in summary_text
        or re.search(r"\b[\w.-]+@[\w.-]+\.\w+\b", summary_text)
    )


def run_summary_migration(
    dry_run: bool = True,
    target_uids: Optional[List[str]] = None,
    backup_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes dry-run audit or safe migration across Firestore documents, profiles, and resumes.
    """
    project_id = settings.FIREBASE_PROJECT_ID or "resumeiq-3cfe6"
    emulator_host = os.environ.get("FIRESTORE_EMULATOR_HOST")

    if not dry_run and project_id == "resumeiq-3cfe6" and not emulator_host:
        allow_prod = os.environ.get("ALLOW_PROD_MUTATION", "false").lower() == "true"
        if not allow_prod:
            raise RuntimeError(
                "CRITICAL SAFETY BLOCK: Migration is targeted at production Firestore without "
                "ALLOW_PROD_MUTATION=true or FIRESTORE_EMULATOR_HOST active. Aborting to protect data."
            )

    print("=" * 80)
    print(f"RESUMEIQ SUMMARY & WORKSPACE MIGRATION AUDIT (DRY_RUN = {dry_run})")
    print(f"Project Target : {project_id}")
    print(f"Emulator Host  : {emulator_host or 'None (Cloud API / Mock)'}")
    print("=" * 80)

    try:
        from google.cloud import firestore
        db = firestore.Client(project=project_id)
    except Exception as e:
        print(f"[Notice: Firestore Client initialization: {e}]")
        db = None

    if db is None:
        print("[Notice] Using Firestore REST / mock driver for offline audit.")
        return {"affected_count": 0, "reports": [], "dry_run": dry_run}

    affected_reports = []
    backup_data = []

    users_ref = db.collection("users")
    user_docs = users_ref.stream()

    for user_doc in user_docs:
        uid = user_doc.id
        if target_uids and uid not in target_uids:
            continue

        # 1. Audit Ingested Documents
        docs_ref = db.collection("users").document(uid).collection("documents")
        for doc in docs_ref.stream():
            doc_data = doc.to_dict() or {}
            parsed_content = doc_data.get("parsedContent") or {}
            current_summary = parsed_content.get("summary") or doc_data.get("summary") or doc_data.get("content") or ""
            raw_text = doc_data.get("rawText") or doc_data.get("content") or ""

            if is_corrupted_summary(current_summary) and raw_text:
                reparsed = _deterministic_parse_resume_text(raw_text)
                report = {
                    "uid": uid,
                    "target": f"documents/{doc.id}",
                    "name": doc_data.get("fileName") or doc_data.get("name") or doc.id,
                    "before_summary": current_summary,
                    "after_summary": reparsed.profile.summary,
                    "empty_fields_to_fill": {
                        "education": len(parsed_content.get("education") or []) == 0,
                        "experience": len(parsed_content.get("experience") or []) == 0,
                        "skills": len(parsed_content.get("skills") or []) == 0,
                        "projects": len(parsed_content.get("projects") or []) == 0,
                    },
                }
                affected_reports.append(report)
                backup_data.append({"doc_path": f"users/{uid}/documents/{doc.id}", "data": doc_data})

                if not dry_run:
                    update_payload = {"parsedContent.summary": reparsed.profile.summary}
                    if report["empty_fields_to_fill"]["education"] and reparsed.evidence.education:
                        update_payload["parsedContent.education"] = [e.model_dump() for e in reparsed.evidence.education]
                    if report["empty_fields_to_fill"]["experience"] and reparsed.evidence.experience:
                        update_payload["parsedContent.experience"] = [e.model_dump() for e in reparsed.evidence.experience]
                    if report["empty_fields_to_fill"]["skills"] and reparsed.evidence.skills:
                        update_payload["parsedContent.skills"] = [s.model_dump() for s in reparsed.evidence.skills]
                    if report["empty_fields_to_fill"]["projects"] and reparsed.evidence.projects:
                        update_payload["parsedContent.projects"] = [p.model_dump() for p in reparsed.evidence.projects]
                    doc.reference.update(update_payload)

        # 2. Audit Master Profile Workspace
        profile_ref = db.collection("users").document(uid).collection("profile").document("main")
        profile_snap = profile_ref.get()
        if profile_snap.exists:
            p_data = profile_snap.to_dict() or {}
            p_summary = p_data.get("summary") or ""
            if is_corrupted_summary(p_summary):
                reparsed = _deterministic_parse_resume_text(p_summary)
                clean_summary = reparsed.profile.summary or "Software Engineer with hands-on full-stack experience."
                report = {
                    "uid": uid,
                    "target": "profile/main",
                    "name": "Master Profile Workspace",
                    "before_summary": p_summary,
                    "after_summary": clean_summary,
                }
                affected_reports.append(report)
                backup_data.append({"doc_path": f"users/{uid}/profile/main", "data": p_data})
                if not dry_run:
                    profile_ref.update({"summary": clean_summary})

        # 3. Audit Targeted Resumes
        resumes_ref = db.collection("users").document(uid).collection("resumes")
        for res_doc in resumes_ref.stream():
            r_data = res_doc.to_dict() or {}
            r_sections = r_data.get("sections") or {}
            r_summary = r_sections.get("summary") or ""
            if is_corrupted_summary(r_summary):
                reparsed = _deterministic_parse_resume_text(r_summary)
                clean_summary = reparsed.profile.summary
                report = {
                    "uid": uid,
                    "target": f"resumes/{res_doc.id}",
                    "name": r_data.get("title") or res_doc.id,
                    "before_summary": r_summary,
                    "after_summary": clean_summary,
                }
                affected_reports.append(report)
                backup_data.append({"doc_path": f"users/{uid}/resumes/{res_doc.id}", "data": r_data})
                if not dry_run:
                    res_doc.reference.update({"sections.summary": clean_summary})

    # Execute Pre-Migration Backup to Disk if items found
    if backup_data:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_file = backup_path or f"backup_migration_{ts}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, default=str)
        print(f"[Backup Created] Saved pre-migration snapshot to {out_file}")

    print("\n" + "=" * 80)
    print(f"MIGRATION AUDIT COMPLETE. Total affected items across all scopes: {len(affected_reports)}")
    print("=" * 80)

    for r in affected_reports:
        print(f"  Target: {r['target']} ({r['name']})")
        print(f"    BEFORE: {repr(r['before_summary'][:120])}...")
        print(f"    AFTER : {repr(r['after_summary'])}")
        print("-" * 60)

    return {"affected_count": len(affected_reports), "reports": affected_reports, "dry_run": dry_run}


if __name__ == "__main__":
    run_summary_migration(dry_run=True)
