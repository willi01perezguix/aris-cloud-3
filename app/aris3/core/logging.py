from __future__ import annotations

import json
import logging


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_json(logger: logging.Logger, payload: dict) -> None:
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))

