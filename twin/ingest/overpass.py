"""OpenStreetMap via Overpass: critical assets, water bodies, storm drains.

Attribution `(c) OpenStreetMap contributors (ODbL)` is a licence condition
wherever any of this is displayed.

These queries are slow (tens of seconds on a city bbox) and the data is close to
static, so the adapters carry long TTLs and are driven from the scheduler, never
from a user request. Routes serve whatever is cached and say so if nothing is.
"""

from .base import IngestAdapter
from .. import config as twin_config

OVERPASS_ENDPOINTS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
)

# Overpass needs real time to answer a city-sized query. This is deliberately
# far above config.HTTP_TIMEOUT_S: these adapters never run on the request path.
OVERPASS_TIMEOUT_S = 90

ASSET_TAGS = [
    ('amenity', 'hospital', 'hospital'),
    ('amenity', 'clinic', 'clinic'),
    ('amenity', 'fire_station', 'fire_station'),
    ('amenity', 'police', 'police'),
    ('amenity', 'school', 'school'),
    ('amenity', 'college', 'college'),
    ('amenity', 'university', 'university'),
    ('amenity', 'shelter', 'shelter'),
    ('railway', 'station', 'railway_station'),
    ('public_transport', 'station', 'metro_station'),
    ('power', 'substation', 'power_substation'),
    ('man_made', 'water_works', 'water_works'),
    ('man_made', 'pumping_station', 'pumping_station'),
]


class _OverpassAdapter(IngestAdapter):
    retries = 1

    def __init__(self, *args, **kwargs):
        super(_OverpassAdapter, self).__init__(*args, **kwargs)
        self.timeout = OVERPASS_TIMEOUT_S

    def query(self, ql):
        last = None
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                return self.post_form(endpoint, {'data': ql})
            except Exception as exc:  # noqa: BLE001 - try the mirror
                last = exc
        raise last

    @staticmethod
    def bbox_clause(bbox):
        """Overpass wants (south,west,north,east); our bboxes are lon-first."""
        min_lon, min_lat, max_lon, max_lat = bbox
        return "%f,%f,%f,%f" % (min_lat, min_lon, max_lat, max_lon)


class AssetsAdapter(_OverpassAdapter):
    source_key = 'overpass_assets'
    ttl_seconds = 7 * 24 * 3600
    stale_grace_seconds = 60 * 24 * 3600

    def fetch(self, bbox=None, **kwargs):
        box = self.bbox_clause(bbox)
        clauses = []
        for key, value, _asset in ASSET_TAGS:
            clauses.append('node["%s"="%s"](%s);' % (key, value, box))
            clauses.append('way["%s"="%s"](%s);' % (key, value, box))
        ql = "[out:json][timeout:%d];(%s);out center tags;" % (
            OVERPASS_TIMEOUT_S - 10, ''.join(clauses))
        payload = self.query(ql)
        return _parse_assets(payload)


def _parse_assets(payload):
    lookup = {(k, v): asset for k, v, asset in ASSET_TAGS}
    out = []
    for element in payload.get('elements', []):
        lat, lon = _element_point(element)
        if lat is None:
            continue
        tags = element.get('tags') or {}
        asset_type = None
        for (key, value), name in lookup.items():
            if tags.get(key) == value:
                asset_type = name
                break
        if asset_type is None:
            continue
        out.append({
            'osm_id': "%s/%s" % (element.get('type'), element.get('id')),
            'asset_type': asset_type,
            'name': tags.get('name') or tags.get('operator'),
            'criticality': twin_config.ASSET_CRITICALITY.get(asset_type, 1),
            'lat': lat,
            'lon': lon,
        })
    return out


