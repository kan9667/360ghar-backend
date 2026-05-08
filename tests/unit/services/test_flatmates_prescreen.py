from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.flatmates.moderation import (
    apply_listing_prescreen_metadata,
    build_listing_prescreen_result,
)


def _listing(**overrides):
    defaults = {
        "title": "2 BHK in Green Residency",
        "description": "Bright room with shared kitchen and quiet flatmates.",
        "city": "Gurugram",
        "locality": "Sector 45",
        "sub_locality": "Green Residency",
        "monthly_rent": 25000,
        "base_price": 25000,
        "bedrooms": 2,
        "bathrooms": 1,
        "main_image_url": "https://cdn.example.com/room-1.jpg",
        "images": [
            SimpleNamespace(
                id=1,
                image_url="https://cdn.example.com/room-1.jpg",
                display_order=0,
            ),
            SimpleNamespace(
                id=2,
                image_url="https://cdn.example.com/room-2.jpg",
                display_order=1,
            ),
        ],
        "features": ["wifi", "fridge"],
        "tags": [],
        "owner_name": "Asha",
        "search_keywords": None,
        "listing_preferences": {
            "gender_preference": "any",
            "sharing_type": "private_room",
        },
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_prescreen_clear_listing_has_no_flags():
    result = build_listing_prescreen_result(
        _listing(),
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    assert result["prescreen_result"] == "clear"
    assert result["flags"] == []
    assert result["photo_count"] == 2
    assert result["flag_reason"] is None


def test_prescreen_flags_missing_photos_fields_and_zero_price():
    result = build_listing_prescreen_result(
        _listing(
            description="",
            city="",
            locality=None,
            sub_locality=None,
            monthly_rent=0,
            base_price=0,
            images=[],
            main_image_url=None,
            listing_preferences={},
        )
    )

    codes = {flag["code"] for flag in result["flags"]}
    fields = {flag.get("field") for flag in result["flags"]}
    assert result["prescreen_result"] == "flagged"
    assert "missing_photos" in codes
    assert "missing_key_field" in codes
    assert "suspicious_pricing" in codes
    assert {"description", "city", "locality", "sub_locality", "gender_preference"}.issubset(fields)


def test_prescreen_flags_high_and_spammy_content():
    result = build_listing_prescreen_result(
        _listing(
            title="2 BHK casino promo",
            description="Click here for crypto offer before visiting.",
            monthly_rent=1_000_000,
        )
    )

    codes = {flag["code"] for flag in result["flags"]}
    assert "suspicious_pricing" in codes
    assert "commercial_spam" in codes
    assert result["flag_reason"]


def test_apply_prescreen_metadata_persists_preferences():
    listing = _listing(images=[], main_image_url=None)
    result = apply_listing_prescreen_metadata(
        listing,
        admin_user_id=7,
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    preferences = listing.listing_preferences
    assert result["prescreen_result"] == "flagged"
    assert preferences["ai_prescreen_result"] == "flagged"
    assert preferences["ai_prescreen_flags"]
    assert preferences["ai_prescreen_reason"] == result["flag_reason"]
    assert preferences["ai_prescreened_by"] == 7
    assert preferences["ai_prescreened_at"] == "2026-05-07T00:00:00+00:00"
