"""Operator-supplied live camera feeds - real access only, never proxied.

OSM's mapped CCTV positions (`ingest/cctv.py`... not yet ported - see
IMPLEMENTATION_TWIN.md) give *where* a camera is, not a video feed: OSM tags
ownership and direction, never a stream URL, and there is no public live CCTV
feed for Hyderabad or Bengaluru (checked while building this - Bengaluru
Traffic Police publish a viewer with no API, GHMC and TS Police publish
nothing). The only way a real stream ever appears here is an operator - GHMC/
Bengaluru ICCC, police, a campus - handing over real access, at which point
it is added as one line to `TWIN_CCTV_STREAMS_FILE`.

**The server never fetches, re-hosts or proxies a stream URL.** This module
only reads the JSON file and returns URLs; the browser loads them directly.
Re-hosting a camera feed would mean this app's own bandwidth and uptime
become a dependency of someone else's CCTV network, for no benefit - the
browser can reach the same URL just as well.

File format - a JSON array, each entry:

    {"id": "ghmc-001", "name": "Necklace Road Jn", "city": "hyderabad",
     "lat": 17.42, "lon": 78.47, "direction": 45,
     "url": "https://.../stream.m3u8", "type": "hls",
     "operator": "GHMC ICCC", "attribution": "GHMC, with permission"}

`type` is one of `hls`, `mjpeg`, `image`. Missing or unreadable file, or an
entry missing `url`/`city`, is skipped - never an error, per the same
"a missing input hides the layer, not the app" rule every adapter follows.
"""

import json
import os

from . import config as twin_config

_CACHE = {'mtime': None, 'rows': None}
VALID_TYPES = ('hls', 'mjpeg', 'image')


def _path():
    return twin_config.CCTV_STREAMS_FILE


def _load():
    path = _path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    if _CACHE['mtime'] != mtime:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                raw = json.load(fh)
        except (OSError, ValueError):
            raw = []
        _CACHE['rows'] = [r for r in raw if isinstance(r, dict) and r.get('url') and r.get('city')]
        _CACHE['mtime'] = mtime
    return _CACHE['rows'] or []


def streams_for_city(city_slug):
    return [r for r in _load() if r.get('city') == city_slug and r.get('type') in VALID_TYPES]


def streams_near(city_slug, lat, lon, radius_m=None):
    """Streams for a city, nearest first, optionally filtered to a radius -

    used by the drawer, which is opened from a specific clicked point.
    """
    from .geo import haversine_m

    rows = streams_for_city(city_slug)
    if lat is None or lon is None:
        return rows

    def distance(row):
        if row.get('lat') is None or row.get('lon') is None:
            return float('inf')
        return haversine_m(lat, lon, row['lat'], row['lon'])

    rows = sorted(rows, key=distance)
    if radius_m is not None:
        rows = [r for r in rows if distance(r) <= radius_m]
    return rows
