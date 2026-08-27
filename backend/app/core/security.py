import re
import hashlib
from typing import Dict, Any


def hash_job_description(job_description: str) -> str:
    """Generates a standard SHA-256 hash of normalized job description."""
    normalized = job_description.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_error_message(status_code: int, raw_error: str) -> str:
    """Sanitizes upstream error messages to prevent leaking stack traces or internal secrets."""
    if status_code == 429 or "429" in raw_error or "rate limit" in raw_error.lower():
        return "AI analysis rate limit reached. Please wait a moment before analyzing again."
    if status_code == 503 or "503" in raw_error:
        return "AI analysis service is temporarily unavailable."
    if status_code == 404:
        return "The requested resource was not found or is inaccessible."
    if status_code == 401:
        return "Unauthorized access. Please sign in to continue."
    return "An error occurred while processing your request. Please try again."
