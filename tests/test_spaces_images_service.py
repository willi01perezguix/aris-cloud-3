from app.aris3.services.spaces_images import SpacesImageService, SpacesImageUploadError


class _FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


def test_upload_image_uses_cdn_url_and_expected_s3_args(monkeypatch):
    service = SpacesImageService()
    monkeypatch.setattr(service, "_access_key", "key")
    monkeypatch.setattr(service, "_secret_key", "secret")
    monkeypatch.setattr(service, "_bucket", "bucket")
    monkeypatch.setattr(service, "_region", "nyc3")
    monkeypatch.setattr(service, "_endpoint", "nyc3.digitaloceanspaces.com")
    monkeypatch.setattr(service, "_origin_base_url", "https://origin.example.com")
    monkeypatch.setattr(service, "_cdn_base_url", "https://cdn.example.com")
    monkeypatch.setattr(service, "_image_source", "digitalocean_spaces")

    fake_client = _FakeS3Client()
    monkeypatch.setattr(service, "_build_s3_client", lambda: fake_client)

    result = service.upload_image(
        file_bytes=b"abc",
        original_filename="photo.png",
        content_type="image/png",
        tenant_id="tenant-1",
        store_id="store-1",
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


def test_upload_image_rejects_large_payload(monkeypatch):
    service = SpacesImageService()
    monkeypatch.setattr(service, "_access_key", "key")
    monkeypatch.setattr(service, "_secret_key", "secret")
    monkeypatch.setattr(service, "_bucket", "bucket")
    monkeypatch.setattr(service, "_region", "nyc3")
    monkeypatch.setattr(service, "_endpoint", "nyc3.digitaloceanspaces.com")
    monkeypatch.setattr(service, "_origin_base_url", "https://origin.example.com")
    monkeypatch.setattr(service, "_cdn_base_url", "")
    monkeypatch.setattr(service, "_image_source", "digitalocean_spaces")

    try:
        service.upload_image(
            file_bytes=b"x" * (10 * 1024 * 1024 + 1),
            original_filename="photo.jpg",
            content_type="image/jpeg",
            tenant_id=None,
            store_id=None,
        )
    except SpacesImageUploadError as exc:
        assert "max size" in str(exc)
    else:
        raise AssertionError("expected SpacesImageUploadError")
