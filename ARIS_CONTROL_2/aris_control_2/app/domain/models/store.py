from dataclasses import dataclass


@dataclass
class Store:
    id: str
    tenant_id: str
    name: str
