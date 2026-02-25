from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import uuid

from app.aris3.core.config import settings

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


@dataclass(frozen=True)
class UploadedImageMetadata:
    image_asset_id: str
    image_url: str
    image_thumb_url: str
    image_source: str
    image_updated_at: str


class SpacesImageUploadError(Exception):
    def __init__(self, message: str, *, error_code: str = "BAD_REQUEST") -> None:
        super().__init__(message)
        self.error_code = error_code


class SpacesImageService:
    def __init__(self) -> None:
        self._access_key = settings.ARIS3_SPACES_ACCESS_KEY
        self._secret_key = settings.ARIS3_SPACES_SECRET_KEY
        self._bucket = settings.ARIS3_SPACES_BUCKET
        self._region = settings.ARIS3_SPACES_REGION
        self._endpoint = settings.ARIS3_SPACES_ENDPOINT
        self._origin_base_url = settings.ARIS3_SPACES_ORIGIN_BASE_URL
        self._cdn_base_url = settings.ARIS3_SPACES_CDN_BASE_URL
        self._image_source = settings.ARIS3_IMAGE_SOURCE

    def upload_image(
        self,
        *,
        file_bytes: bytes,
        original_filename: str | None,
        content_type: str | None,
        tenant_id: str | None,
        store_id: str | None,
        trace_id: str | None,
    ) -> UploadedImageMetadata:
        self._validate_settings()
        if not file_bytes:
            raise SpacesImageUploadError("file is required")
        if len(file_bytes) > _MAX_IMAGE_BYTES:
            raise SpacesImageUploadError("image exceeds max size of 10 MB")

        image_asset_id = str(uuid.uuid4())
        extension = self._resolve_extension(original_filename=original_filename, content_type=content_type)
        resolved_content_type = self._resolve_content_type(content_type=content_type, extension=extension)
        key = self._build_object_key(image_asset_id=image_asset_id, tenant_id=tenant_id, store_id=store_id, extension=extension)

        endpoint_url = self._normalized_endpoint_url()
        logger.info(
            "spaces_upload_start",
            extra={
                "bucket": self._bucket,
                "endpoint": endpoint_url,
                "tenant_id": tenant_id,
                "store_id": store_id,
                "trace_id": trace_id,
            },
        )

        client_error_types = self._client_error_types()
        botocore_error_types = self._botocore_error_types()
        client = self._build_s3_client()
        try:
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=file_bytes,
                ACL="public-read",
                ContentType=resolved_content_type,
                CacheControl="public, max-age=31536000",
            )
            logger.info(
                "spaces_upload_ok",
                extra={"key": key, "bytes": len(file_bytes), "trace_id": trace_id},
            )
        except client_error_types as exc:
            s3_response = getattr(exc, "response", {}) or {}
            logger.exception(
                "spaces_upload_error",
                extra={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "s3_error": s3_response.get("Error"),
                    "s3_response_metadata": s3_response.get("ResponseMetadata"),
                    "trace_id": trace_id,
                },
            )
            error_message = (s3_response.get("Error") or {}).get("Message") or str(exc)
            raise SpacesImageUploadError(f"storage upload failed: {error_message}", error_code="STORAGE_ERROR") from exc
        except botocore_error_types as exc:
            logger.exception(
                "spaces_upload_error",
                extra={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "trace_id": trace_id,
                },
            )
            raise SpacesImageUploadError(f"storage upload failed: {str(exc)}", error_code="STORAGE_ERROR") from exc
        except Exception as exc:
            logger.exception(
                "spaces_upload_error",
                extra={
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "trace_id": trace_id,
                },
            )
            raise SpacesImageUploadError("storage upload failed: unexpected error", error_code="STORAGE_ERROR") from exc

        public_base = (self._cdn_base_url or self._origin_base_url).rstrip("/")
        image_url = f"{public_base}/{key}"
        image_updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return UploadedImageMetadata(
            image_asset_id=image_asset_id,
            image_url=image_url,
            image_thumb_url=image_url,
            image_source=self._image_source,
            image_updated_at=image_updated_at,
        )

    def _validate_settings(self) -> None:
        required = {
            "ARIS3_SPACES_ACCESS_KEY": self._access_key,
            "ARIS3_SPACES_SECRET_KEY": self._secret_key,
            "ARIS3_SPACES_BUCKET": self._bucket,
            "ARIS3_SPACES_REGION": self._region,
            "ARIS3_SPACES_ENDPOINT": self._endpoint,
            "ARIS3_SPACES_ORIGIN_BASE_URL": self._origin_base_url,
            "ARIS3_IMAGE_SOURCE": self._image_source,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise SpacesImageUploadError(
                f"missing spaces configuration: {', '.join(missing)}",
                error_code="BAD_REQUEST",
            )

    def _normalized_endpoint_url(self) -> str:
        endpoint = (self._endpoint or "").strip()
        if not endpoint:
            return ""

        parsed = urlparse(endpoint)
        if parsed.scheme:
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        else:
            normalized = f"https://{endpoint.lstrip('/')}".rstrip("/")
        return normalized

    def _build_s3_client(self):
        boto3 = import_module("boto3")
        botocore_client = import_module("botocore.client")
        return boto3.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._normalized_endpoint_url(),
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=botocore_client.Config(signature_version="s3v4"),
        )

    def _client_error_types(self) -> tuple[type[BaseException], ...]:
        try:
            botocore_exceptions = import_module("botocore.exceptions")
            return (botocore_exceptions.ClientError,)
        except Exception:
            return ()

    def _botocore_error_types(self) -> tuple[type[BaseException], ...]:
        try:
            botocore_exceptions = import_module("botocore.exceptions")
            return (botocore_exceptions.BotoCoreError,)
        except Exception:
            return ()

    def _resolve_extension(self, *, original_filename: str | None, content_type: str | None) -> str:
        from_filename = Path(original_filename or "").suffix.lower().lstrip(".")
        if from_filename in _ALLOWED_EXTENSIONS:
            return "jpg" if from_filename == "jpeg" else from_filename

        from_content_type = _CONTENT_TYPE_TO_EXT.get((content_type or "").lower())
        if from_content_type:
            return from_content_type

        raise SpacesImageUploadError("unsupported image extension")

    def _resolve_content_type(self, *, content_type: str | None, extension: str) -> str:
        normalized = (content_type or "").lower()
        if normalized.startswith("image/"):
            return normalized
        guessed = mimetypes.guess_type(f"dummy.{extension}")[0]
        return guessed or "application/octet-stream"

    def _build_object_key(self, *, image_asset_id: str, tenant_id: str | None, store_id: str | None, extension: str) -> str:
        now = datetime.now(timezone.utc)
        safe_tenant_id = (tenant_id or "no-tenant").strip() or "no-tenant"
        safe_store_id = (store_id or "no-store").strip() or "no-store"
        return f"aris3/images/{safe_tenant_id}/{safe_store_id}/{now:%Y}/{now:%m}/{image_asset_id}.{extension}"
