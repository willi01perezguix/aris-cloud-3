from __future__ import annotations

from dataclasses import dataclass

from .auth import AuthClient
from .health import HealthClient


@dataclass
class SmokeResult:
    health: dict
    me: dict | None


class SmokeClient:
    def __init__(self, auth_client: AuthClient, health_client: HealthClient) -> None:
        self.auth_client = auth_client
        self.health_client = health_client

    def check(self, include_me: bool = True) -> SmokeResult:
        health = self.health_client.health()
        me = None
        if include_me:
            me = self.auth_client.me().model_dump()
        return SmokeResult(health=health, me=me)
