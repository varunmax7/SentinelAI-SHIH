"""Street-level imagery near a point - the honest proxy for 'what does this
camera see'.

OpenStreetMap does not host camera feeds, and Sentinel never proxies a
third-party stream. What open data *can* give you is the nearest public
street-level photograph whose own compass angle points roughly where the camera
points. That is a genuinely useful answer, and it must always be captioned with
its provider and capture date so nobody mistakes a 2019 photo for a live feed.
"""

import math
from concurrent.futures import ThreadPoolExecutor

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

        # Verified directly: at the normal 500-800 m radius, roughly half the
        # cells in both modelled cities come back with zero photos even though
        # a real one exists a little further out. Rather than show "no
        # imagery" for half the city, widen once and let `nearest` carry the
        # honest, larger distance - never silently presented as this exact
        # spot (see routes.py::_view_caption's 'nearest' case).
        #
        # KartaView is NOT re-queried here: its own API hard-caps `radius` at
        # KARTAVIEW_MAX_RADIUS_M (500 m, see `_kartaview`), so a "wider"
        # KartaView call at any radius_m above that clamps to the exact same
        # request already made above - a duplicate round trip for a
        # guaranteed-identical, already-empty result. Only Mapillary's tile
        # fallback actually gains anything from a wider radius, since the
        # z14 tile it reads covers ~1-2 km regardless and the radius is only
        # a post-fetch filter on points already in hand.
        widened = False
        if not images:
            widened = True
            # Two wider rings of legal 500 m KartaView queries, since KartaView
            # cannot be asked for a bigger radius directly. Measured on five
            # Hyderabad cells that returned nothing at all from the close ring:
            # four of the five found real photographs 1.3-2.6 km out, in 1-2 s.
            # Whatever comes back carries its true distance into the caption
            # (routes.py::_view_caption's 'nearest' case), so a photo 2 km away
            # is never presented as a picture of this spot.
            images += _kartaview_wide(self, lat, lon)
            # Mapillary is queried too and costs nothing while its token is
            # unscoped; it is the source that would actually fill these gaps
            # properly if the token were fixed.
            images += _mapillary(self, lat, lon, twin_config.STREETVIEW_FALLBACK_RADIUS_M)

        for image in live:
            # Distance from the point the operator clicked, not from the anchor
            # the search used - otherwise a city-anchored webcam would claim to
            # be at the city centre no matter which cell is open.
            image['distance_m'] = round(haversine_m(lat, lon, image['lat'], image['lon']), 1)
            image['city_level'] = city_lat is not None
        live.sort(key=lambda i: i['distance_m'])

        if not images:
            return {'images': [], 'facing': None, 'nearest': None, 'live': live,
                    'widened': widened}

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
            'widened': widened,
        }


def _kartaview(adapter, lat, lon, radius_m):
    """KartaView around a point, sampled as a small ring rather than one call.

    KartaView's API hard-caps `radius` at 500 m (KARTAVIEW_MAX_RADIUS_M), which
    is smaller than an H3 res-8 cell is wide, so a single centre query leaves a
    large share of cells with no photograph of their own - and a cell with no
    photograph of its own falls back to the city webcam, which is the same
    picture in every cell. That is exactly the "why is every location showing
    me the same image" failure.

    Measured directly on 24 random Hyderabad cells:

        single 500 m query   14/24 cells had a photo, median 1 photo
        5-point ring         19/24 cells had a photo, median 5 photos

    The ring is four offsets at STREETVIEW_RING_STEP_M around the centre,
    queried in parallel and de-duplicated by image id. Each call is still a
    legal 500 m query; together they cover roughly a 900 m box. Results are
    cached for a day by the adapter, so a cell pays this once.
    """
    points = _ring_points(lat, lon, twin_config.STREETVIEW_RING_POINTS,
                          twin_config.STREETVIEW_RING_STEP_M)

    rows = []
    if len(points) == 1:
        rows = _kartaview_at(adapter, points[0][0], points[0][1], radius_m)
    else:
        with ThreadPoolExecutor(max_workers=len(points)) as pool:
            for chunk in pool.map(
                    lambda p: _kartaview_at(adapter, p[0], p[1], radius_m), points):
                rows.extend(chunk)

    seen, out = set(), []
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        out.append(row)
    return out


def _kartaview_wide(adapter, lat, lon):
    """The widened search: rings at two larger radii, de-duplicated.

    Only reached when the close ring found nothing, and only ever labelled
    `widened` so the caller captions the real distance.
    """
    points = []
    for step in twin_config.STREETVIEW_WIDE_RING_STEPS_M:
        points += _ring_points(lat, lon,
                               twin_config.STREETVIEW_WIDE_RING_POINTS + 1, step)[1:]
    if not points:
        return []

    rows = []
    with ThreadPoolExecutor(max_workers=min(12, len(points))) as pool:
        for chunk in pool.map(
                lambda p: _kartaview_at(adapter, p[0], p[1], KARTAVIEW_MAX_RADIUS_M), points):
            rows.extend(chunk)

    seen, out = set(), []
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        out.append(row)
    return out


def _ring_points(lat, lon, count, step_m):
    """The centre, plus `count - 1` offsets evenly spaced around it.

    Longitude is scaled by cos(latitude) so the ring is round on the ground
    rather than an ellipse stretched east-west.
    """
    points = [(lat, lon)]
    extra = max(0, int(count) - 1)
    if not extra or step_m <= 0:
        return points
    d_lat = step_m / 111000.0
    cos_lat = max(0.2, math.cos(math.radians(lat)))
    for i in range(extra):
        bearing = math.radians(360.0 * i / extra)
        points.append((lat + d_lat * math.cos(bearing),
                       lon + (d_lat * math.sin(bearing)) / cos_lat))
    return points


def _kartaview_at(adapter, lat, lon, radius_m):
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
    out = []
    # Mapillary takes a bbox, not a radius. ~111 km per degree of latitude.
    delta = radius_m / 111000.0
    try:
        payload = adapter.get_json(MAPILLARY_URL, params={
            'access_token': token,
            'fields': 'id,thumb_1024_url,compass_angle,captured_at,geometry',
            'bbox': '%f,%f,%f,%f' % (lon - delta, lat - delta, lon + delta, lat + delta),
            'limit': 20,
        })
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
    except Exception:  # noqa: BLE001
        pass

    if out:
        return out

    # The bbox search above reliably returns zero rows for both modelled
    # cities even well within its own size limit - verified directly, see
    # mapillary_tiles.py's module docstring. Fall back to the same vector
    # tiles Mapillary's own web app reads from, filtered back down to the
    # requested radius (a tile covers ~1-2 km at z14, wider than most calls
    # here ask for).
    try:
        from .mapillary_tiles import fetch_tile_images
        for row in fetch_tile_images(lat, lon):
            if haversine_m(lat, lon, row['lat'], row['lon']) <= radius_m:
                out.append(row)
    except Exception:  # noqa: BLE001
        pass
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
                # `categories` is what tells two webcams published under the
                # same bare title apart - both Hyderabad cams are titled just
                # "Hyderabad" and stand on the same rooftop, so coordinates
                # cannot separate them but "Indoor" can.
                'include': 'images,location,urls,categories',
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
            'category': next((c.get('name') for c in (row.get('categories') or [])
                              if c.get('name')), None),
            'live': True,
        })
    return out


def _to_float(value):
    try:
        return float(value) % 360.0
    except (TypeError, ValueError):
        return None
