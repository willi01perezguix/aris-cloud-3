from __future__ import annotations

from aris3_client_sdk.image_utils import choose_best_image, placeholder_image_ref, safe_image_url
from aris3_client_sdk.models_media import MediaAsset


def test_safe_image_url_allows_http_https() -> None:
    assert safe_image_url("https://example.com/a.png") == "https://example.com/a.png"
    assert safe_image_url("http://example.com/a.png") == "http://example.com/a.png"
    assert safe_image_url("ftp://example.com/a.png") is None


def test_choose_best_image_prefers_thumb() -> None:
    asset = MediaAsset(url="https://example.com/full.jpg", thumb_url="https://example.com/thumb.jpg")
    assert choose_best_image(asset) == "https://example.com/thumb.jpg"
    assert choose_best_image(asset, prefer_thumb=False) == "https://example.com/full.jpg"


def test_placeholder_image_ref_constant() -> None:
    assert placeholder_image_ref().startswith("placeholder://")
