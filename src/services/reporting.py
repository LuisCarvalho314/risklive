"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from agents.report.agent import generate_report_section
from models.csv import LLMEnrichedRow
from models.report import ReportEntry
from utils.llm_rate_limit import rate_limit_sleep


def generate_reports(inputs: List[str], model_name: str = "gpt-4o") -> List[ReportEntry]:
    reports: List[ReportEntry] = []
    for text in inputs:
        rate_limit_sleep()
        reports.append(generate_report_section(text, model_name=model_name))
    return reports


def generate_reports_from_rows(
    rows: List[LLMEnrichedRow], model_name: str = "gpt-4o"
) -> List[ReportEntry]:
    grouped: Dict[int, List[LLMEnrichedRow]] = defaultdict(list)
    for row in rows:
        if row.alert_flag != "Red":
            continue
        if row.topic is None:
            continue
        grouped[int(row.topic)].append(row)

    reports: List[ReportEntry] = []
    for topic, group in grouped.items():
        summaries = "\n".join([row.short_summary for row in group if row.short_summary])
        rate_limit_sleep()
        report = generate_report_section(summaries, model_name=model_name)
        report.topic = topic
        reports.append(report)
    return reports
