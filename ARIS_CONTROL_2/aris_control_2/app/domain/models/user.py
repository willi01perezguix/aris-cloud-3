from dataclasses import dataclass


@dataclass
class User:
    id: str
    tenant_id: str
    email: str
