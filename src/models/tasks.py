"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


class TaskName(str, Enum):
    save_regular_news = "save_regular_news"
    save_trending_news = "save_trending_news"
    llm_info_extraction = "llm_info_extraction"
    compute_topic_model = "compute_topic_model"
    generate_report = "generate_report"
    export_dashboard = "export_dashboard"
    cleanup = "cleanup"


class TaskRequest(BaseModel):
    task: TaskName
    params: Dict[str, Any] = {}


class TaskResult(BaseModel):
    task: TaskName
    ok: bool
    message: str = ""
    details: Dict[str, Any] = {}
    error: Optional[str] = None