class WaterAdapter(_OverpassAdapter):
    """Standing water and storm drainage.

    Two distinct things in one query because they answer the same question -
    how does water get in and how does it get out - and because a second
    Overpass round trip on a city bbox costs another minute.
    """

    source_key = 'overpass_water'
    ttl_seconds = 7 * 24 * 3600
    stale_grace_seconds = 60 * 24 * 3600

    def fetch(self, bbox=None, **kwargs):
        box = self.bbox_clause(bbox)
        ql = (
            "[out:json][timeout:%d];("
            'way["natural"="water"](%s);'
            'relation["natural"="water"](%s);'
            'way["landuse"="reservoir"](%s);'
            'way["waterway"~"^(river|stream|canal)$"](%s);'
            'way["waterway"~"^(drain|ditch)$"](%s);'
            ");out geom tags;"
        ) % (OVERPASS_TIMEOUT_S - 10, box, box, box, box, box)
        payload = self.query(ql)
        return _parse_water(payload)


def _parse_water(payload):
    bodies, drains, channels = [], [], []
    for element in payload.get('elements', []):
        geometry = element.get('geometry') or []
        if len(geometry) < 2:
            continue
        coords = [[p['lon'], p['lat']] for p in geometry]
        tags = element.get('tags') or {}
        osm_id = "%s/%s" % (element.get('type'), element.get('id'))
        waterway = tags.get('waterway')

        if tags.get('natural') == 'water' or tags.get('landuse') == 'reservoir':
            ring = coords[:]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            if len(ring) < 4:
                continue
            bodies.append({'osm_id': osm_id, 'name': tags.get('name'), 'ring': ring})
        elif waterway in ('drain', 'ditch'):
            drains.append({'osm_id': osm_id, 'kind': waterway, 'line': coords})
        elif waterway in ('river', 'stream', 'canal'):
            channels.append({'osm_id': osm_id, 'kind': waterway,
                             'name': tags.get('name'), 'line': coords})
    return {'bodies': bodies, 'drains': drains, 'channels': channels}


class CameraAdapter(_OverpassAdapter):
    """OSINT surveillance-camera locations.

    This is a map of publicly documented infrastructure, nothing more. It never
    reaches a camera device, never proxies a stream, and `stream_url` is only
    ever populated from OSM's own `contact:webcam` tag.
    """

    source_key = 'overpass_cctv'
    ttl_seconds = 7 * 24 * 3600
    stale_grace_seconds = 60 * 24 * 3600

    def fetch(self, bbox=None, **kwargs):
        box = self.bbox_clause(bbox)
        ql = (
            "[out:json][timeout:%d];("
            'node["man_made"="surveillance"](%s);'
            'way["man_made"="surveillance"](%s);'
            ");out center tags;"
        ) % (OVERPASS_TIMEOUT_S - 10, box, box)
        payload = self.query(ql)
        return _parse_cameras(payload)


def _parse_cameras(payload):
    out = []
    for element in payload.get('elements', []):
        lat, lon = _element_point(element)
        if lat is None:
            continue
        tags = element.get('tags') or {}
        out.append({
            'osm_id': "%s/%s" % (element.get('type'), element.get('id')),
            'lat': lat,
            'lon': lon,
            'kind': tags.get('surveillance') or 'unknown',          # public / traffic / outdoor / indoor
            'camera_type': tags.get('camera:type') or 'unknown',    # fixed / panning / dome
            'mount': tags.get('camera:mount') or tags.get('surveillance:type'),
            'direction': _parse_direction(tags.get('camera:direction') or tags.get('direction')),
            'operator': tags.get('operator'),
            'zone': tags.get('surveillance:zone'),
            'stream_url': tags.get('contact:webcam') or tags.get('contact:website'),
            'osm_url': 'https://www.openstreetmap.org/%s/%s' % (element.get('type'), element.get('id')),
        })
    return out


_COMPASS = {
    'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90, 'ESE': 112.5,
    'SE': 135, 'SSE': 157.5, 'S': 180, 'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
    'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5,
}


def _parse_direction(raw):
    """OSM stores bearings as degrees or as compass points. Absent means absent.

    Returning None rather than 0 matters: a camera with no recorded bearing must
    render as a bare dot, never as a confident north-facing view cone.
    """
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text in _COMPASS:
        return _COMPASS[text]
    try:
        return float(text) % 360.0
    except ValueError:
        return None


def _element_point(element):
    if element.get('lat') is not None:
        return element['lat'], element['lon']
    center = element.get('center')
    if center:
        return center.get('lat'), center.get('lon')
    return None, None
