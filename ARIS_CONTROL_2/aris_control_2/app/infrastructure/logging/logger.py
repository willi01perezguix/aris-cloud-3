import json
import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def log_action(logger: logging.Logger, module: str, action: str, tenant_id: str | None, trace_id: str | None) -> None:
    logger.info(
        json.dumps(
            {
                "module": module,
                "action": action,
                "effective_tenant_id": tenant_id,
                "trace_id": trace_id,
            }
        )
    )
