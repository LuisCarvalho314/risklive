"""© 2025 University of Aberdeen. All rights reserved"""

from __future__ import annotations

from pydantic_ai import Agent

from adapters.llm import build_model
from agents.prompts.report import REPORT_MERGE_PROMPT, REPORT_PROMPT
from agents.prompts.system import SYSTEM_PROMPT
from config.prompts import load_prompts
from models.report import ReportEntry


_REPORT_AGENT: Agent | None = None


def build_report_agent(model_name: str = "gpt-4o", refresh: bool = False) -> Agent:
    global _REPORT_AGENT
    if _REPORT_AGENT is None or refresh:
        model = build_model(model_name)
        _REPORT_AGENT = Agent(
            model,
            instructions=SYSTEM_PROMPT,
            output_type=ReportEntry,
        )
    return _REPORT_AGENT


def reset_report_agent() -> None:
    global _REPORT_AGENT
    _REPORT_AGENT = None


def generate_report_section(text: str, model_name: str = "gpt-4o") -> ReportEntry:
    agent = build_report_agent(model_name)
    prompts = load_prompts()
    report_prompt = prompts.get("REPORT_PROMPT", REPORT_PROMPT)
    return _run_report_prompt(agent, report_prompt, text)


def generate_merged_report_section(text: str, model_name: str = "gpt-4o") -> ReportEntry:
    agent = build_report_agent(model_name)
    prompts = load_prompts()
    report_merge_prompt = prompts.get("REPORT_MERGE_PROMPT", REPORT_MERGE_PROMPT)
    return _run_report_prompt(agent, report_merge_prompt, text)


def _run_report_prompt(agent: Agent, prompt_template: str, text: str) -> ReportEntry:
    prompt = f"{prompt_template}\n\n{text}"
    result = agent.run_sync(prompt)
    return result.output
