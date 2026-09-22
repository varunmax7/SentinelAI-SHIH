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

# api.openstreetcam.org is the pre-rename host. It still resolves but reads time
# out far more often than not, so nearly every cell fell back to "no imagery" and
# showed only the single city webcam. api.kartaview.org is the live endpoint.
KARTAVIEW_URL = 'https://api.kartaview.org/2.0/photo/'
# Hard limit enforced by the API; anything larger is rejected with a 400.
KARTAVIEW_MAX_RADIUS_M = 500
MAPILLARY_URL = 'https://graph.mapillary.com/images'
WINDY_URL = 'https://api.windy.com/webcams/api/v3/webcams'


class StreetViewAdapter(IngestAdapter):
    """Ground-level imagery near a point.

    Returns three things, and the distinction between them is the whole point:

      `live`    - webcams publishing a current still. Genuinely now.
      `facing`  - the nearest archival photo shot roughly along the camera's
                  bearing. The best proxy for "what this camera sees".
      `nearest` - the nearest archival photo in any direction.

    `nearest` exists because `facing` frequently finds nothing: a 45-degree
    tolerance against sparse street-level coverage misses more often than it
    hits, and showing an operator a caption saying "no image found" when there
    is a perfectly good photo of the junction thirty metres away is a worse
    answer than showing the photo and saying which way it looks.
    """

    source_key = 'streetview'
    ttl_seconds = 24 * 3600

    def __init__(self, cache_dir=None, timeout=None):
        # KartaView's own latency swings between ~1s and ~10s for the same
        # point, so the shared 8s budget dropped whole neighbourhoods at random
        # and left the drawer showing only the city webcam. This runs lazily in
        # a drawer, not on the dashboard's critical path, so it can afford to
        # wait.
        super(StreetViewAdapter, self).__init__(
            cache_dir=cache_dir,
            timeout=timeout or twin_config.STREETVIEW_TIMEOUT_S)

    def cache_key(self, lat=None, lon=None, radius_m=None, direction=None,
                  city_lat=None, city_lon=None, **kwargs):
        # NOTE: live frames are re-fetched with force=True by the caller when a
        # current image is wanted; this key only governs the archival lookup.
        # Rounded to ~11 m so two cameras on the same junction share a cache
        # entry instead of each triggering its own provider round trip.
        return super(StreetViewAdapter, self).cache_key(
            lat=round(float(lat), 4) if lat is not None else None,
            lon=round(float(lon), 4) if lon is not None else None,
            radius=radius_m,
            direction=round(float(direction)) if direction is not None else None,
            # The webcam anchor changes the result, so it has to change the key.
            # Leaving it out meant a cell cached before the anchor existed kept
            # serving its old, webcam-less answer for ever.
            anchor=(round(float(city_lat), 3), round(float(city_lon), 3))
                   if city_lat is not None and city_lon is not None else None,
        )

    def fetch(self, lat=None, lon=None, radius_m=None, direction=None,
              tolerance_deg=45.0, city_lat=None, city_lon=None, **kwargs):
        radius_m = radius_m or twin_config.STREETVIEW_RADIUS_M

        # Live webcams are searched around the CITY, not around this point.
        # There are three Windy webcams across both modelled cities, so a
        # point-radius search gives live imagery to a handful of cells and
        # nothing to the other nine hundred. Anchoring the search on the city
        # centre means every cell gets its city's live cameras - they are
        # genuinely live and genuinely this city, they are simply not this
        # hexagon, and the distance shown against each one says so.
        anchor_lat = city_lat if city_lat is not None else lat
        anchor_lon = city_lon if city_lon is not None else lon
        live = _windy_webcams(self, anchor_lat, anchor_lon, twin_config.WEBCAM_RADIUS_M)

        images = []
        # Both providers are queried, always - showing only the first one that
        # answers is what made imagery look inconsistent from cell to cell (D6).
        images += _kartaview(self, lat, lon, radius_m)
        images += _mapillary(self, lat, lon, radius_m)

        for image in live:
            # Distance from the point the operator clicked, not from the anchor
            # the search used - otherwise a city-anchored webcam would claim to
            # be at the city centre no matter which cell is open.
            image['distance_m'] = round(haversine_m(lat, lon, image['lat'], image['lon']), 1)
            image['city_level'] = city_lat is not None
        live.sort(key=lambda i: i['distance_m'])

        if not images:
            return {'images': [], 'facing': None, 'nearest': None, 'live': live}

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

        return {
            'images': images[:12],
            'facing': facing,
            # Always populated when any imagery exists, so the UI never has to
            # show nothing just because the bearing did not line up.
            'nearest': images[0],
            'live': live,
        }


def _kartaview(adapter, lat, lon, radius_m):
    try:
        payload = adapter.get_json(KARTAVIEW_URL, params={
            'lat': lat, 'lng': lon,
            'radius': max(1, min(int(radius_m), KARTAVIEW_MAX_RADIUS_M)),
            'itemsPerPage': 20,
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


def _windy_webcams(adapter, lat, lon, radius_m):
    """Webcams publishing a current image, via Windy Webcams API v3.

    The only genuinely live imagery available here. OpenStreetMap maps camera
    *locations* - not one of Bengaluru's 2,891 mapped cameras carries a
    `contact:webcam` tag - so without a Windy key there is no live frame to
    show, and the UI must say that rather than implying otherwise.
    """
    key = twin_config.WINDY_WEBCAMS_KEY
    if not key:
        return []
    try:
        payload = adapter.get_json(
            WINDY_URL,
            params={
                # Windy takes a radius in kilometres, minimum 1.
                'nearby': '%f,%f,%d' % (lat, lon, max(1, int(round(radius_m / 1000.0)))),
                'include': 'images,location,urls',
                'limit': 8,
            },
            headers={'x-windy-api-key': key, 'Accept': 'application/json'},
        )
    except Exception:  # noqa: BLE001 - a keyed source failing loses one panel
        return []

    out = []
    for row in (payload.get('webcams') or []):
        location = row.get('location') or {}
        images = (row.get('images') or {}).get('current') or {}
        preview = images.get('preview') or images.get('thumbnail')
        if not preview or location.get('latitude') is None:
            continue
        out.append({
            'provider': 'Windy Webcams',
            'licence': 'per Windy terms',
            'id': row.get('webcamId') or row.get('id'),
            'lat': location['latitude'],
            'lon': location['longitude'],
            'heading': None,
            'title': row.get('title'),
            # Windy publishes the capture time; without it we must not claim
            # the frame is current.
            'captured_at': row.get('lastUpdatedOn'),
            'thumb_url': preview,
            'full_url': images.get('preview') or preview,
            'page_url': (row.get('urls') or {}).get('detail'),
            'live': True,
        })
    return out


def _to_float(value):
    try:
        return float(value) % 360.0
    except (TypeError, ValueError):
        return None
