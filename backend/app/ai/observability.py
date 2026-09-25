"""
Phase 4.0.7: AI Observability & Reliability Metrics.

Internal provider usage and cost estimation is collected solely for engineering observability
and infrastructure optimization. ResumeIQ is a completely free product for users.
This telemetry has no relationship to user billing, subscriptions, credits, entitlements, or feature access.
"""

import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field, ConfigDict, field_validator


# --- 1. Strongly Typed Token & Cost Models ---

class TokenUsage(BaseModel):
    """Accurate token accounting model for AI provider executions."""
    prompt_tokens: int = Field(default=0, ge=0, description="Input/prompt token count")
    completion_tokens: int = Field(default=0, ge=0, description="Output/completion token count")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")

    @field_validator("total_tokens", mode="before")
    @classmethod
    def validate_total(cls, v: Any, info: Any) -> int:
        return max(0, int(v or 0))

    def add(self, other: Optional["TokenUsage"]) -> "TokenUsage":
        """Deterministic sum of two token usages."""
        if other is None:
            return self.model_copy()
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    model_config = ConfigDict(populate_by_name=True)


class CostBreakdown(BaseModel):
    """Deterministic financial cost breakdown for AI provider executions in USD."""
    input_cost_usd: float = Field(default=0.0, ge=0.0, description="Cost of input prompt tokens in USD")
    output_cost_usd: float = Field(default=0.0, ge=0.0, description="Cost of output completion tokens in USD")
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total execution cost in USD")
    pricing_version: str = Field(default="2026.09.v1", description="Pricing registry schema/version identifier")
    pricing_source: str = Field(default="registry", description="'registry' if exact model found, 'fallback' if default rates used")
    is_authoritative: bool = Field(default=True, description="True if rates are verified from provider specs")

    def add(self, other: Optional["CostBreakdown"]) -> "CostBreakdown":
        """Deterministic sum of two cost breakdowns."""
        if other is None:
            return self.model_copy()
        dec_in = Decimal(str(self.input_cost_usd)) + Decimal(str(other.input_cost_usd))
        dec_out = Decimal(str(self.output_cost_usd)) + Decimal(str(other.output_cost_usd))
        dec_tot = Decimal(str(self.total_cost_usd)) + Decimal(str(other.total_cost_usd))
        return CostBreakdown(
            input_cost_usd=float(dec_in.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
            output_cost_usd=float(dec_out.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
            total_cost_usd=float(dec_tot.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
            pricing_version=self.pricing_version,
            pricing_source=self.pricing_source if self.pricing_source == other.pricing_source else "mixed",
            is_authoritative=self.is_authoritative and other.is_authoritative,
        )

    model_config = ConfigDict(populate_by_name=True)


class StageLatency(BaseModel):
    """End-to-end pipeline execution stage latencies in milliseconds."""
    retrieval_ms: float = Field(default=0.0, ge=0.0, description="Candidate evidence extraction & graph build time")
    planning_ms: float = Field(default=0.0, ge=0.0, description="ResumePlan creation & validation time")
    generation_ms: float = Field(default=0.0, ge=0.0, description="LLM provider execution time across attempts")
    validation_ms: float = Field(default=0.0, ge=0.0, description="Grounding & claim validation time")
    total_ms: float = Field(default=0.0, ge=0.0, description="End-to-end request processing time")

    model_config = ConfigDict(populate_by_name=True)


class GroundingMetrics(BaseModel):
    """Observational metrics summarizing ClaimValidator & Grounding decisions."""
    claims_evaluated: int = Field(default=0, ge=0, description="Total individual claims checked against evidence")
    claims_accepted: int = Field(default=0, ge=0, description="Claims passing grounding constraints")
    claims_rejected: int = Field(default=0, ge=0, description="Claims failing grounding constraints")
    bullets_reverted: int = Field(default=0, ge=0, description="Bullets safely reverted to original source text")

    model_config = ConfigDict(populate_by_name=True)


# --- 2. Centralized Model Pricing Registry ---

CURRENT_PRICING_VERSION = "2026.09.v1"

# Pricing table: rates in USD per 1,000,000 tokens (input_rate, output_rate)
MODEL_PRICING_REGISTRY: Dict[Tuple[str, str], Dict[str, Any]] = {
    # Groq Models
    ("groq", "llama-3.3-70b-versatile"): {
        "input_per_1m": Decimal("0.59"),
        "output_per_1m": Decimal("0.79"),
        "is_authoritative": True,
    },
    ("groq", "llama-3.1-70b-versatile"): {
        "input_per_1m": Decimal("0.59"),
        "output_per_1m": Decimal("0.79"),
        "is_authoritative": True,
    },
    ("groq", "llama-3.1-8b-instant"): {
        "input_per_1m": Decimal("0.05"),
        "output_per_1m": Decimal("0.08"),
        "is_authoritative": True,
    },
    # Gemini Models
    ("gemini", "gemini-2.5-flash"): {
        "input_per_1m": Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "is_authoritative": True,
    },
    ("gemini", "gemini-3.6-flash"): {
        "input_per_1m": Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "is_authoritative": True,
    },
    ("gemini", "gemini-1.5-flash"): {
        "input_per_1m": Decimal("0.075"),
        "output_per_1m": Decimal("0.30"),
        "is_authoritative": True,
    },
    ("gemini", "gemini-1.5-pro"): {
        "input_per_1m": Decimal("1.25"),
        "output_per_1m": Decimal("5.00"),
        "is_authoritative": True,
    },
    # NVIDIA NIM Models
    ("nvidia", "meta/llama-3.3-70b-instruct"): {
        "input_per_1m": Decimal("0.70"),
        "output_per_1m": Decimal("0.90"),
        "is_authoritative": True,
    },
    ("nvidia", "meta/llama-3.1-70b-instruct"): {
        "input_per_1m": Decimal("0.70"),
        "output_per_1m": Decimal("0.90"),
        "is_authoritative": True,
    },
}

# Fallback default pricing for unlisted models/providers (explicitly marked non-authoritative)
DEFAULT_FALLBACK_RATES = {
    "input_per_1m": Decimal("0.50"),
    "output_per_1m": Decimal("0.75"),
    "is_authoritative": False,
}


def calculate_token_cost(
    provider_name: str,
    model_name: str,
    usage: Optional[TokenUsage],
    pricing_version: str = CURRENT_PRICING_VERSION,
) -> CostBreakdown:
    """
    Deterministically computes token cost using exact Decimal arithmetic, rounded to 6 decimal places.
    
    Formula:
        input_cost = prompt_tokens / 1,000,000 * input_rate
        output_cost = completion_tokens / 1,000,000 * output_rate
        total_cost = input_cost + output_cost
    """
    if usage is None or not isinstance(usage, TokenUsage) or (usage.prompt_tokens == 0 and usage.completion_tokens == 0):
        return CostBreakdown(
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
            pricing_version=pricing_version,
            pricing_source="registry",
            is_authoritative=True,
        )

    norm_p = (provider_name or "").lower().strip()
    norm_m = (model_name or "").lower().strip()

    rates = MODEL_PRICING_REGISTRY.get((norm_p, norm_m))
    pricing_source = "registry"

    if rates is None:
        # Check by provider default or partial model match
        for (reg_p, reg_m), r_data in MODEL_PRICING_REGISTRY.items():
            if reg_p == norm_p and (reg_m in norm_m or norm_m in reg_m):
                rates = r_data
                pricing_source = "registry"
                break

    if rates is None:
        rates = DEFAULT_FALLBACK_RATES
        pricing_source = "fallback"

    million = Decimal("1000000")
    prompt_dec = Decimal(str(usage.prompt_tokens))
    comp_dec = Decimal(str(usage.completion_tokens))

    input_cost = (prompt_dec / million) * rates["input_per_1m"]
    output_cost = (comp_dec / million) * rates["output_per_1m"]
    total_cost = input_cost + output_cost

    # Quantize to 6 decimal places (micro-USD precision)
    six_places = Decimal("0.000001")
    input_q = input_cost.quantize(six_places, rounding=ROUND_HALF_UP)
    output_q = output_cost.quantize(six_places, rounding=ROUND_HALF_UP)
    total_q = total_cost.quantize(six_places, rounding=ROUND_HALF_UP)

    return CostBreakdown(
        input_cost_usd=float(input_q),
        output_cost_usd=float(output_q),
        total_cost_usd=float(total_q),
        pricing_version=pricing_version,
        pricing_source=pricing_source,
        is_authoritative=rates["is_authoritative"],
    )
