"""Geospatial utility functions."""


def wkt_point(longitude: float, latitude: float) -> str:
    """Build a PostGIS WKT POINT string with SRID=4326.

    Args:
        longitude: Longitude in degrees
        latitude: Latitude in degrees

    Returns:
        WKT string like 'SRID=4326;POINT(lon lat)'
    """
    return f"SRID=4326;POINT({longitude} {latitude})"
