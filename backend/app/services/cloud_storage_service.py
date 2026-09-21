"""
Server-side file backup storage via Cloudinary.

WHY THIS EXISTS: the original architecture had the browser upload resume
files directly to Firebase Storage (client-side, via the Firebase JS SDK).
That required Firebase Storage's bucket-level CORS to be configured for
every deployment origin, AND (as of Feb 2026) required upgrading the whole
Firebase project to the Blaze billing plan just to create a Storage bucket
at all -- a real cost/complexity barrier for a project with no other need
for paid Firebase services.

This service instead uploads from the BACKEND, using Cloudinary's free
tier (no credit card required). Two real benefits, not just a 1:1 swap:
  1. The browser never talks to Cloudinary directly for the upload, so
     there's no CORS preflight to configure at all for this operation.
  2. Credentials (API secret) stay server-side; nothing sensitive is ever
     exposed to the client.

CRITICAL DESIGN CONSTRAINT: this is a backup/convenience feature (letting
the user view/download their original file later), NOT part of the core
AI analysis pipeline. The actual parsing (document_extractor.py,
ingestion_parser.py) already works directly off the raw uploaded bytes and
does not depend on this succeeding. Every function here is written to fail
SAFELY: if Cloudinary is unconfigured, down, or errors, ingestion must
still complete and return a usable draft -- just without a file_url. Never
let a backup-storage failure block or fail the actual resume analysis.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_cloudinary_configured = False


def _ensure_cloudinary_configured() -> bool:
    """Lazily configures the Cloudinary SDK on first use. Returns False if not configured."""
    global _cloudinary_configured
    if _cloudinary_configured:
        return True

    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        return False

    try:
        import cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
        _cloudinary_configured = True
        return True
    except ImportError:
        logger.warning(
            "CLOUDINARY_* settings are configured but the 'cloudinary' package "
            "is not installed. Run: pip install cloudinary"
        )
        return False


async def upload_document_backup(
    content: bytes,
    filename: str,
    user_id: str,
) -> Optional[str]:
    """
    Uploads the original resume document to Cloudinary as a raw file backup.
    Returns the secure HTTPS URL on success, or None on ANY failure --
    never raises. Ingestion must proceed regardless of this outcome.
    """
    if not _ensure_cloudinary_configured():
        logger.info(
            "Cloudinary is not configured (CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET "
            "unset) -- skipping document backup upload. Ingestion will proceed "
            "without a stored file_url."
        )
        return None

    try:
        import cloudinary.uploader

        # resource_type="raw" is required for non-image files (PDF/DOCX/TXT).
        # public_id is namespaced per-user to avoid collisions and to mirror
        # the tenant-isolation pattern already used in Firestore/Storage rules.
        safe_public_id = f"resumeiq/{user_id}/{filename}".replace(" ", "_")

        result = cloudinary.uploader.upload(
            content,
            resource_type="raw",
            public_id=safe_public_id,
            overwrite=True,
            timeout=30,
        )
        return result.get("secure_url")
    except Exception as exc:
        # Deliberately broad: a backup-storage failure of ANY kind (network,
        # auth, quota, SDK error) must never surface as an ingestion failure.
        logger.warning(
            "Cloudinary document backup upload failed for user=%s filename=%s: %s. "
            "Ingestion will proceed without a stored file_url.",
            user_id, filename, str(exc),
        )
        return None