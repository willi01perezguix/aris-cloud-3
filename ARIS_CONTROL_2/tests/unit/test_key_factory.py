from aris_control_2.app.infrastructure.idempotency.key_factory import IdempotencyKeyFactory


def test_key_factory_stable_prefix_timestamp_nonce() -> None:
    key = IdempotencyKeyFactory.new_key("Create User")

    assert key.startswith("aris2-create-user-")
    assert len(key.split("-")) >= 5
