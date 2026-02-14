import uuid


class IdempotencyKeyFactory:
    @staticmethod
    def new_key(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4()}"
