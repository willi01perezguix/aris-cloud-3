import secrets
from datetime import datetime, timezone


class IdempotencyKeyFactory:
    @staticmethod
    def new_key(prefix: str) -> str:
        normalized = prefix.strip().lower().replace(" ", "-").replace("_", "-")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        nonce = secrets.token_hex(6)
        return f"aris2-{normalized}-{ts}-{nonce}"
