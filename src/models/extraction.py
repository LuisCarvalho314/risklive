from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Relevance(str, Enum):
    yes = "Yes"
    no = "No"
    unknown = ""


class AlertFlag(str, Enum):
    red = "Red"
    yellow = "Yellow"
    green = "Green"
    none = ""


class ExtractionResult(BaseModel):
    relevant_keywords: List[str] = Field(default_factory=list)
    short_summary: str = ""
    relevance: Relevance = Relevance.unknown
    relevance_reason: str = ""
    alert_flag: AlertFlag = AlertFlag.none
    alert_reason: str = ""
    news_category: str = ""


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMCallMetrics(BaseModel):
    model: str = ""
    price_usd: float | None = None
    token_usage: Optional[TokenUsage] = None


class ExtractionRecord(BaseModel):
    input_text: str
    result: ExtractionResult | None = None
    metrics: LLMCallMetrics | None = None
