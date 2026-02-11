from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsersListViewModel:
    users: list[dict]
    query: str = ""

    @property
    def filtered(self) -> list[dict]:
        if not self.query:
            return self.users
        query = self.query.lower()
        return [u for u in self.users if query in u.get("username", "").lower() or query in u.get("email", "").lower()]
