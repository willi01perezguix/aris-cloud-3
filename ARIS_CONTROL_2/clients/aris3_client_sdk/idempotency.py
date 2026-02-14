from __future__ import annotations

import uuid


def generate_idempotency_key() -> str:
    return str(uuid.uuid4())


def build_idempotency_headers(idempotency_key: str) -> dict[str, str]:
    return {
        "Idempotency-Key": idempotency_key,
        "X-Idempotency-Key": idempotency_key,
    }
