import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def log_action(logger: logging.Logger, module: str, action: str, tenant_id: str | None, trace_id: str | None) -> None:
    logger.info("module=%s action=%s tenant=%s trace_id=%s", module, action, tenant_id or "-", trace_id or "-")
