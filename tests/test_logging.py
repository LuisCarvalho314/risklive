from __future__ import annotations

from utils.logging import get_logger


def test_get_logger():
    logger = get_logger("name")
    assert logger.name == "name"
