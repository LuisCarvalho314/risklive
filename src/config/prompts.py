from __future__ import annotations

from pathlib import Path
from typing import Dict

from config import settings as settings_module


def load_prompts() -> Dict[str, str]:
    config = settings_module.get_config()
    prompts: Dict[str, str] = {}
    for key, rel_path in config.prompt_paths.items():
        path = Path(rel_path)
        if not path.is_absolute():
            path = settings_module.ROOT_DIR / rel_path
        if path.exists():
            prompts[key] = path.read_text()
    return prompts
