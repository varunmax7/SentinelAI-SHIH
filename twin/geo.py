"""Small geodesic helpers.

Deliberately dependency-free (no shapely, no pyproj): everything the twin needs
is a handful of formulae on a sphere, and at city scale the error against a
proper ellipsoid is well under a metre.
"""

import math

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def destination(lat, lon, bearing_deg, distance_m):
    """Point `distance_m` away along `bearing_deg`. Returns (lon, lat).

    Returned lon-first because every consumer is GeoJSON.
    """
    d = distance_m / EARTH_RADIUS_M
    br = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(br))
    l2 = l1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return [math.degrees(l2), math.degrees(p2)]


def bearing_delta(a, b):
    """Smallest angle between two compass bearings, 0-180.

    Compare bearings circularly or everything facing north matches nothing:
    |350 - 10| is 340, but the true separation is 20.
    """
    if a is None or b is None:
        return None
    d = abs((a % 360.0) - (b % 360.0))
    return min(d, 360.0 - d)


def bbox_of(points, pad_deg=0.0):
    """(min_lon, min_lat, max_lon, max_lat) over an iterable of (lat, lon)."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return (min(lons) - pad_deg, min(lats) - pad_deg,
            max(lons) + pad_deg, max(lats) + pad_deg)


def point_in_bbox(lat, lon, bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def normalise(value, low, high):
    """Linear 0-100 scale of `value` between `low` and `high`, clamped."""
    if high == low:
        return 0.0
    return clamp((float(value) - low) / (high - low) * 100.0)


def circle_ring(lat, lon, radius_m, segments=32):
    """A closed GeoJSON ring approximating a circle. Used for zone fallbacks."""
    ring = [destination(lat, lon, (360.0 * i) / segments, radius_m)
            for i in range(segments)]
    ring.append(ring[0])
    return ring
