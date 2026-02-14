import json
import logging

from aris_control_2.app.infrastructure.logging.logger import log_action


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def test_log_action_contains_required_fields_and_no_secrets() -> None:
    logger = logging.getLogger("aris_control_2.test.obs")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    handler = CaptureHandler()
    logger.addHandler(handler)

    log_action(
        logger=logger,
        module="users",
        action="create",
        actor_role="ADMIN",
        tenant_id="tenant-a",
        trace_id="trace-obs-1",
        outcome="success",
    )

    assert len(handler.messages) == 1
    payload = json.loads(handler.messages[0])
    for key in ["ts", "level", "module", "action", "actor_role", "effective_tenant_id", "trace_id", "outcome"]:
        assert key in payload

    serialized = handler.messages[0].lower()
    assert "password" not in serialized
    assert "access_token" not in serialized
