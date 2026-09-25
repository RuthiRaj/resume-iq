from typing import Protocol, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from app.schemas.candidate import CandidateEvidence
    from app.schemas.analyze import AnalyzeResponse


class AiAnalyzerProvider(Protocol):
    """Provider-agnostic interface for ATS resume analysis."""

    @property
    def name(self) -> str:
        ...

    async def analyze(
        self,
        target_role: str,
        target_company: Optional[str],
        job_description: str,
        job_description_hash: str,
        candidate_evidence: CandidateEvidence,
    ) -> AnalyzeResponse:
        ...

    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        schema_hint: Optional[str] = None,
    ) -> dict:
        ...
