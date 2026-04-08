"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from agents.report.agent import generate_merged_report_section, generate_report_section
from models.csv import LLMEnrichedRow
from models.report import ReportEntry
from utils.logging import get_logger
from utils.llm_rate_limit import rate_limit_sleep

logger = get_logger(__name__)

REPORT_CHUNK_CHAR_BUDGET = 4_000
REPORT_CHUNK_SEPARATOR = "\n\n"


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
        chunk_inputs = build_topic_report_chunks(group)
        if not chunk_inputs:
            continue
        report = _generate_topic_report(chunk_inputs, topic=topic, model_name=model_name)
        report.topic = topic
        reports.append(report)
    return reports


def build_topic_report_chunks(
    rows: List[LLMEnrichedRow], char_budget: int | None = None
) -> List[str]:
    if char_budget is None:
        char_budget = REPORT_CHUNK_CHAR_BUDGET
    if char_budget <= len(REPORT_CHUNK_SEPARATOR):
        raise ValueError("char_budget must exceed separator length")

    fragments: List[str] = []
    for row in rows:
        base_text = (row.short_summary or "").strip() or (row.title or "").strip()
        if not base_text:
            continue
        fragments.extend(_split_fragment(base_text, char_budget))

    if not fragments:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for fragment in fragments:
        separator_len = len(REPORT_CHUNK_SEPARATOR) if current else 0
        projected_len = current_len + separator_len + len(fragment)
        if current and projected_len > char_budget:
            chunks.append(REPORT_CHUNK_SEPARATOR.join(current))
            current = [fragment]
            current_len = len(fragment)
            continue
        current.append(fragment)
        current_len = projected_len

    if current:
        chunks.append(REPORT_CHUNK_SEPARATOR.join(current))
    return chunks


def _split_fragment(text: str, char_budget: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= char_budget:
        return [text]

    parts: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + char_budget, len(text))
        if end < len(text):
            split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        part = text[start:end].strip()
        if part:
            parts.append(part)
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return parts


def _generate_topic_report(chunk_inputs: List[str], *, topic: int, model_name: str) -> ReportEntry:
    logger.info(
        "report_topic_chunking",
        extra={
            "event": "report_topic_chunking",
            "component": "services.reporting",
            "operation": "generate_reports_from_rows",
            "topic": topic,
            "chunk_count": len(chunk_inputs),
            "chunk_sizes": [len(chunk) for chunk in chunk_inputs],
        },
    )
    if len(chunk_inputs) == 1:
        rate_limit_sleep()
        return generate_report_section(chunk_inputs[0], model_name=model_name)

    partial_reports: List[ReportEntry] = []
    for chunk_input in chunk_inputs:
        rate_limit_sleep()
        partial_reports.append(generate_report_section(chunk_input, model_name=model_name))

    merge_input = _build_merge_input(partial_reports)
    rate_limit_sleep()
    return generate_merged_report_section(merge_input, model_name=model_name)


def _build_merge_input(partial_reports: List[ReportEntry]) -> str:
    sections: List[str] = []
    for idx, report in enumerate(partial_reports, start=1):
        keyword = (report.keyword or "").strip()
        response = (report.response or "").strip()
        input_prompt = (report.input_prompt or "").strip()
        section_lines = [f"Chunk Report {idx}"]
        if keyword:
            section_lines.append(f"Keyword: {keyword}")
        if input_prompt:
            section_lines.append(f"Input Prompt: {input_prompt}")
        if response:
            section_lines.append("Response:")
            section_lines.append(response)
        sections.append("\n".join(section_lines).strip())
    return f"\n\n{'-' * 40}\n\n".join(sections)
