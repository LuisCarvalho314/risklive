from __future__ import annotations

import os
import random
import time

_LAST_CALL_TS = 0.0


def rate_limit_sleep() -> None:
    global _LAST_CALL_TS
    min_interval = float(os.getenv("AZURE_OPENAI_MIN_INTERVAL_SEC", os.getenv("OPENAI_MIN_INTERVAL_SEC", "0")))
    if min_interval <= 0:
        return
    now = time.time()
    remaining = min_interval - (now - _LAST_CALL_TS)
    if remaining > 0:
        time.sleep(remaining + random.uniform(0, min_interval * 0.2))
    _LAST_CALL_TS = time.time()
