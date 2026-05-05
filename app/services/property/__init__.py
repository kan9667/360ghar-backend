"""Property service package — re-exports all public symbols for backward compatibility.

All public functions from the original ``app.services.property`` module are available
here so that existing ``from app.services.property import X`` statements continue
to work unchanged.
"""

from app.services.property.crud import (
    create_property,
    delete_property,
    get_all_amenities,
    get_property,
    increment_property_view_count,
    list_user_properties,
    update_property,
)
from app.services.property.helpers import (
    _validate_listing_contract,
    build_location_wkt,
)
from app.services.property.recommendations import get_property_recommendations
from app.services.property.search import (
    TEXT_WEIGHT,
    VECTOR_WEIGHT,
    get_unified_properties_optimized,
    property_embeddings_table,
)

__all__ = [
    # CRUD
    "create_property",
    "delete_property",
    "get_all_amenities",
    "get_property",
    "increment_property_view_count",
    "list_user_properties",
    "update_property",
    # Search
    "get_unified_properties_optimized",
    "property_embeddings_table",
    "VECTOR_WEIGHT",
    "TEXT_WEIGHT",
    # Recommendations
    "get_property_recommendations",
    # Helpers
    "_validate_listing_contract",
    "build_location_wkt",
]
