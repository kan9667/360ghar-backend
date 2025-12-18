from app.core.cache import PropertyCacheManager
from app.schemas.property import SortBy


def test_property_cache_key_is_stable_for_filter_order() -> None:
    filters_a = {
        "city": "Gurgaon",
        "purpose": "rent",
        "price_min": 10000,
        "sort_by": SortBy.newest,
    }
    filters_b = {
        "sort_by": SortBy.newest,
        "price_min": 10000,
        "purpose": "rent",
        "city": "Gurgaon",
    }

    key_a = PropertyCacheManager.generate_cache_key(filters_a, user_id=0, page=1, limit=20)
    key_b = PropertyCacheManager.generate_cache_key(filters_b, user_id=0, page=1, limit=20)

    assert key_a == key_b


def test_property_cache_key_changes_with_user_and_pagination() -> None:
    filters = {"city": "Gurgaon", "purpose": "rent"}

    k1 = PropertyCacheManager.generate_cache_key(filters, user_id=0, page=1, limit=20)
    k2 = PropertyCacheManager.generate_cache_key(filters, user_id=1, page=1, limit=20)
    k3 = PropertyCacheManager.generate_cache_key(filters, user_id=0, page=2, limit=20)
    k4 = PropertyCacheManager.generate_cache_key(filters, user_id=0, page=1, limit=10)

    assert k1 != k2
    assert k1 != k3
    assert k1 != k4

