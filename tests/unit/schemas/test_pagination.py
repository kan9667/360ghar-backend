from __future__ import annotations

import pytest

from app.core.exceptions import BadRequestException
from app.schemas.pagination import (
    CURSOR_VERSION,
    build_cursor_page,
    decode_cursor,
    encode_cursor,
    keyset_payload,
    offset_payload,
    read_keyset,
    read_offset,
)


def test_encode_decode_roundtrip():
    payload = {"v": CURSOR_VERSION, "o": 40}
    token = encode_cursor(payload)
    assert isinstance(token, str)
    assert "=" not in token  # url-safe, unpadded
    assert decode_cursor(token) == payload


def test_decode_rejects_garbage():
    with pytest.raises(BadRequestException) as exc:
        decode_cursor("!!!not-base64!!!")
    assert exc.value.error_code == "INVALID_CURSOR"


def test_decode_rejects_version_mismatch():
    token = encode_cursor({"v": 999, "o": 0})
    with pytest.raises(BadRequestException) as exc:
        decode_cursor(token)
    assert exc.value.error_code == "INVALID_CURSOR"


def test_keyset_payload_roundtrip():
    p = keyset_payload("2026-06-17T00:00:00Z", 100)
    assert read_keyset(p) == ("2026-06-17T00:00:00Z", 100)


def test_offset_payload_roundtrip():
    assert read_offset(offset_payload(60)) == 60


def test_build_cursor_page_has_more_true_drops_extra():
    # limit=2, but 3 rows were fetched (limit+1) -> has_more, only 2 returned
    rows = [{"id": 3}, {"id": 2}, {"id": 1}]
    page = build_cursor_page(
        rows[:2], limit=2, next_payload=offset_payload(2), total=None
    )
    assert page["has_more"] is True
    assert page["next_cursor"] is not None
    assert page["limit"] == 2
    assert "total" not in page or page["total"] is None
    assert len(page["items"]) == 2


def test_build_cursor_page_end_of_list():
    page = build_cursor_page([{"id": 1}], limit=20, next_payload=None, total=7)
    assert page["has_more"] is False
    assert page["next_cursor"] is None
    assert page["total"] == 7
