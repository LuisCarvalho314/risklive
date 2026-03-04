"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, HttpUrl


class ArticleSource(str, Enum):
    valyu = "valyu"
    unknown = "unknown"


class Article(BaseModel):
    title: str = ""
    url: Optional[HttpUrl] = None
    description: str = ""
    timestamp: datetime | None = None
    query: str | None = None
    publication_date: str | None = None
    source_price: float | None = None
    source: ArticleSource = ArticleSource.unknown
    metadata: Dict[str, Any] = Field(default_factory=dict)
