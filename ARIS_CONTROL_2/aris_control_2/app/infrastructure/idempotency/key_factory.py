import uuid


class IdempotencyKeyFactory:
    @staticmethod
    def new_key(prefix: str) -> str:
        normalized = prefix.strip().lower().replace(" ", "-")
        return f"{normalized}-{uuid.uuid4()}"
