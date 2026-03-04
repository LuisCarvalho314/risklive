from __future__ import annotations

import inspect
import json
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type

import langextract as lx
from openai import AzureOpenAI

from config.settings import get_settings


# ----------------------------
# Objects langextract expects
# ----------------------------
@dataclass
class LangExtractExtraction:
    extraction_text: str
    extraction_class: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class LangExtractExample:
    text: str
    extractions: list[LangExtractExtraction]


def load_examples(example_json_path: Path) -> list[LangExtractExample]:
    payload = json.loads(example_json_path.read_text(encoding="utf-8"))
    raw_examples = payload.get("examples", [payload])

    if not isinstance(raw_examples, list):
        raise ValueError("example.json must be an object or {'examples': [...]}")

    examples: list[LangExtractExample] = []
    for index, raw in enumerate(raw_examples):
        if not isinstance(raw, dict):
            raise ValueError(f"Example {index} must be a JSON object")

        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Example {index} missing non-empty 'text'")

        raw_extractions = raw.get("expected_extractions", raw.get("extractions", [])) or []
        if not isinstance(raw_extractions, list):
            raise ValueError(f"Example {index} 'expected_extractions'/'extractions' must be a list")

        extraction_objects: list[LangExtractExtraction] = []
        for j, item in enumerate(raw_extractions):
            if not isinstance(item, dict):
                raise ValueError(f"Example {index} extraction {j} must be an object")

            extraction_class = item.get("type")
            extraction_text = item.get("value")

            if not isinstance(extraction_class, str) or not extraction_class:
                raise ValueError(f"Example {index} extraction {j} missing non-empty 'type' (string)")
            if not isinstance(extraction_text, str) or not extraction_text:
                raise ValueError(f"Example {index} extraction {j} missing non-empty 'value' (string)")

            attributes = {k: v for k, v in item.items() if k not in {"type", "value"}}

            extraction_objects.append(
                LangExtractExtraction(
                    extraction_text=extraction_text,
                    extraction_class=extraction_class,
                    attributes=attributes,
                )
            )

        examples.append(LangExtractExample(text=text, extractions=extraction_objects))

    return examples


def configure_azure_hardcoded() -> dict[str, str]:
    """
    Hardcode ONLY the deployment name here.
    Endpoint + key still come from your settings.
    """
    settings = get_settings()
    azure_cfg = settings.azure_openai_config

    api_key = azure_cfg.api_key.get_secret_value()
    endpoint = azure_cfg.api_base  # e.g. https://<resource>.openai.azure.com
    api_version = getattr(azure_cfg, "api_version", "2024-02-15-preview")

    # ---- HARD-CODE THIS (AZURE DEPLOYMENT NAME) ----
    deployment = "gpt-4o"  # replace with your Azure deployment name if different
    # ------------------------------------------------

    os.environ["AZURE_OPENAI_API_KEY"] = api_key
    os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
    os.environ["AZURE_OPENAI_API_VERSION"] = api_version
    os.environ["AZURE_OPENAI_DEPLOYMENT"] = deployment

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "api_version": api_version,
        "deployment": deployment,
    }


def _find_openai_provider_class(openai_module) -> Type[Any]:
    candidates: list[Type[Any]] = []
    for _, obj in vars(openai_module).items():
        if inspect.isclass(obj) and obj.__module__ == openai_module.__name__:
            if hasattr(obj, "infer") and callable(getattr(obj, "infer")):
                candidates.append(obj)

    if not candidates:
        raise RuntimeError(
            f"No provider-like class found in {openai_module.__name__}. "
            f"Inspect {openai_module.__file__} to find the class name."
        )

    candidates.sort(key=lambda c: ("openai" not in c.__name__.lower(), c.__name__.lower()))
    return candidates[0]


def patch_langextract_openai_provider_to_use_azure() -> str:
    import langextract.providers.openai as lx_openai  # type: ignore

    provider_class = _find_openai_provider_class(lx_openai)
    original_init = provider_class.__init__

    def patched_init(self, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self._client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )

    provider_class.__init__ = patched_init  # type: ignore
    return provider_class.__name__


def main() -> None:
    azure = configure_azure_hardcoded()

    patched_class = patch_langextract_openai_provider_to_use_azure()
    print(f"Patched provider class: {patched_class}")

    examples = load_examples(Path(__file__).with_name("example.json"))

    input_text = textwrap.dedent(
        """\
        A little known security feature on iPhones is in the spotlight after it stymied efforts by U.S. federal authorities to search devices seized from a reporter.

        Apple's Lockdown Mode recently prevented FBI agents from getting into Washington Post reporter Hannah Natanson's iPhone.

        Agents seized the phone, as well as two MacBooks and other electronic devices, when they searched Natanson’s home last month as part of an investigation into a Pentagon contractor accused of illegally handling classified information. But the FBI reported that its Computer Analysis Response Team “could not extract” data from the iPhone because it was in Lockdown Mode, according to a court filing.

        So what is Lockdown Mode? Here's a rundown of how it works and how to use it:
        """
    ).strip()

    prompt_description = "Extract the following information from the text:"

    result = lx.extract(
        text_or_documents=input_text,
        prompt_description=prompt_description,
        examples=examples,
        model_id=azure["deployment"],      # Azure deployment name
        api_key=azure["api_key"],          # required by langextract config validation
        fence_output=True,
        use_schema_constraints=False,
    )

    print(result)


if __name__ == "__main__":
    main()
