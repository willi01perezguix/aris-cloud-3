class AuthStore:
    def __init__(self) -> None:
        self.token: str | None = None

    def set_token(self, token: str) -> None:
        self.token = token

    def get_token(self) -> str | None:
        return self.token
