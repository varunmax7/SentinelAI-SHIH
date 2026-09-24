"""Open-source intelligence feeds, filtered to one city.

The twin already models the city from weather, hydrology, OSM and its own
reports. What it had no way to show was *what the open world is observing
about this place right now* - the feeds an OSINT analyst would open in
separate tabs. This module pulls those onto the same map, on the same terms
as every other source here: real or not drawn, and every feature carries its
provider and its age.

**Each source, and what was actually verified against its live endpoint:**

  `aircraft`  OpenSky Network. Live ADS-B positions, keyless, ~10 s
              resolution. Verified: four aircraft over the Bengaluru box at
              the moment of writing (callsign, altitude, velocity, origin
              country), zero over Hyderabad in the same instant - which is
              the correct answer at 22:45 IST, not a failure. Anonymous
              access is rate-limited, hence the short cache and the single
              bbox query per city.

  `seismic`   EMSC seismicportal.eu (FDSN). Keyless. Verified: ten events
              across the Indian region in the last 30 days at M2.5+. Chosen
              alongside the existing USGS feed because EMSC's regional
              detection threshold over India is materially lower - USGS's
              all_day feed rarely lists anything under M4.5 here.

  `events`    NASA EONET v3. Open natural-event tracks, keyless. Verified:
              six features over the India box, all points on the track of an
              active Bay of Bengal system (Tropical Cyclone 01B). EONET
              emits one feature per track point, so points are collapsed to
              one feature per event at its most recent position - otherwise a
              single storm draws as a line of identical pins.

  `fire`      NASA FIRMS VIIRS/MODIS thermal anomalies. Needs a free MAP_KEY
              (firms.modaps.eosdis.nasa.gov/api/map_key). Verified only that
              the API rejects a missing key with 401 `Invalid MAP_KEY` - with
              no key configured this source reports `unconfigured` and draws
              nothing, it never guesses.

  `news`      GDELT 2.0 DOC API. Keyless geocoded world news. Its rate limit
              is strict (one request per five seconds, and this network was
              held at HTTP 429 through repeated backoff during development),
              so it is cached hard and a 429 is reported as `throttled`
              rather than as an outage or, worse, as "no news".

Everything is filtered to within OSINT_RADIUS_KM of the city centre and
carries `distance_km`. A cyclone 300 km offshore is genuinely this city's
problem and is drawn where it actually is - what is never done is drawing a
feature without saying how far away it is.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import config as twin_config
from .geo import haversine_m
from .ingest.base import IngestAdapter

OPENSKY_URL = 'https://opensky-network.org/api/states/all'
EMSC_URL = 'https://www.seismicportal.eu/fdsnws/event/1/query'
EONET_URL = 'https://eonet.gsfc.nasa.gov/api/v3/events/geojson'
FIRMS_URL = 'https://firms.modaps.eosdis.nasa.gov/api/area/csv'
GDELT_URL = 'https://api.gdeltproject.org/api/v2/doc/doc'

KIND_LABELS = {
    'aircraft': 'Aircraft in the air',
    'seismic': 'Seismic events',
    'events': 'Natural events',
    'fire': 'Thermal anomalies',
    'news': 'Geocoded news',
}


# --- helpers -----------------------------------------------------------------
def _utc(value):
    """Best-effort naive-UTC datetime from the several shapes these feeds use."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    # NOTE: the 'Z' is stripped below before matching, so no pattern here may
    # carry one - '%Y%m%dT%H%M%SZ' silently never matched GDELT's stamps and
    # every article rendered as "time unknown".
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M',
                '%Y%m%dT%H%M%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text.replace('Z', '')[:26], fmt)
        except ValueError:
            continue
    return None


def _age_label(when, now):
    if when is None:
        return 'time unknown'
    seconds = (now - when).total_seconds()
    if seconds < 0:
        return 'just now'
    if seconds < 90:
        return '%ds ago' % int(seconds)
    if seconds < 5400:
        return '%dm ago' % int(seconds / 60)
    if seconds < 172800:
        return '%dh ago' % int(seconds / 3600)
    return '%dd ago' % int(seconds / 86400)


