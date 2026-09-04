"""Street-level imagery near a point - the honest proxy for 'what does this
camera see'.

OpenStreetMap does not host camera feeds, and Sentinel never proxies a
third-party stream. What open data *can* give you is the nearest public
street-level photograph whose own compass angle points roughly where the camera
points. That is a genuinely useful answer, and it must always be captioned with
its provider and capture date so nobody mistakes a 2019 photo for a live feed.
"""

from .base import IngestAdapter
from .. import config as twin_config
from ..geo import bearing_delta, haversine_m

KARTAVIEW_URL = 'https://api.openstreetcam.org/2.0/photo/'
MAPILLARY_URL = 'https://graph.mapillary.com/images'


class StreetViewAdapter(IngestAdapter):
    source_key = 'streetview'
    ttl_seconds = 24 * 3600

    def fetch(self, lat=None, lon=None, radius_m=None, direction=None,
              tolerance_deg=45.0, **kwargs):
        radius_m = radius_m or twin_config.STREETVIEW_RADIUS_M
        images = []
        # Both providers are queried, always - showing only the first one that
        # answers is what made imagery look inconsistent from cell to cell (D6).
        images += _kartaview(self, lat, lon, radius_m)
        images += _mapillary(self, lat, lon, radius_m)
        if not images:
            return {'images': [], 'facing': None}

        for image in images:
            image['distance_m'] = round(haversine_m(lat, lon, image['lat'], image['lon']), 1)
            image['bearing_delta'] = bearing_delta(direction, image.get('heading'))
        images.sort(key=lambda i: i['distance_m'])

        facing = None
        if direction is not None:
            candidates = [i for i in images
                          if i['bearing_delta'] is not None and i['bearing_delta'] <= tolerance_deg]
            if candidates:
                facing = min(candidates, key=lambda i: i['distance_m'])

        return {'images': images[:12], 'facing': facing}


def _kartaview(adapter, lat, lon, radius_m):
    try:
        payload = adapter.get_json(KARTAVIEW_URL, params={
            'lat': lat, 'lng': lon, 'radius': int(radius_m), 'itemsPerPage': 20,
        })
    except Exception:  # noqa: BLE001 - one provider failing is not an outage
        return []
    rows = ((payload.get('result') or {}).get('data')) or []
    out = []
    for row in rows:
        try:
            out.append({
                'provider': 'KartaView',
                'licence': 'CC BY-SA',
                'id': row.get('id'),
                'lat': float(row.get('lat')),
                'lon': float(row.get('lng')),
                'heading': _to_float(row.get('heading')),
                'captured_at': row.get('shotDate'),
                # fileurlProc is the full processed frame - often 3840 px wide.
                # The drawer renders these in a ~300 px box, so prefer the
                # thumbnail and keep the full frame behind `full_url` for
                # anyone who wants to open it.
                'thumb_url': (row.get('fileurlLTh') or row.get('fileurlTh')
                              or row.get('fileurlProc')),
                'full_url': row.get('fileurlProc'),
                'page_url': 'https://kartaview.org/details/%s' % row.get('sequenceId')
                            if row.get('sequenceId') else None,
                'live': False,
            })
        except (TypeError, ValueError):
            continue
    return out


def _mapillary(adapter, lat, lon, radius_m):
    token = twin_config.MAPILLARY_TOKEN
    if not token:
        return []
    # Mapillary takes a bbox, not a radius. ~111 km per degree of latitude.
    delta = radius_m / 111000.0
    try:
        payload = adapter.get_json(MAPILLARY_URL, params={
            'access_token': token,
            'fields': 'id,thumb_1024_url,compass_angle,captured_at,geometry',
            'bbox': '%f,%f,%f,%f' % (lon - delta, lat - delta, lon + delta, lat + delta),
            'limit': 20,
        })
    except Exception:  # noqa: BLE001
        return []
    out = []
    for row in payload.get('data', []):
        coords = ((row.get('geometry') or {}).get('coordinates')) or []
        if len(coords) != 2:
            continue
        out.append({
            'provider': 'Mapillary',
            'licence': 'CC BY-SA',
            'id': row.get('id'),
            'lat': coords[1],
            'lon': coords[0],
            'heading': _to_float(row.get('compass_angle')),
            'captured_at': row.get('captured_at'),
            'thumb_url': row.get('thumb_1024_url'),
            'full_url': row.get('thumb_1024_url'),
            'page_url': 'https://www.mapillary.com/app/?pKey=%s' % row.get('id'),
            'live': False,
        })
    return out


def _to_float(value):
    try:
        return float(value) % 360.0
    except (TypeError, ValueError):
        return None
