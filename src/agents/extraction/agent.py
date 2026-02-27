from __future__ import annotations

from pydantic_ai import Agent

from adapters.llm import build_model
from agents.prompts.extraction import EXTRACTION_PROMPT
from agents.prompts.system import SYSTEM_PROMPT
from config.prompts import load_prompts
from models.extraction import ExtractionRecord, ExtractionResult, LLMCallMetrics, TokenUsage
from utils.pricing import estimate_price_usd


_EXTRACTION_AGENT: Agent | None = None


def build_extraction_agent(model_name: str = "gpt-4o", refresh: bool = False) -> Agent:
    global _EXTRACTION_AGENT
    if _EXTRACTION_AGENT is None or refresh:
        model = build_model(model_name)
        _EXTRACTION_AGENT = Agent(
            model,
            instructions=SYSTEM_PROMPT,
            output_type=ExtractionResult,
        )
    return _EXTRACTION_AGENT


def reset_extraction_agent() -> None:
    global _EXTRACTION_AGENT
    _EXTRACTION_AGENT = None


def extract(text: str, model_name: str = "gpt-4o") -> ExtractionResult:
    agent = build_extraction_agent(model_name)
    prompts = load_prompts()
    extraction_prompt = prompts.get("EXTRACTION_PROMPT", EXTRACTION_PROMPT)
    prompt = f"{extraction_prompt}\n\n{text}"
    result = agent.run_sync(prompt)
    return result.output


def extract_record(text: str, model_name: str = "gpt-4o") -> ExtractionRecord:
    agent = build_extraction_agent(model_name)
    prompts = load_prompts()
    extraction_prompt = prompts.get("EXTRACTION_PROMPT", EXTRACTION_PROMPT)
    prompt = f"{extraction_prompt}\n\n{text}"
    run = agent.run_sync(prompt)
    output = run.output
    usage = getattr(run.response, "usage", None)
    token_usage = None
    if usage is not None:
        token_usage = TokenUsage(
            prompt_tokens=getattr(usage, "input_tokens", 0),
            completion_tokens=getattr(usage, "response_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )
    metrics = LLMCallMetrics(
        model=model_name,
        price_usd=estimate_price_usd(model_name, token_usage),
        token_usage=token_usage,
    )
    return ExtractionRecord(input_text=text, result=run.output, metrics=metrics)