def _feature(kind, key, lat, lon, title, when, now, city, **props):
    """One normalised GeoJSON point. `None` when the point is unusable -

    a feature with no real coordinate is never given a placeholder one.
    """
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    distance_km = haversine_m(city.center_latitude, city.center_longitude, lat, lon) / 1000.0
    payload = {
        'kind': kind,
        'id': '%s:%s' % (kind, key),
        'title': title,
        'observed_at': when.isoformat() + 'Z' if when else None,
        'age_label': _age_label(when, now),
        'age_seconds': int((now - when).total_seconds()) if when else None,
        'distance_km': round(distance_km, 1),
    }
    payload.update({k: v for k, v in props.items() if v is not None})
    return {
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
        'properties': payload,
    }


class _Osint(IngestAdapter):
    """Shared adapter shell: each source is one subclass with its own TTL."""

    stale_grace_seconds = 3600

    def __init__(self, ttl):
        super(_Osint, self).__init__(timeout=twin_config.OSINT_TIMEOUT_S)
        self.ttl_seconds = ttl


# --- aircraft (OpenSky) --------------------------------------------------------
class AircraftAdapter(_Osint):
    source_key = 'osint_aircraft'

    def __init__(self):
        super(AircraftAdapter, self).__init__(twin_config.OSINT_AIRCRAFT_TTL_S)

    def cache_key(self, bbox=None, **kwargs):
        return super(AircraftAdapter, self).cache_key(bbox=[round(v, 2) for v in bbox])

    def fetch(self, bbox=None, **kwargs):
        min_lon, min_lat, max_lon, max_lat = bbox
        payload = self.get_json(OPENSKY_URL, params={
            'lamin': min_lat, 'lomin': min_lon, 'lamax': max_lat, 'lomax': max_lon})
        # OpenSky returns `states: null`, not `[]`, for an empty box. That is a
        # successful "nothing flying here right now", not a failure, and must
        # not be turned into one.
        return {'time': payload.get('time'), 'states': payload.get('states') or []}


# The OpenSky state vector is a fixed-order array, not an object.
_ICAO, _CALLSIGN, _ORIGIN, _TIMEPOS = 0, 1, 2, 3
_LON, _LAT, _BARO_ALT, _ON_GROUND = 5, 6, 7, 8
_VELOCITY, _HEADING, _VERT_RATE, _GEO_ALT = 9, 10, 11, 13


def _aircraft_features(data, city, now):
    out = []
    for state in (data.get('states') or []):
        if len(state) <= _GEO_ALT:
            continue
        callsign = (state[_CALLSIGN] or '').strip() or (state[_ICAO] or '').strip()
        altitude = state[_GEO_ALT] if state[_GEO_ALT] is not None else state[_BARO_ALT]
        feature = _feature(
            'aircraft', state[_ICAO], state[_LAT], state[_LON],
            callsign or 'Unknown aircraft', _utc(state[_TIMEPOS]), now, city,
            callsign=callsign or None,
            icao24=state[_ICAO],
            origin_country=state[_ORIGIN],
            on_ground=bool(state[_ON_GROUND]),
            altitude_m=round(altitude, 1) if altitude is not None else None,
            velocity_ms=round(state[_VELOCITY], 1) if state[_VELOCITY] is not None else None,
            heading_deg=round(state[_HEADING], 1) if state[_HEADING] is not None else None,
            vertical_rate_ms=(round(state[_VERT_RATE], 1)
                              if state[_VERT_RATE] is not None else None),
            source='OpenSky Network',
            licence='OpenSky Network, CC BY-SA 4.0 (non-commercial)')
        if feature is not None:
            out.append(feature)
    return out


# --- seismic (EMSC) ------------------------------------------------------------
class SeismicAdapter(_Osint):
    source_key = 'osint_seismic'

    def __init__(self):
        super(SeismicAdapter, self).__init__(twin_config.OSINT_SEISMIC_TTL_S)

    def cache_key(self, bbox=None, days=None, **kwargs):
        return super(SeismicAdapter, self).cache_key(
            bbox=[round(v, 1) for v in bbox], days=days)

    def fetch(self, bbox=None, days=None, **kwargs):
        min_lon, min_lat, max_lon, max_lat = bbox
        start = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        return self.get_json(EMSC_URL, params={
            'format': 'json', 'limit': 200, 'start': start,
            'minlat': min_lat, 'maxlat': max_lat,
            'minlon': min_lon, 'maxlon': max_lon,
            'minmag': twin_config.OSINT_SEISMIC_MIN_MAG})


