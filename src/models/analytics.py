from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["page_view"]
    page_path: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^/",
    )
    session_id: str | None = Field(default=None, max_length=128)
