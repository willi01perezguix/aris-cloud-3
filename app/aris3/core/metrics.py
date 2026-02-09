from __future__ import annotations

from dataclasses import dataclass

from app.aris3.core.config import settings

try:
    from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
    from prometheus_client.exposition import CONTENT_TYPE_LATEST
except ImportError:  # pragma: no cover - optional dependency
    CollectorRegistry = None
    Counter = None
    Histogram = None
    generate_latest = None
    CONTENT_TYPE_LATEST = "text/plain"


@dataclass
class MetricsSnapshot:
    content: bytes
    content_type: str


class Metrics:
    def __init__(self) -> None:
        self.enabled = bool(settings.METRICS_ENABLED and CollectorRegistry)
        self._registry = None
        self._http_requests_total = None
        self._http_request_duration_ms = None
        self._idempotency_replay_total = None
        self._lock_wait_timeout_total = None
        self._rbac_denied_total = None
        self._invariants_violation_total = None
        if self.enabled:
            self._initialize_registry()

    def _initialize_registry(self) -> None:
        self._registry = CollectorRegistry()
        self._http_requests_total = Counter(
            "http_requests_total",
            "HTTP requests by route/method/status.",
            ["route", "method", "status"],
            registry=self._registry,
        )
        self._http_request_duration_ms = Histogram(
            "http_request_duration_ms",
            "HTTP request latency in milliseconds.",
            ["route", "method", "status"],
            buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
            registry=self._registry,
        )
        self._idempotency_replay_total = Counter(
            "idempotency_replay_total",
            "Idempotent replay responses.",
            registry=self._registry,
        )
        self._lock_wait_timeout_total = Counter(
            "lock_wait_timeout_total",
            "Lock wait timeout occurrences.",
            registry=self._registry,
        )
        self._rbac_denied_total = Counter(
            "rbac_denied_total",
            "RBAC permission denied decisions.",
            registry=self._registry,
        )
        self._invariants_violation_total = Counter(
            "invariants_violation_total",
            "Integrity invariant violations.",
            ["check_id"],
            registry=self._registry,
        )

    def reset(self) -> None:
        if not self.enabled:
            return
        self._initialize_registry()

    def record_http_request(self, *, route: str, method: str, status_code: int, latency_ms: float) -> None:
        if not self.enabled:
            return
        labels = {"route": route, "method": method, "status": str(status_code)}
        self._http_requests_total.labels(**labels).inc()
        self._http_request_duration_ms.labels(**labels).observe(latency_ms)

    def increment_idempotency_replay(self) -> None:
        if not self.enabled:
            return
        self._idempotency_replay_total.inc()

    def increment_lock_wait_timeout(self) -> None:
        if not self.enabled:
            return
        self._lock_wait_timeout_total.inc()

    def increment_rbac_denied(self) -> None:
        if not self.enabled:
            return
        self._rbac_denied_total.inc()

    def increment_invariant_violation(self, check_id: str, count: int = 1) -> None:
        if not self.enabled:
            return
        self._invariants_violation_total.labels(check_id=check_id).inc(count)

    def render(self) -> MetricsSnapshot:
        if not self.enabled or not generate_latest:
            return MetricsSnapshot(content=b"metrics_disabled\n", content_type="text/plain")
        return MetricsSnapshot(content=generate_latest(self._registry), content_type=CONTENT_TYPE_LATEST)


metrics = Metrics()

