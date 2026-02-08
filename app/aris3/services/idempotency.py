import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import IdempotencyRecord
from app.aris3.repos.idempotency import IdempotencyRepository


IDEMPOTENCY_HEADER = "Idempotency-Key"


@dataclass
class IdempotencyReplay:
    status_code: int
    response_body: dict


class IdempotencyContext:
    def __init__(self, record: IdempotencyRecord, repo: IdempotencyRepository):
        self._record = record
        self._repo = repo

    def record_success(self, *, status_code: int, response_body: dict) -> None:
        self._record.status_code = status_code
        self._record.response_body = json.dumps(response_body)
        self._record.state = "succeeded"
        self._record.updated_at = datetime.utcnow()
        self._repo.update(self._record)

    def record_failure(self, *, status_code: int, response_body: dict) -> None:
        self._record.status_code = status_code
        self._record.response_body = json.dumps(response_body)
        self._record.state = "failed"
        self._record.updated_at = datetime.utcnow()
        self._repo.update(self._record)


class IdempotencyService:
    def __init__(self, db):
        self.repo = IdempotencyRepository(db)

    @staticmethod
    def fingerprint(payload: object) -> str:
        payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def start(
        self,
        *,
        tenant_id: str,
        endpoint: str,
        method: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[IdempotencyContext | None, IdempotencyReplay | None]:
        existing = self.repo.get_by_key(
            tenant_id=tenant_id,
            endpoint=endpoint,
            method=method,
            idempotency_key=idempotency_key,
        )
        if existing:
            return self._handle_existing(existing, request_hash)

        record = IdempotencyRecord(
            tenant_id=tenant_id,
            endpoint=endpoint,
            method=method,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            state="in_progress",
            status_code=None,
            response_body=None,
        )
        try:
            record = self.repo.create(record)
        except IntegrityError:
            self.repo.db.rollback()
            return self._handle_existing(
                self.repo.get_by_key(
                    tenant_id=tenant_id,
                    endpoint=endpoint,
                    method=method,
                    idempotency_key=idempotency_key,
                ),
                request_hash,
            )

        return IdempotencyContext(record, self.repo), None

    def _handle_existing(
        self, existing: IdempotencyRecord | None, request_hash: str
    ) -> tuple[IdempotencyContext | None, IdempotencyReplay | None]:
        if existing is None:
            raise AppError(ErrorCatalog.IDEMPOTENCY_REQUEST_IN_PROGRESS)
        if existing.request_hash != request_hash:
            raise AppError(ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD)
        if existing.state == "in_progress":
            raise AppError(ErrorCatalog.IDEMPOTENCY_REQUEST_IN_PROGRESS)
        if existing.response_body is None or existing.status_code is None:
            raise AppError(ErrorCatalog.IDEMPOTENCY_REQUEST_IN_PROGRESS)
        response_body = json.loads(existing.response_body)
        return None, IdempotencyReplay(status_code=existing.status_code, response_body=response_body)


def extract_idempotency_key(headers, *, required: bool) -> str | None:
    key = headers.get(IDEMPOTENCY_HEADER)
    if not key and required:
        raise AppError(ErrorCatalog.IDEMPOTENCY_KEY_REQUIRED)
    return key
