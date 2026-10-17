"""Distance and offset calculations on the Earth's surface."""

from math import atan2, cos, pi, radians, sin, sqrt

EARTH_RADIUS_M = 6371000  # mean Earth radius


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points (haversine formula).

    Args:
        lat1, lon1: first point, degrees.
        lat2, lon2: second point, degrees.

    Returns:
        Distance in metres.
    """
    lat1 = radians(float(lat1))
    lon1 = radians(float(lon1))
    lat2 = radians(float(lat2))
    lon2 = radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return c * EARTH_RADIUS_M


def offset_position(lat: float, lon: float,
                    north_m: float, east_m: float) -> tuple[float, float]:
    """Point shifted from (lat, lon) by north_m and east_m metres.

    Flat-Earth approximation, accurate enough for offsets of a few hundred metres.

    Returns:
        Tuple (lat, lon) in degrees.
    """
    m_per_lat_degree = (EARTH_RADIUS_M * pi) / 180
    m_per_lon_degree = m_per_lat_degree * cos(radians(lat))

    return lat + north_m / m_per_lat_degree, lon + east_m / m_per_lon_degree
