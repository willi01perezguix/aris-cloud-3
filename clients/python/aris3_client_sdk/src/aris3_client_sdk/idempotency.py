from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class IdempotencyKeys:
    transaction_id: str
    idempotency_key: str


def new_idempotency_keys() -> IdempotencyKeys:
    return IdempotencyKeys(transaction_id=str(uuid.uuid4()), idempotency_key=str(uuid.uuid4()))
