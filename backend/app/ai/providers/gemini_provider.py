import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import (
    AnalyzeResponse,
    ScoreBreakdown,
    SkillMatchItem,
    SkillMissingItem,
    SkillPartialItem,
    AnalysisMetadata,
)


class GeminiAnalyzerProvider:
    @property
    def name(self) -> str:
        return "gemini"

    async def analyze(
        self,
        target_role: str,
        target_company: Optional[str],
        job_description: str,
        job_description_hash: str,
        candidate_evidence: CandidateEvidence,
    ) -> AnalyzeResponse:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key.strip() in ("", "your_server_side_gemini_api_key_here"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GEMINI_API_KEY is not configured on the backend server.",
            )

        model_name = settings.AI_ANALYZER_MODEL or "gemini-3.6-flash"

        ai = genai.Client(api_key=api_key)

        company_str = f" at {target_company}" if target_company else ""
        prompt = f"""You are a Senior Principal Technical Recruiter and ATS (Applicant Tracking System) Evaluation Engine.
Your task is to analyze the candidate's resume evidence against the provided Job Description for the target role: "{target_role}"{company_str}.

CRITICAL EVIDENCE RULES (STRICT NON-NEGOTIABLE CONSTRAINT):
1. Evaluate ONLY the evidence explicitly contained in the supplied Resume Evidence below.
2. DO NOT hallucinate, assume, or invent candidate experience, skills, achievements, metrics, or technologies.
3. If a requirement in the Job Description has NO supporting evidence in the resume, you MUST classify it as a missing skill or gap with High or Medium priority.
4. If a requirement is partially mentioned or adjacent, classify it as a partial match with actionable advice.
5. Scores must reflect genuine semantic congruence (0 to 100).
6. Return only valid JSON conforming to the requested schema.

TARGET JOB TITLE: {target_role}
{f"TARGET COMPANY: {target_company}" if target_company else ""}

TARGET JOB DESCRIPTION:
\"\"\"
{job_description}
\"\"\"

CANDIDATE RESUME EVIDENCE:
\"\"\"
{json.dumps(candidate_evidence.model_dump(by_alias=True), indent=2)}
\"\"\"

Evaluate the candidate now and return the structured ATS assessment."""

        gemini_schema = {
            "type": "OBJECT",
            "properties": {
                "atsScore": {
                    "type": "INTEGER",
                    "description": "Overall ATS readiness score between 0 and 100",
                },
                "scoreBreakdown": {
                    "type": "OBJECT",
                    "properties": {
                        "relevance": {"type": "INTEGER", "description": "Role relevance score 0-100"},
                        "keywords": {"type": "INTEGER", "description": "Keyword match score 0-100"},
                        "metrics": {"type": "INTEGER", "description": "Quantifiable metrics score 0-100"},
                        "formatting": {"type": "INTEGER", "description": "Structure score 0-100"},
                    },
                    "required": ["relevance", "keywords", "metrics", "formatting"],
                },
                "summaryFeedback": {
                    "type": "STRING",
                    "description": "2-3 clear sentences summarizing candidate fit and primary improvement areas",
                },
                "matchingSkills": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "context": {"type": "STRING", "description": "Verified section/bullet in resume"},
                        },
                        "required": ["name", "context"],
                    },
                },
                "missingSkills": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "priority": {"type": "STRING", "enum": ["High", "Medium", "Low"]},
                            "reason": {"type": "STRING", "description": "Why this requirement is missing in resume"},
                        },
                        "required": ["name", "priority", "reason"],
                    },
                },
                "partialSkills": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "note": {"type": "STRING", "description": "How to emphasize adjacent skills"},
                        },
                        "required": ["name", "note"],
                    },
                },
            },
            "required": [
                "atsScore",
                "scoreBreakdown",
                "summaryFeedback",
                "matchingSkills",
                "missingSkills",
                "partialSkills",
            ],
        }

        try:
            response = ai.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=gemini_schema,
                    temperature=0.2,
                ),
            )
            response_text = response.text or ""
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "rate limit" in err_str.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI provider rate limit reached. Please wait a moment before analyzing again.",
                )
            if "API key not valid" in err_str or "API_KEY_INVALID" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Invalid Gemini API key configured on the backend server.",
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI analysis service encountered an error processing the request.",
            )

        if not response_text:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider returned an empty response.",
            )

        try:
            parsed = json.loads(response_text)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI provider returned an invalid JSON response format.",
            )

        metadata = AnalysisMetadata(
            provider=self.name,
            model=model_name,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            job_description_hash=job_description_hash,
            target_role=target_role,
            target_company=target_company or "",
        )

        return AnalyzeResponse(
            ats_score=parsed["atsScore"],
            score_breakdown=ScoreBreakdown(
                relevance=parsed["scoreBreakdown"]["relevance"],
                keywords=parsed["scoreBreakdown"]["keywords"],
                metrics=parsed["scoreBreakdown"]["metrics"],
                formatting=parsed["scoreBreakdown"]["formatting"],
            ),
            summary_feedback=parsed["summaryFeedback"],
            matching_skills=[
                SkillMatchItem(name=m["name"], context=m["context"])
                for m in parsed.get("matchingSkills", [])
            ],
            missing_skills=[
                SkillMissingItem(name=m["name"], priority=m["priority"], reason=m["reason"])
                for m in parsed.get("missingSkills", [])
            ],
            partial_skills=[
                SkillPartialItem(name=p["name"], note=p["note"])
                for p in parsed.get("partialSkills", [])
            ],
            metadata=metadata,
        )
