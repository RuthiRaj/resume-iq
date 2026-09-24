"""
LLM Evaluation Boundary for ResumeIQ Phase 4.0.2

Defines the interface and offline isolation contracts for LLM-assisted evaluation:
- EvaluationModelProvider (Abstract Protocol)
- OfflineMockEvaluationProvider (Deterministic offline mock)
- Guard: Core evaluation suite runs strictly OFFLINE with 0 external network/API dependencies.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class EvaluationModelProvider(ABC):
    """Abstract interface for optional model-backed evaluation hooks."""
    
    @abstractmethod
    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        schema_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates structured JSON response from prompt."""
        pass


class OfflineMockEvaluationProvider(EvaluationModelProvider):
    """
    Deterministic offline mock provider for testing LLM evaluation flows
    without network calls, API keys, or live external providers.
    """
    
    def __init__(self, predefined_response: Optional[Dict[str, Any]] = None):
        self.predefined_response = predefined_response or {
            "summary": "Tailored candidate summary.",
            "experienceRewrites": [],
            "projectRewrites": [],
        }
        self.call_history = []

    async def generate_json(
        self,
        system_instruction: str,
        user_prompt: str,
        schema_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "system_instruction": system_instruction,
            "user_prompt": user_prompt,
            "schema_hint": schema_hint,
        })
        return self.predefined_response