def _seismic_features(data, city, now):
    out = []
    for row in (data.get('features') or []):
        props = row.get('properties') or {}
        coords = (row.get('geometry') or {}).get('coordinates') or []
        if len(coords) < 2:
            continue
        magnitude = props.get('mag')
        feature = _feature(
            'seismic', props.get('unid') or row.get('id'), coords[1], coords[0],
            'M%.1f %s' % (magnitude, props.get('flynn_region') or 'earthquake')
            if magnitude is not None else (props.get('flynn_region') or 'Earthquake'),
            _utc(props.get('time')), now, city,
            magnitude=magnitude,
            depth_km=props.get('depth'),
            region=props.get('flynn_region'),
            page_url=('https://www.emsc-csem.org/Earthquake/earthquake.php?id=%s'
                      % props.get('unid')) if props.get('unid') else None,
            source='EMSC (seismicportal.eu)',
            licence='EMSC-CSEM, open data')
        if feature is not None:
            out.append(feature)
    return out


# --- natural events (NASA EONET) ------------------------------------------------
class EventsAdapter(_Osint):
    source_key = 'osint_events'

    def __init__(self):
        super(EventsAdapter, self).__init__(twin_config.OSINT_EVENTS_TTL_S)

    def cache_key(self, bbox=None, days=None, **kwargs):
        return super(EventsAdapter, self).cache_key(
            bbox=[round(v, 1) for v in bbox], days=days)

    def fetch(self, bbox=None, days=None, **kwargs):
        min_lon, min_lat, max_lon, max_lat = bbox
        # EONET's bbox is min-lon, MAX-lat, max-lon, MIN-lat - upper-left then
        # lower-right, which is the opposite vertical order to every other
        # bbox in this codebase. Getting it wrong returns an empty list rather
        # than an error, so it is spelled out here.
        return self.get_json(EONET_URL, params={
            'status': 'open', 'days': days,
            'bbox': '%f,%f,%f,%f' % (min_lon, max_lat, max_lon, min_lat)})


def _event_features(data, city, now):
    """One feature per EONET event, at its most recent track point.

    EONET emits a separate feature for every point on a storm's track, so the
    raw response draws an active cyclone as a dozen identical pins marching
    across the sea. Only the latest point of each event is kept, and the
    number of points behind it is carried through as `track_points` so the UI
    can say this is a moving system rather than a single observation.
    """
    latest = {}
    for row in (data.get('features') or []):
        props = row.get('properties') or {}
        coords = (row.get('geometry') or {}).get('coordinates') or []
        if len(coords) < 2:
            continue
        event_id = props.get('id') or props.get('title')
        when = _utc(props.get('date'))
        entry = latest.get(event_id)
        if entry is None:
            latest[event_id] = {'row': row, 'when': when, 'count': 1}
        else:
            entry['count'] += 1
            if when is not None and (entry['when'] is None or when > entry['when']):
                entry['row'], entry['when'] = row, when

    out = []
    for event_id, entry in latest.items():
        props = entry['row']['properties'] or {}
        coords = entry['row']['geometry']['coordinates']
        categories = props.get('categories')
        if isinstance(categories, list):
            category = ', '.join(str(c.get('title') if isinstance(c, dict) else c)
                                 for c in categories) or None
        else:
            category = str(categories) if categories else None
        feature = _feature(
            'events', event_id, coords[1], coords[0],
            props.get('title') or 'Natural event', entry['when'], now, city,
            category=category,
            track_points=entry['count'],
            page_url=props.get('link'),
            source='NASA EONET',
            licence='NASA, open data')
        if feature is not None:
            out.append(feature)
    return out


