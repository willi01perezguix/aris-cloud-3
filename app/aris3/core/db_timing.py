from __future__ import annotations

from contextvars import ContextVar

_db_time_ms: ContextVar[float | None] = ContextVar("db_time_ms", default=None)


def start_db_timer() -> object:
    return _db_time_ms.set(0.0)


def stop_db_timer(token: object) -> None:
    _db_time_ms.reset(token)


def add_db_time(delta_ms: float) -> None:
    current = _db_time_ms.get()
    if current is None:
        return
    _db_time_ms.set(current + delta_ms)


def get_db_time_ms() -> float | None:
    return _db_time_ms.get()

