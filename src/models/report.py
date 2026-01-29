from __future__ import annotations

from pydantic import BaseModel

from models.extraction import LLMCallMetrics


class ReportEntry(BaseModel):
    topic: int | str | None = None
    keyword: str = ""
    input_prompt: str = ""
    response: str = ""
    metrics: LLMCallMetrics | None = None
