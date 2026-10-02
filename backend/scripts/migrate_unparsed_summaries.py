"""
Dry-Run Migration Script for Unparsed Resume Summaries in Firestore.

By default, dry_run is True:
- Iterates over all users in Firestore.
- Identifies documents where the summary contains raw document header dumps or trailing section delimiters.
- Performs deterministic parsing on the rawText.
- Prints exact BEFORE and AFTER field comparison for each affected document.
- WRITES NOTHING (no mutations or deletions).
"""

import os
import re
import sys
from typing import Dict, Any, Optional

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai.ingestion_parser import _deterministic_parse_resume_text


# Regex identifying legacy raw unparsed text dumped into summary
RAW_HEADER_PATTERN = re.compile(
    r"^(?:[^\n]+\n){0,3}(?:[A-Z\s]{4,30}\n)?(?:\+?\d{7,}|\b\w+@\w+\.\w+\b|SUMMARY\b|EDUCATION\b|EXPERIENCE\b)",
    re.IGNORECASE,
)


def run_summary_migration(dry_run: bool = True, target_uids: Optional[list] = None) -> Dict[str, Any]:
    """
    Executes dry-run audit and migration proposal across Firestore users.
    """
    from app.core.config import settings
    project_id = settings.FIREBASE_PROJECT_ID or "resumeiq-3cfe6"

    try:
        from google.cloud import firestore
        db = firestore.Client(project=project_id)
    except Exception as e:
        print(f"[Notice: GCP Cloud Client Auth ({e}) - Using configured project {project_id}]")
        db = None

    print("=" * 80)
    print(f"RESUMEIQ SUMMARY MIGRATION AUDIT (DRY_RUN = {dry_run})")
    print("=" * 80)

    users_ref = db.collection("users")
    user_docs = users_ref.stream()

    affected_reports = []

    for user_doc in user_docs:
        uid = user_doc.id
        if target_uids and uid not in target_uids:
            continue

        # Inspect subcollections: documents and profile
        docs_ref = db.collection("users").document(uid).collection("documents")
        for doc in docs_ref.stream():
            doc_data = doc.to_dict() or {}
            parsed_content = doc_data.get("parsedContent") or {}
            current_summary = parsed_content.get("summary") or doc_data.get("summary") or ""
            raw_text = doc_data.get("rawText") or ""

            # Check if summary has raw header signature or trailing section markers
            is_unparsed_dump = bool(
                current_summary
                and (
                    RAW_HEADER_PATTERN.search(current_summary)
                    or "EDUCATION" in current_summary
                    or "SUMMARY\n" in current_summary
                    or re.search(r"\b[\w.-]+@[\w.-]+\.\w+\b", current_summary)
                )
            )

            if is_unparsed_dump and raw_text:
                reparsed = _deterministic_parse_resume_text(raw_text)
                
                report = {
                    "uid": uid,
                    "doc_id": doc.id,
                    "doc_name": doc_data.get("fileName") or doc_data.get("title") or "Unnamed Document",
                    "before": {
                        "summary": current_summary,
                        "education_count": len(parsed_content.get("education") or []),
                        "experience_count": len(parsed_content.get("experience") or []),
                        "skills_count": len(parsed_content.get("skills") or []),
                    },
                    "after": {
                        "summary": reparsed.profile.summary,
                        "education_count": len(reparsed.evidence.education),
                        "experience_count": len(reparsed.evidence.experience),
                        "skills_count": len(reparsed.evidence.skills),
                        "candidate_name": reparsed.profile.full_name,
                        "candidate_email": reparsed.profile.email,
                    },
                }
                affected_reports.append(report)

                print(f"\n[AFFECTED ACCOUNT FOUND]")
                print(f"  User UID : {uid}")
                print(f"  Doc ID   : {doc.id} ({report['doc_name']})")
                print("-" * 80)
                print("  BEFORE Summary Snippet:")
                print(f"    {repr(current_summary[:180])}...")
                print(f"    Sections populated: education={report['before']['education_count']}, experience={report['before']['experience_count']}, skills={report['before']['skills_count']}")
                print("-" * 80)
                print("  AFTER (Proposed Clean Summary):")
                print(f"    {repr(reparsed.profile.summary)}")
                print(f"    Extracted Contact : Name='{reparsed.profile.full_name}', Email='{reparsed.profile.email}', Phone='{reparsed.profile.phone}'")
                print(f"    Sections Preserved: education={report['after']['education_count']}, experience={report['after']['experience_count']}, skills={report['after']['skills_count']}")
                print("-" * 80)

                if not dry_run:
                    print(f"  [WRITING UPDATE] Updating document {doc.id}...")
                    doc.reference.update({
                        "parsedContent.summary": reparsed.profile.summary,
                        "parsedContent.education": [e.model_dump() for e in reparsed.evidence.education],
                        "parsedContent.experience": [e.model_dump() for e in reparsed.evidence.experience],
                        "parsedContent.skills": [s.model_dump() for s in reparsed.evidence.skills],
                        "parsedContent.projects": [p.model_dump() for p in reparsed.evidence.projects],
                    })
                else:
                    print("  [DRY RUN] No writes performed.")

    print("\n" + "=" * 80)
    print(f"MIGRATION AUDIT COMPLETE. Total affected documents: {len(affected_reports)}")
    print("=" * 80)

    return {"affected_count": len(affected_reports), "reports": affected_reports}


if __name__ == "__main__":
    # Default is dry_run = True
    run_summary_migration(dry_run=True)
