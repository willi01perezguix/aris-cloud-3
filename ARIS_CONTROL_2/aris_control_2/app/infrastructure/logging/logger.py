import json
import logging
from datetime import datetime, timezone


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def log_action(
    logger: logging.Logger,
    module: str,
    action: str,
    actor_role: str | None,
    tenant_id: str | None,
    trace_id: str | None,
    outcome: str,
) -> None:
    logger.info(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "module": module,
                "action": action,
                "actor_role": actor_role,
                "effective_tenant_id": tenant_id,
                "trace_id": trace_id,
                "outcome": outcome,
            }
        )
    )
