import logging

import pytest

from app.aris3.services.spaces_images import SpacesImageService, SpacesImageUploadError


class _FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


class _FakeClientError(Exception):
    def __init__(self, message: str, response: dict):
        super().__init__(message)
        self.response = response


class _FakeS3ClientRaisesClientError:
    def put_object(self, **kwargs):
        raise _FakeClientError(
            "PutObject failed",
            response={"Error": {"Code": "InvalidArgument", "Message": "invalid ACL"}},
        )


def _configure_service(monkeypatch, *, endpoint: str) -> SpacesImageService:
    service = SpacesImageService()
    monkeypatch.setattr(service, "_access_key", "key")
    monkeypatch.setattr(service, "_secret_key", "secret")
    monkeypatch.setattr(service, "_bucket", "bucket")
    monkeypatch.setattr(service, "_region", "nyc3")
    monkeypatch.setattr(service, "_endpoint", endpoint)
    monkeypatch.setattr(service, "_origin_base_url", "https://origin.example.com")
    monkeypatch.setattr(service, "_cdn_base_url", "https://cdn.example.com")
    monkeypatch.setattr(service, "_image_source", "digitalocean_spaces")
    return service


def test_endpoint_host_without_scheme_is_normalized(monkeypatch):
    service = _configure_service(monkeypatch, endpoint="nyc3.digitaloceanspaces.com")

    assert service._normalized_endpoint_url() == "https://nyc3.digitaloceanspaces.com"


def test_endpoint_with_scheme_is_not_duplicated(monkeypatch):
    service = _configure_service(monkeypatch, endpoint="https://nyc3.digitaloceanspaces.com")

    assert service._normalized_endpoint_url() == "https://nyc3.digitaloceanspaces.com"


def test_upload_image_uses_cdn_url_and_expected_s3_args(monkeypatch):
    service = _configure_service(monkeypatch, endpoint="nyc3.digitaloceanspaces.com")

    fake_client = _FakeS3Client()
    monkeypatch.setattr(service, "_build_s3_client", lambda: fake_client)

    result = service.upload_image(
        file_bytes=b"abc",
        original_filename="photo.png",
        content_type="image/png",
        tenant_id="tenant-1",
        store_id="store-1",
        trace_id="trace-123",
    )

    assert result.image_asset_id
    assert result.image_url.startswith("https://cdn.example.com/aris3/images/tenant-1/store-1/")
    assert result.image_thumb_url == result.image_url
    assert result.image_source == "digitalocean_spaces"
    assert result.image_updated_at.endswith("Z")

    assert len(fake_client.calls) == 1
    payload = fake_client.calls[0]
    assert payload["Bucket"] == "bucket"
    assert payload["ACL"] == "public-read"
    assert payload["ContentType"] == "image/png"
    assert payload["CacheControl"] == "public, max-age=31536000"


def test_upload_image_logs_client_error_and_raises_controlled_error(monkeypatch, caplog):
    service = _configure_service(monkeypatch, endpoint="nyc3.digitaloceanspaces.com")
    monkeypatch.setattr(service, "_build_s3_client", lambda: _FakeS3ClientRaisesClientError())
    monkeypatch.setattr(service, "_client_error_types", lambda: (_FakeClientError,))

    caplog.set_level(logging.INFO)

    with pytest.raises(SpacesImageUploadError) as exc_info:
        service.upload_image(
            file_bytes=b"abc",
            original_filename="photo.png",
            content_type="image/png",
            tenant_id="tenant-1",
            store_id="store-1",
            trace_id="trace-123",
        )

    assert exc_info.value.error_code == "STORAGE_ERROR"
    assert "storage upload failed" in str(exc_info.value)
    assert "invalid ACL" in str(exc_info.value)
    assert any(record.message == "spaces_upload_error" for record in caplog.records)


def test_upload_image_rejects_large_payload(monkeypatch):
    service = _configure_service(monkeypatch, endpoint="nyc3.digitaloceanspaces.com")

    with pytest.raises(SpacesImageUploadError) as exc_info:
        service.upload_image(
            file_bytes=b"x" * (10 * 1024 * 1024 + 1),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            tenant_id=None,
            store_id=None,
            trace_id="trace-123",
        )

    assert "max size" in str(exc_info.value)
