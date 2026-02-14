from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory


def test_idempotency_key_factory_normalizes_prefix() -> None:
    key = IdempotencyKeyFactory.new_key("Create User")

    assert key.startswith("create-user-")
    assert len(key.split("-")) >= 6