# --- thermal anomalies (NASA FIRMS) ---------------------------------------------
class FireAdapter(_Osint):
    source_key = 'osint_fire'

    def __init__(self):
        super(FireAdapter, self).__init__(twin_config.OSINT_FIRE_TTL_S)

    def cache_key(self, bbox=None, days=None, **kwargs):
        return super(FireAdapter, self).cache_key(
            bbox=[round(v, 2) for v in bbox], days=days)

    def fetch(self, bbox=None, days=None, **kwargs):
        import csv
        import io

        import requests

        key = twin_config.FIRMS_MAP_KEY
        min_lon, min_lat, max_lon, max_lat = bbox
        url = '%s/%s/%s/%f,%f,%f,%f/%d' % (
            FIRMS_URL, key, twin_config.FIRMS_PRODUCT,
            min_lon, min_lat, max_lon, max_lat, days)
        response = requests.get(url, timeout=self.timeout,
                                headers={'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        response.raise_for_status()
        body = response.text
        # FIRMS answers a bad key with HTTP 200 and a plain-text body, not a
        # 4xx with CSV - so a key problem would otherwise parse as "zero fires"
        # and read on the map as "nothing is burning".
        if 'Invalid MAP_KEY' in body or not body.strip().lower().startswith('country_id,'):
            raise ValueError(body.strip()[:120] or 'FIRMS returned no CSV header')
        return {'rows': list(csv.DictReader(io.StringIO(body)))}


def _fire_features(data, city, now):
    out = []
    for row in (data.get('rows') or []):
        when = _utc('%sT%s' % (row.get('acq_date'),
                               str(row.get('acq_time') or '0000').zfill(4)[:2] + ':' +
                               str(row.get('acq_time') or '0000').zfill(4)[2:] + ':00'))
        feature = _feature(
            'fire', '%s_%s_%s' % (row.get('latitude'), row.get('longitude'),
                                  row.get('acq_time')),
            row.get('latitude'), row.get('longitude'),
            'Thermal anomaly (%s confidence)' % (row.get('confidence') or 'unknown'),
            when, now, city,
            confidence=row.get('confidence'),
            brightness_k=_float(row.get('bright_ti4') or row.get('brightness')),
            frp_mw=_float(row.get('frp')),
            satellite=row.get('satellite'),
            daynight=row.get('daynight'),
            source='NASA FIRMS (%s)' % twin_config.FIRMS_PRODUCT,
            licence='NASA FIRMS, open data')
        if feature is not None:
            out.append(feature)
    return out


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --- geocoded news (GDELT) --------------------------------------------------------
class NewsAdapter(_Osint):
    source_key = 'osint_news'

    def __init__(self):
        super(NewsAdapter, self).__init__(twin_config.OSINT_NEWS_TTL_S)

    def cache_key(self, query=None, **kwargs):
        return super(NewsAdapter, self).cache_key(query=query)

    def fetch(self, query=None, **kwargs):
        import requests

        _gdelt_gate()
        response = requests.get(GDELT_URL, params={
            'query': query, 'mode': 'artlist', 'format': 'json',
            'timespan': '%dd' % twin_config.OSINT_NEWS_DAYS,
            'maxrecords': twin_config.OSINT_NEWS_MAX,
        }, timeout=self.timeout, headers={'User-Agent': 'SentinelAI-DigitalTwin/1.0'})
        if response.status_code == 429:
            _gdelt_throttled()
            # GDELT allows one request every five seconds per caller and
            # answers 429 in plain text. Raising a distinguishable error lets
            # the collector report `throttled` instead of `failed` - the
            # difference between "ask again later" and "this is broken".
            raise _Throttled(response.text.strip()[:160])
        response.raise_for_status()
        return response.json()


class _Throttled(Exception):
    pass


# GDELT's limit is per caller, not per query, so two cities collected
# back-to-back throttle each other - which is exactly what happened in
# testing: Hyderabad's news succeeded and Bengaluru's came back 429 a second
# later. This gate serialises GDELT calls process-wide and spaces them.
_GDELT_LOCK = threading.Lock()
_GDELT_LAST = [0.0]
_GDELT_COOLDOWN_UNTIL = [0.0]


def _gdelt_gate():
    """Space GDELT calls, and refuse outright while known to be throttled.

    Spacing alone was not enough: after a 429 the block outlasts the published
    five-second window, so the next request spent the full gate wait and then
    got 429 again - twenty-five seconds of an analyst's page load spent
    earning a refusal. Once throttled, this raises immediately until the
    cooldown expires, which turns that into an instant, honest `throttled`.
    """
    with _GDELT_LOCK:
        now = time.time()
        if now < _GDELT_COOLDOWN_UNTIL[0]:
            raise _Throttled(
                'GDELT rate-limited this caller; not retrying for another %ds.'
                % int(_GDELT_COOLDOWN_UNTIL[0] - now))
        wait = twin_config.OSINT_NEWS_MIN_INTERVAL_S - (now - _GDELT_LAST[0])
        if wait > 0:
            time.sleep(min(wait, twin_config.OSINT_NEWS_MIN_INTERVAL_S))
        _GDELT_LAST[0] = time.time()


def _gdelt_throttled():
    _GDELT_COOLDOWN_UNTIL[0] = time.time() + twin_config.OSINT_NEWS_COOLDOWN_S

# --- news relevance -----------------------------------------------------------
# GDELT's matching is loose: a query of "Bengaluru" plus an OR-list of single
# hazard words returned an Australian cricket coach, Kerala aviation politics
# and a Karnataka drought-policy quote, because "rain", "fire" and "storm" are
# ordinary English that appears in sports and metaphor constantly ("rain
# delay", "fired up", "storming performance").
#
# So the query is tightened AND every returned headline is re-checked here.
# Matching on PHRASES rather than bare words is what does the work: "heavy
# rain" is weather, "rain" alone is a cricket match. A headline that matches
# nothing is dropped rather than shown - a disaster map that lists cricket
# teaches an analyst to stop reading it.
NEWS_HAZARD_PATTERNS = (
    r'heavy rain', r'rains? lash', r'rainfall', r'downpour', r'cloudburst',
    r'waterlog', r'inundat', r'flood', r'deluge', r'submerg',
    r'landslide', r'landslip', r'mudslide',
    r'cyclone', r'depression', r'storm surge', r'thunderstorm',
    r'building collapse', r'wall collapse', r'roof collapse', r'collapsed',
    r'fire broke out', r'blaze', r'gutted', r'fire accident',
    r'rescue', r'evacuat', r'stranded', r'drown',
    r'red alert', r'orange alert', r'yellow alert', r'imd ',
    r'ndrf', r'sdrf', r'disaster', r'calamit',
    r'traffic jam', r'traffic snarl', r'gridlock', r'road cave',
    r'power outage', r'power cut', r'blackout',
    r'heatwave', r'heat wave', r'drought',
)

_NEWS_HAZARD_RE = None


def _news_is_relevant(title):
    """True when a headline is about a hazard, not merely near hazard words.

    Checked against the exact headlines that made this necessary - see
    NEWS_HAZARD_PATTERNS above.
    """
    global _NEWS_HAZARD_RE
    if _NEWS_HAZARD_RE is None:
        _NEWS_HAZARD_RE = re.compile('|'.join(NEWS_HAZARD_PATTERNS), re.IGNORECASE)
    return bool(title) and bool(_NEWS_HAZARD_RE.search(title))


def _news_items(data, city, now):
    """News articles as a LIST, deliberately not as map features.

    GDELT's article list says an article is *about* this city. It never says
    where *in* the city, so there is no honest coordinate to draw one at.
    Pinning them all on the city centre - which is what this did first - puts
    forty identical markers on one pixel and invents a precision the feed does
    not have. They belong in the drawer, as reading.
    """
    out = []
    for i, article in enumerate(data.get('articles') or []):
        title = article.get('title') or ''
        # GDELT's own matching is loose enough to return cricket; the headline
        # itself is re-checked. See _news_is_relevant.
        if not _news_is_relevant(title):
            continue
        when = _utc(article.get('seendate'))
        # GDELT carries the article's own og:image as `socialimage`. It is a
        # hotlink to the publisher's CDN, loaded by the browser like any other
        # third-party image here - never fetched or re-hosted by the server.
        # Many articles have none, so the UI must degrade to text, not to a
        # broken frame.
        image = (article.get('socialimage') or '').strip() or None
        out.append({
            'kind': 'news',
            'id': 'news:%s' % (article.get('url') or i),
            'title': title or 'Untitled article',
            'domain': article.get('domain'),
            'language': article.get('language'),
            'source_country': article.get('sourcecountry'),
            'image_url': image,
            'page_url': article.get('url'),
            'observed_at': when.isoformat() + 'Z' if when else None,
            'age_label': _age_label(when, now),
            'age_seconds': int((now - when).total_seconds()) if when else None,
            'source': 'GDELT 2.0',
            'licence': 'GDELT Project, open data',
        })
    # Syndication duplicates: the same wire story came back four times from
    # four US local-TV domains ("Climate disasters are growing...") in a single
    # response. Dedupe on a normalised title, keeping the first (freshest,
    # since the list is date-ordered) copy.
    seen, deduped = set(), []
    for item in out:
        key = re.sub(r'[^a-z0-9]+', ' ', (item['title'] or '').lower()).strip()[:90]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    # An American climate feature is not reporting on Bengaluru. Indian
    # sources lead; everything else keeps its place behind them rather than
    # being thrown away, since a foreign wire is occasionally the first to
    # carry a major Indian disaster.
    deduped.sort(key=lambda a: (
        0 if (a.get('source_country') or '').lower() in ('india', 'in') else 1,
        a['age_seconds'] if a['age_seconds'] is not None else 10 ** 9))
    return deduped


# --- the collector ---------------------------------------------------------------
def _city_bbox(city, radius_km):
    """A degree box around the city centre big enough to hold `radius_km`."""
    import math

    d_lat = radius_km / 111.0
    cos_lat = max(0.2, math.cos(math.radians(city.center_latitude)))
    d_lon = d_lat / cos_lat
    return (city.center_longitude - d_lon, city.center_latitude - d_lat,
            city.center_longitude + d_lon, city.center_latitude + d_lat)


def collect(city, kinds=None, now=None):
    """Every OSINT feed for one city as one GeoJSON FeatureCollection.

    Sources are queried in parallel and every one reports its own status, so
    a key that is missing or a feed that is throttled is visible as exactly
    that rather than as an empty map.
    """
    now = now or datetime.utcnow()
    radius_km = twin_config.OSINT_RADIUS_KM
    bbox = _city_bbox(city, radius_km)
    wanted = set(kinds or KIND_LABELS.keys())
    health = {}

    def note(kind, status, count, detail=None):
        health[kind] = {'status': status, 'count': count, 'detail': detail}

    jobs = []
    if 'aircraft' in wanted:
        jobs.append(('aircraft', AircraftAdapter(), {'bbox': bbox}, _aircraft_features))
    if 'seismic' in wanted:
        jobs.append(('seismic', SeismicAdapter(),
                     {'bbox': bbox, 'days': twin_config.OSINT_SEISMIC_DAYS}, _seismic_features))
    if 'events' in wanted:
        jobs.append(('events', EventsAdapter(),
                     {'bbox': bbox, 'days': twin_config.OSINT_EVENTS_DAYS}, _event_features))
    if 'fire' in wanted:
        if twin_config.FIRMS_MAP_KEY:
            jobs.append(('fire', FireAdapter(),
                         {'bbox': bbox, 'days': twin_config.OSINT_FIRE_DAYS}, _fire_features))
        else:
            note('fire', 'unconfigured', 0,
                 'FIRMS_MAP_KEY is not set. A free key from '
                 'firms.modaps.eosdis.nasa.gov/api/map_key turns on satellite '
                 'thermal-anomaly detections for this city.')
    if 'news' in wanted:
        jobs.append(('news', NewsAdapter(),
                     {'query': _news_query(city)}, _news_items))

    def run(job):
        kind, adapter, kwargs, _builder = job
        try:
            return kind, adapter.run(**kwargs), None
        except Exception as exc:  # noqa: BLE001 - never let one feed fail the map
            return kind, None, exc

    features, news = [], []
    if jobs:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            results = list(pool.map(run, jobs))
        builders = {job[0]: job[3] for job in jobs}
        for kind, result, error in results:
            if error is not None:
                note(kind, 'failed', 0, str(error)[:200])
                continue
            if not result.ok:
                detail = result.error or 'No response.'
                # `_Throttled` is raised both by a live 429 and by the local
                # cooldown gate that avoids earning another one. Matching only
                # the upstream wording classified the gate's own refusal as
                # `failed`, which reads as "this feed is broken" when it means
                # "ask again in a few minutes".
                status = ('throttled'
                          if ('429' in detail or 'limit requests' in detail
                              or '_Throttled' in detail or 'rate-limited' in detail)
                          else 'failed')
                note(kind, status, 0, detail[:200])
                continue
            built = builders[kind](result.data or {}, city, now)
            status = 'ok' if result.status == 'ok' else 'cached'

            # News has no coordinate within the city, so it is a list, not
            # geometry. See _news_items.
            if kind == 'news':
                news.extend(built[:twin_config.OSINT_NEWS_MAX])
                note(kind, status, len(news))
                continue

            # Radius, not the bounding box the feeds were asked for: a box's
            # corners reach ~40% further than its sides, and a quake in the
            # corner would otherwise be drawn as if it were as close as one
            # due north at the stated radius.
            built = [f for f in built if f['properties']['distance_km'] <= radius_km]
            built.sort(key=lambda f: f['properties']['distance_km'])
            built = built[:twin_config.OSINT_MAX_PER_KIND]
            features.extend(built)
            note(kind, status, len(built))

    return {
        'type': 'FeatureCollection',
        'features': features,
        'city': city.slug,
        'generated_at': now.isoformat() + 'Z',
        'radius_km': radius_km,
        # What the client should poll at. Driven by the aircraft TTL,
        # since aircraft are the only thing here that is wrong after a
        # minute - polling faster only burns OpenSky's anonymous quota.
        'refresh_seconds': twin_config.OSINT_AIRCRAFT_TTL_S,
        'news': news,
        'counts': dict(
            {kind: sum(1 for f in features if f['properties']['kind'] == kind)
             for kind in KIND_LABELS},
            news=len(news)),
        'sources': [{
            'kind': kind,
            'label': KIND_LABELS.get(kind, kind),
            'status': entry['status'],
            'count': entry['count'],
            'detail': entry.get('detail'),
        } for kind, entry in sorted(health.items())],
        'note': 'Open-source intelligence within %d km of the city centre. Every feature '
                'carries its provider, its age and its distance. Nothing here is an '
                'official warning - official alerts are the separate SACHET/IMD layer.'
                % radius_km,
    }


def near_point(city, lat, lon, radius_km=None, now=None):
    """The city's OSINT collection, re-measured against one clicked point.

    Deliberately reuses `collect()` rather than re-querying anything: that
    call is cached per city, so opening twenty cell drawers costs twenty
    dictionary filters and zero extra requests to OpenSky, EMSC, EONET or
    FIRMS. Re-querying per cell would burn OpenSky's anonymous quota in a
    couple of minutes of ordinary clicking.

    Every distance is recomputed from the clicked point, not carried over
    from the city centre - a quake 130 km from the centre can be 40 km from
    this cell, and showing the centre's number here would be wrong in a way
    nobody could see.

    `cameras` is always present and is usually empty, with a reason. That is
    the honest answer to "is there a camera looking at this spot": no open
    source publishes a live public camera feed for Hyderabad or Bengaluru
    (see cameras.py), and a silent empty section reads as a bug rather than
    as an answer.
    """
    now = now or datetime.utcnow()
    radius_km = radius_km if radius_km is not None else twin_config.OSINT_NEAR_RADIUS_KM
    collection = collect(city, now=now)

    near, beyond = [], []
    for feature in collection.get('features') or []:
        coords = (feature.get('geometry') or {}).get('coordinates') or []
        if len(coords) != 2:
            continue
        distance_km = haversine_m(lat, lon, coords[1], coords[0]) / 1000.0
        props = dict(feature['properties'])
        props['distance_km'] = round(distance_km, 1)
        # Kept alongside so an operator can tell "40 km from this cell" from
        # "130 km from the city centre" without doing the arithmetic.
        props['distance_from_centre_km'] = feature['properties'].get('distance_km')
        (near if distance_km <= radius_km else beyond).append(props)

    near.sort(key=lambda p: (-_TIER.get(p['kind'], 0), p['distance_km']))
    beyond.sort(key=lambda p: p['distance_km'])

    # The closest item of each kind that fell OUTSIDE the radius, with its real
    # distance. Without this the drawer goes silent at a city-centre cell while
    # twenty aircraft sit over the airport thirty kilometres away - and silence
    # reads as "the feed is broken", not as "nothing is close".
    nearest_beyond = {}
    for props in beyond:
        nearest_beyond.setdefault(props['kind'], props)

    return {
        'city': city.slug,
        'lat': lat,
        'lon': lon,
        'radius_km': radius_km,
        'generated_at': collection.get('generated_at'),
        'refresh_seconds': collection.get('refresh_seconds'),
        'observations': near[:twin_config.OSINT_NEAR_MAX],
        'nearest_beyond': [dict(props, total_in_city=sum(
            1 for b in beyond if b['kind'] == props['kind']))
            for props in nearest_beyond.values()],
        'counts': {kind: sum(1 for p in near if p['kind'] == kind) for kind in KIND_LABELS},
        'cameras': _cameras_near(city, lat, lon, radius_km),
        # City-level, never point-level: GDELT locates an article to the city
        # and no further, so the newest few are offered as context for the
        # cell without ever claiming to be about this street.
        'city_news': (collection.get('news') or [])[:twin_config.OSINT_NEAR_NEWS],
        'sources': collection.get('sources') or [],
    }


# Ranking for the per-point list: something in the air right now outranks a
# tremor from three weeks ago, however much closer the tremor was.
_TIER = {'fire': 4, 'aircraft': 3, 'events': 2, 'seismic': 1}


def _cameras_near(city, lat, lon, radius_km):
    """Any live public camera covering this point, and why there is none.

    Two real sources are checked, both already in this codebase:
    operator-supplied streams (`cameras.py`, empty until GHMC/BBMP ICCC hand
    over access) and Windy's registered webcams. Windy has exactly three
    across both modelled cities, so for almost every point the honest answer
    is "the nearest live camera is kilometres away", with the distance said
    out loud rather than implied away.
    """
    from . import cameras as operator_cameras
    # ground.py's webcam adapter, not streetview's raw helper: the raw helper
    # hits Windy on every call, which turned each cell click into a live HTTP
    # round trip (1.6 s warm). The adapter caches the city's webcams for
    # GROUND_WEBCAM_TTL_S, so clicking through twenty cells costs one request.
    from .ground import _WebcamAdapter

    out = []
    try:
        for row in operator_cameras.streams_near(city.slug, lat, lon):
            if row.get('lat') is None or row.get('lon') is None:
                continue
            distance_km = haversine_m(lat, lon, row['lat'], row['lon']) / 1000.0
            out.append({
                'name': row.get('name') or 'Operator camera',
                'operator': row.get('operator'),
                'kind': row.get('type'),
                'url': row.get('url'),
                'distance_km': round(distance_km, 1),
                'source': 'Operator-supplied (%s)' % (row.get('attribution') or 'permission on file'),
                'live': True,
            })
    except Exception:  # noqa: BLE001 - a missing file hides this, never the drawer
        pass

    try:
        result = _WebcamAdapter().run(
            lat=city.center_latitude, lon=city.center_longitude,
            radius_m=twin_config.WEBCAM_RADIUS_M)
        for row in ((result.data or {}).get('rows') or []):
            if row.get('lat') is None:
                continue
            distance_km = haversine_m(lat, lon, row['lat'], row['lon']) / 1000.0
            out.append({
                'name': row.get('title') or 'Public webcam',
                'operator': None,
                'kind': 'image',
                'url': row.get('page_url'),
                'thumb_url': row.get('thumb_url'),
                'captured_at': row.get('captured_at'),
                'distance_km': round(distance_km, 1),
                'source': 'Windy Webcams',
                'live': True,
            })
    except Exception:  # noqa: BLE001
        pass

    out.sort(key=lambda c: c['distance_km'])
    covering = [c for c in out if c['distance_km'] <= twin_config.OSINT_CAMERA_COVER_KM]
    return {
        'covering': covering,
        'nearest': out[:3],
        'reason': None if covering else (
            'No open source publishes a live camera feed covering this point. '
            'OpenStreetMap maps camera locations, not streams; neither GHMC/TS '
            'Police nor Bengaluru Traffic Police publish a public API; and the '
            'nearest registered public webcam is %s. A real feed appears here '
            'only when an operator hands over access (TWIN_CCTV_STREAMS_FILE).'
            % ('%.1f km away' % out[0]['distance_km'] if out else 'not within this city')),
    }


def _news_query(city):
    """A GDELT query scoped to this city, to hazard vocabulary, and to India.

    Three things narrow it, and all three were needed:

      the city name      - obviously
      hazard terms       - without them the feed is cricket and civic politics
      sourcecountry:IN   - without it a US syndicated climate feature came back
                           four times from four American local-TV domains

    Even with all three, GDELT matches loosely enough to return a cricket
    coach, so every headline is re-checked by `_news_is_relevant` after the
    fact. This query reduces what has to be thrown away; it does not replace
    the check.
    """
    terms = ' OR '.join('"%s"' % t if ' ' in t else t
                        for t in twin_config.OSINT_NEWS_TERMS)
    return '"%s" (%s) sourcecountry:IN' % (city.name, terms)
