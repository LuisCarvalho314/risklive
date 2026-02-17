from __future__ import annotations

from datetime import datetime
import ast
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NewsRow(BaseModel):
    title: str = Field(default="", alias="Title")
    url: Optional[HttpUrl] = Field(default=None, alias="URL")
    description: str = Field(default="", alias="Description")
    timestamp: Optional[datetime] = Field(default=None, alias="Timestamp")
    query: str | None = Field(default=None, alias="Query")

    model_config = {
        "populate_by_name": True,
    }

    @field_validator("url", mode="before")
    @classmethod
    def _empty_url_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "nan"}:
            return None
        return value

    @field_validator("timestamp", mode="before")
    @classmethod
    def _empty_timestamp_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "nan"}:
            return None
        return value


class LLMEnrichedRow(NewsRow):
    llm_response: Any | None = Field(default=None, alias="LLM_Response")
    llm_price: float | None = Field(default=None, alias="LLM_Price")
    llm_token_usage: Any | None = Field(default=None, alias="LLM_Token_Usage")
    prompt_tokens: int | None = Field(default=None, alias="PromptTokens")
    completion_tokens: int | None = Field(default=None, alias="CompletionTokens")
    total_tokens: int | None = Field(default=None, alias="TotalTokens")
    relevant_keywords: List[str] = Field(default_factory=list, alias="RelevantKeywords")
    short_summary: str = Field(default="", alias="ShortSummary")
    relevance: str = Field(default="", alias="Relevance")
    relevance_reason: str = Field(default="", alias="RelevanceReason")
    alert_flag: str = Field(default="", alias="AlertFlag")
    alert_reason: str = Field(default="", alias="AlertReason")
    news_category: str = Field(default="", alias="NewsCategory")
    api_timestamp: str | None = Field(default=None, alias="API_Timestamp")
    topic: int | None = Field(default=None, alias="topic")

    model_config = {
        "populate_by_name": True,
    }

    @field_validator("relevant_keywords", mode="before")
    @classmethod
    def _coerce_keywords(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                for loader in (json.loads, ast.literal_eval):
                    try:
                        parsed = loader(raw)
                    except Exception:
                        continue
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
            if raw.startswith("[") and not raw.endswith("]"):
                raw = raw.lstrip("[").rstrip("]")
            return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]
        return [str(value)]

    @field_validator("llm_price", "prompt_tokens", "completion_tokens", "total_tokens", "topic", mode="before")
    @classmethod
    def _empty_numeric_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "nan"}:
            return None
        return value
