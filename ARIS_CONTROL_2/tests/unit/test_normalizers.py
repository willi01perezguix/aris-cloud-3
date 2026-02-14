from clients.aris3_client_sdk.normalizers import normalize_listing


def test_normalize_meta_rows_totals_shape() -> None:
    payload = {
        "meta": {"page": 2, "page_size": 5, "has_next": True},
        "rows": [{"id": 1}],
        "totals": {"total": 15},
    }

    result = normalize_listing(payload)

    assert result["rows"] == [{"id": 1}]
    assert result["page"] == 2
    assert result["page_size"] == 5
    assert result["total"] == 15
    assert result["has_next"] is True


def test_normalize_items_shape() -> None:
    payload = {"items": [{"id": "a"}], "total": 30, "page": 3, "page_size": 10}

    result = normalize_listing(payload)

    assert result["rows"][0]["id"] == "a"
    assert result["page"] == 3
    assert result["page_size"] == 10
    assert result["has_prev"] is True


def test_normalize_direct_list_shape() -> None:
    result = normalize_listing([{"id": "x"}], page=1, page_size=20)

    assert result["rows"] == [{"id": "x"}]
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert result["total"] == 1
