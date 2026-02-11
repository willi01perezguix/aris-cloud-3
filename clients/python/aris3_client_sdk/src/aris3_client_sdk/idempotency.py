from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class IdempotencyKeys:
    transaction_id: str
    idempotency_key: str


def new_idempotency_keys() -> IdempotencyKeys:
    return IdempotencyKeys(transaction_id=str(uuid.uuid4()), idempotency_key=str(uuid.uuid4()))


def resolve_idempotency_keys(transaction_id: str | None = None, idempotency_key: str | None = None) -> IdempotencyKeys:
    generated = new_idempotency_keys()
    return IdempotencyKeys(
        transaction_id=transaction_id or generated.transaction_id,
        idempotency_key=idempotency_key or generated.idempotency_key,
    )


def idempotency_headers(keys: IdempotencyKeys) -> dict[str, str]:
    return {"Idempotency-Key": keys.idempotency_key}
