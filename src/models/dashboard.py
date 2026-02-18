from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class AlertItem(BaseModel):
    title: str = ""
    url: Optional[HttpUrl] = None
    description: str = ""
    timestamp: Optional[datetime] = None
    alert_flag: str = ""
    alert_reason: str = ""
    news_category: str = ""
    short_summary: str = ""
    relevance: str = ""

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


class AlertsSection(BaseModel):
    nuclear: List[AlertItem] = Field(default_factory=list)
    non_nuclear: Dict[str, List[AlertItem]] = Field(default_factory=dict)


class RecentAlerts(BaseModel):
    red: List[AlertItem] = Field(default_factory=list)
    yellow: List[AlertItem] = Field(default_factory=list)
    green: List[AlertItem] = Field(default_factory=list)


class FlaggedAlerts(BaseModel):
    red: List[AlertItem] = Field(default_factory=list)
    yellow: List[AlertItem] = Field(default_factory=list)


class TreemapNode(BaseModel):
    name: str
    value: float | int | None = None
    children: List["TreemapNode"] = Field(default_factory=list)
    meta: Dict[str, Any] | None = None


class TopicEntry(BaseModel):
    keyword: str = ""
    response: str = ""


class DashboardModel(BaseModel):
    generated_at: datetime
    alerts: AlertsSection
    recent_alerts: RecentAlerts
    flagged_alerts: FlaggedAlerts
    newsmap: TreemapNode
    topics: List[TopicEntry] = Field(default_factory=list)
    topic_tree: str = ""
