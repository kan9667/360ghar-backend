"""Geospatial utility functions."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# City alias mapping — common alternate names for Indian cities.
# Canonical (display) form is the value; alias is the key.
# Used by property search to normalize user input before filtering.
# ---------------------------------------------------------------------------
CITY_ALIASES: dict[str, str] = {
    # Karnataka
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    # Maharashtra
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "pune": "Pune",
    "poona": "Pune",
    "nagpur": "Nagpur",
    # Tamil Nadu
    "madras": "Chennai",
    "chennai": "Chennai",
    # Delhi NCR
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "noida": "Noida",
    "faridabad": "Faridabad",
    "ghaziabad": "Ghaziabad",
    # West Bengal
    "calcutta": "Kolkata",
    "kolkata": "Kolkata",
    # Telangana
    "hyderabad": "Hyderabad",
    # Rajasthan
    "jaipur": "Jaipur",
    "jodhpur": "Jodhpur",
    "udaipur": "Udaipur",
    # Gujarat
    "ahmedabad": "Ahmedabad",
    "ahemdabad": "Ahmedabad",
    "surat": "Surat",
    "vadodara": "Vadodara",
    "baroda": "Vadodara",
    # Uttar Pradesh
    "lucknow": "Lucknow",
    "agra": "Agra",
    "kanpur": "Kanpur",
    "varanasi": "Varanasi",
    "benaras": "Varanasi",
    # Kerala
    "kochi": "Kochi",
    "cochin": "Kochi",
    "trivandrum": "Thiruvananthapuram",
    "thiruvananthapuram": "Thiruvananthapuram",
    # Punjab
    "chandigarh": "Chandigarh",
    "ludhiana": "Ludhiana",
    "amritsar": "Amritsar",
    # Madhya Pradesh
    "bhopal": "Bhopal",
    "indore": "Indore",
    # Goa
    "goa": "Goa",
    "panaji": "Panaji",
    "panjim": "Panaji",
    # Bihar
    "patna": "Patna",
    # Odisha
    "bhubaneswar": "Bhubaneswar",
    # Assam
    "guwahati": "Guwahati",
}


def normalize_city(city: str) -> str:
    """Normalize a city name using the alias map.

    Returns the canonical city name if an alias matches, otherwise
    returns the title-cased input.
    """
    if not city:
        return city
    canonical = CITY_ALIASES.get(city.strip().lower())
    if canonical:
        return canonical
    return city.strip().title()


def city_match_names(city: str) -> list[str]:
    """Return display names that should match a user-supplied city filter.

    Inventory historically stores both common aliases and the canonical form
    (e.g. ``Gurgaon`` and ``Gurugram``). Filtering only on the canonical name
    drops rows stored under an alias. This returns the canonical name plus
    every alias that maps to the same canonical, title-cased for display and
    LOWER()-safe matching.

    Unknown cities return a single title-cased token so free-form input still
    works.
    """
    if not city:
        return []
    stripped = city.strip()
    if not stripped:
        return []

    canonical = normalize_city(stripped)
    names: set[str] = {canonical}
    canonical_lower = canonical.lower()
    for alias, target in CITY_ALIASES.items():
        if target.lower() != canonical_lower:
            continue
        names.add(target)
        # Skip ultra-short aliases (e.g. "ncr") as LIKE tokens — they are too
        # broad as substrings and are already covered by the canonical form
        # for typical inventory (city="Delhi" matches "Delhi NCR" via %delhi%).
        if len(alias) < 4:
            continue
        names.add(alias.title())
    # Preserve a title-cased form of the raw input so odd casing still matches
    # rows that stored the user-facing string literally.
    names.add(stripped.title())
    # Stable order: canonical first, then alphabetical remainder.
    rest = sorted(n for n in names if n.lower() != canonical_lower)
    return [canonical, *rest]


def escape_like_pattern(value: str) -> str:
    """Escape ``%`` and ``_`` for use in SQL LIKE/ILIKE with escape='\\\\'."""
    return value.replace("%", r"\%").replace("_", r"\_")


def wkt_point(longitude: float, latitude: float) -> str:
    """Build a PostGIS WKT POINT string with SRID=4326.

    Args:
        longitude: Longitude in degrees
        latitude: Latitude in degrees

    Returns:
        WKT string like 'SRID=4326;POINT(lon lat)'
    """
    return f"SRID=4326;POINT({longitude} {latitude})"
