from __future__ import annotations

import uuid

from aris3_client_sdk.idempotency import new_idempotency_keys


def test_idempotency_keys_format() -> None:
    keys = new_idempotency_keys()
    uuid.UUID(keys.transaction_id)
    uuid.UUID(keys.idempotency_key)
