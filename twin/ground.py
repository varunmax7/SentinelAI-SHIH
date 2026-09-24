"""City-wide ground imagery - every location at once, from every source that
actually answers.

`ingest/streetview.py` answers one question well: "what does *this* point look
like". That is the right shape for a drawer opened on one hexagon, and the
wrong shape for the question an operator actually asks first - *show me the
city*. This module is that second question: it fans out across every zone
centre in the city plus every point that carries its own imagery (a live
webcam, a citizen photo, an operator still), queries every provider in
parallel, and returns one board of locations each carrying its own pictures.

**Which sources are real, checked directly against live endpoints:**

  `webcam`   Windy Webcams API v3. The only genuinely live frames here. There
             are exactly three registered webcams across both modelled cities
             (two Hyderabad, one Bengaluru, verified at radii from 15 km to
             60 km - the count does not grow), so this source gives the board
             its "now", not its coverage.
  `report`   Photos attached to this application's own `Report` rows. Recent,
             at exact surveyed coordinates, and the only imagery here that was
             taken *because* something was happening. The most valuable source
             on the board and the one nobody else has.
  `street`   KartaView. Archival street-level photography, answering 13 of the
             16 zone centres across both cities. Every frame carries its own
             capture date and is labelled with it - a 2019 photo is never
             allowed to read as a live one.
  `street`   Mapillary. Implemented and wired, currently returning nothing:
             the configured token answers HTTP 200 `{"data": []}` for every
             query shape tried (bbox, ids, single-id, worldwide control point),
             while its vector tiles return 1,659 image points for the same
             tile. That is a token missing `read` scope, not a coverage gap.
             It is reported as `blocked` with that reason rather than silently
             contributing zero, so the owner can see there is a key to fix.
  `operator` Stills from `TWIN_CCTV_STREAMS_FILE` (`type: image`). Empty until
             an operator hands over real access - see `cameras.py`.

**Checked and deliberately rejected:** Wikimedia Commons geosearch. It answers
every zone centre and needs no key, but what it returns for these coordinates
is portraits, food and tourist shots ("Chicken Biryani in Alpha Hotel",
"Pavan kumar p.jpg") - place-tagged photography, not ground situational
imagery. Putting it on this board would pad the counts and mislead the
operator, which the no-mock-data rule forbids just as much as inventing a
number would.

Nothing here is ever fabricated. A source that fails, is unkeyed or returns
nothing contributes no tiles and one honest line in `sources[]` saying why.
"""

from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from . import aerial
from . import config as twin_config
from .geo import haversine_m
from .ingest.base import IngestAdapter
from .ingest import streetview

# Tiers, worst to best. Sorting a location's images by this puts a frame that
# is actually current above a photograph of the same junction from 2019.
TIER_STREET = 0
TIER_OPERATOR = 1
TIER_REPORT = 2
TIER_LIVE = 3

_PROVIDER_META = {
    'windy': {'label': 'Windy Webcams', 'licence': 'per Windy terms', 'live': True},
    'report': {'label': 'Citizen reports', 'licence': 'reporter-submitted', 'live': False},
    'kartaview': {'label': 'KartaView', 'licence': 'CC BY-SA', 'live': False},
    'mapillary': {'label': 'Mapillary', 'licence': 'CC BY-SA', 'live': False},
    'operator': {'label': 'Operator cameras', 'licence': 'per operator terms', 'live': True},
    'aerial': {'label': 'Esri satellite crops', 'licence': aerial.ATTRIBUTION, 'live': False},
}


# --- per-source adapters ------------------------------------------------------
class _WebcamAdapter(IngestAdapter):
    """Live webcam frames around a city centre.

    Short TTL on purpose: the whole claim this source makes is "this is now",
    and serving a ten-minute-old frame under a LIVE badge would be a lie the
    operator has no way to catch.
    """

    source_key = 'ground_webcam'
    # A stale live frame is worse than no live frame, so it is not served past
    # its grace either - `run()` falls through to FAILED and the board says the
    # webcam source is unavailable rather than showing an old picture as now.
    stale_grace_seconds = 300

    def __init__(self):
        super(_WebcamAdapter, self).__init__(timeout=twin_config.STREETVIEW_TIMEOUT_S)
        self.ttl_seconds = twin_config.GROUND_WEBCAM_TTL_S

    def cache_key(self, lat=None, lon=None, radius_m=None, **kwargs):
        return super(_WebcamAdapter, self).cache_key(
            lat=round(float(lat), 3), lon=round(float(lon), 3), radius=radius_m)

    def fetch(self, lat=None, lon=None, radius_m=None, **kwargs):
        return {'rows': streetview._windy_webcams(self, lat, lon, radius_m)}


class _StreetAdapter(IngestAdapter):
    """Archival street-level photography at one point, one provider.

    One adapter per provider rather than one per point-pair, so a provider
    that is down or unkeyed shows up as exactly that in the health list
    instead of being averaged into a vague "imagery degraded".
    """

    stale_grace_seconds = 30 * 24 * 3600

    def __init__(self, provider):
        super(_StreetAdapter, self).__init__(timeout=twin_config.STREETVIEW_TIMEOUT_S)
        self.provider = provider
        self.source_key = 'ground_%s' % provider
        self.ttl_seconds = twin_config.GROUND_ARCHIVE_TTL_S

    def cache_key(self, lat=None, lon=None, radius_m=None, **kwargs):
        # ~11 m. Two zone centres never collide; a point re-queried on the next
        # board build always hits.
        return super(_StreetAdapter, self).cache_key(
            lat=round(float(lat), 4), lon=round(float(lon), 4), radius=radius_m)

    def fetch(self, lat=None, lon=None, radius_m=None, **kwargs):
        if self.provider == 'kartaview':
            rows = streetview._kartaview(self, lat, lon, radius_m)
        else:
            rows = streetview._mapillary(self, lat, lon, radius_m)
        return {'rows': rows}


# --- normalisation ------------------------------------------------------------
_EPOCH_MS_CUTOFF = 10 ** 11  # Mapillary publishes capture time in milliseconds.


def _parse_when(value):
    """Best-effort UTC datetime from the four shapes the providers use.

    `None` whenever it cannot be read - which the caller renders as "date
    unknown", never as "now".
    """
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > _EPOCH_MS_CUTOFF else float(value)
        try:
            return datetime.utcfromtimestamp(seconds)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip().replace('Z', '').replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    return None


def _age_label(when, now):
    if when is None:
        return 'date unknown'
    delta = (now - when).total_seconds()
    if delta < 0:
        return 'just now'
    if delta < 90:
        return '%d s ago' % int(delta)
    if delta < 5400:
        return '%d min ago' % int(delta / 60)
    if delta < 172800:
        return '%d h ago' % int(delta / 3600)
    if delta < 31536000:
        return '%d d ago' % int(delta / 86400)
    return when.strftime('%b %Y')


def _normalise(row, provider, tier, now, origin_lat, origin_lon):
    thumb = row.get('thumb_url') or row.get('full_url')
    if not thumb:
        return None
    lat, lon = row.get('lat'), row.get('lon')
    meta = _PROVIDER_META.get(provider, {})
    when = _parse_when(row.get('captured_at'))
    return {
        'id': '%s:%s' % (provider, row.get('id')),
        'provider': meta.get('label', provider),
        'provider_key': provider,
        'licence': row.get('licence') or meta.get('licence'),
        'tier': tier,
        'live': tier == TIER_LIVE,
        'title': row.get('title'),
        'lat': lat,
        'lon': lon,
        'heading': row.get('heading'),
        'captured_at': when.isoformat() + 'Z' if when else None,
        'age_label': _age_label(when, now),
        'age_seconds': int((now - when).total_seconds()) if when else None,
        'thumb_url': thumb,
        'full_url': row.get('full_url') or thumb,
        'page_url': row.get('page_url'),
        'distance_m': (round(haversine_m(origin_lat, origin_lon, lat, lon), 1)
                       if lat is not None and lon is not None else None),
    }


# --- locations ----------------------------------------------------------------
def _zone_points(city, zones):
    """Where to look. Zone centres, plus the city centre when it is not

    already covered by one - these are the twin's own published locations, not
    coordinates typed in here (max.md's rule). Every one is approximate by
    construction and is labelled `zone`, same as everywhere else in the twin.
    """
    points = [{'key': 'zone:%s' % z.slug, 'name': z.name, 'kind': 'zone',
               'lat': z.center_latitude, 'lon': z.center_longitude}
              for z in zones
              if z.center_latitude is not None and z.center_longitude is not None]
    limit = twin_config.GROUND_POINTS_PER_CITY
    if len(points) < limit and city.center_latitude is not None:
        nearest = min((haversine_m(city.center_latitude, city.center_longitude,
                                   p['lat'], p['lon']) for p in points), default=None)
        if nearest is None or nearest > 1500:
            points.insert(0, {'key': 'city:%s' % city.slug, 'name': '%s centre' % city.name,
                              'kind': 'centre',
                              'lat': city.center_latitude, 'lon': city.center_longitude})
    return points[:limit]


def _report_images(Report, city, now):
    """Photos attached to this app's own reports, inside the city bbox.

    Each becomes its own location - a report photo is the one image on this
    board taken at a place *because* something happened there, so it is never
    folded into whichever zone centre happens to be nearest.
    """
    if Report is None or city.bbox_min_lon is None:
        return []
    min_lon, min_lat, max_lon, max_lat = city.bbox
    since = now - timedelta(hours=twin_config.GROUND_REPORT_LOOKBACK_H)
    try:
        rows = (Report.query
                .filter(Report.timestamp >= since,
                        Report.image_file.isnot(None),
                        Report.image_file != '',
                        Report.latitude.between(min_lat, max_lat),
                        Report.longitude.between(min_lon, max_lon))
                .order_by(Report.timestamp.desc())
                .limit(twin_config.GROUND_REPORT_LIMIT)
                .all())
    except Exception:  # noqa: BLE001 - C1: a DB shape surprise hides this source, never the board
        return []

    out = []
    for report in rows:
        # The filename came out of a database row that an uploader
        # influenced, so it is percent-encoded rather than pasted into a
        # URL. Flask's static handler refuses traversal on its own; this
        # stops a filename with a `?`, `#` or space from silently
        # producing a URL that points somewhere else.
        url = '/static/uploads/%s' % quote(report.image_file)
        # `location` is a full reverse-geocoded address; the board wants a
        # label, so take the leading component and let the tile's own metadata
        # carry the rest.
        place = (report.location or '').split(',')[0].strip() or 'Reported location'
        image = _normalise({
            'id': report.id, 'lat': float(report.latitude), 'lon': float(report.longitude),
            'captured_at': report.timestamp, 'thumb_url': url, 'full_url': url,
            # /report/<id> does not exist in this app - the route is
            # /view_report/<id>, so the old link 404'd.
            'page_url': '/view_report/%s' % report.id,
            'title': report.title,
        }, 'report', TIER_REPORT, now, float(report.latitude), float(report.longitude))
        if image is None:
            continue
        image['hazard_type'] = report.hazard_type
        image['verification_status'] = report.verification_status
        image['priority'] = report.priority
        out.append({
            'key': 'report:%s' % report.id,
            'name': place,
            'kind': 'report',
            'lat': float(report.latitude), 'lon': float(report.longitude),
            'subtitle': '%s · %s' % ((report.hazard_type or 'report').replace('_', ' ').title(),
                                     report.verification_status or 'pending'),
            'images': [image],
        })
    return out


def _operator_images(city_slug, now):
    from . import cameras
    out = []
    for row in cameras.streams_for_city(city_slug):
        if row.get('type') != 'image':
            continue
        lat, lon = row.get('lat'), row.get('lon')
        if lat is None or lon is None:
            continue
        image = _normalise({
            'id': row.get('id'), 'lat': lat, 'lon': lon, 'captured_at': now,
            'thumb_url': row.get('url'), 'full_url': row.get('url'),
            'title': row.get('name'), 'licence': row.get('attribution'),
        }, 'operator', TIER_OPERATOR, now, lat, lon)
        if image is None:
            continue
        out.append({
            'key': 'operator:%s' % row.get('id'), 'name': row.get('name') or 'Operator camera',
            'kind': 'operator', 'lat': lat, 'lon': lon,
            'subtitle': row.get('operator') or 'Operator-supplied still',
            'images': [image],
        })
    return out


# --- the board ----------------------------------------------------------------
def build_board(city, zones, Report=None, fresh=False, now=None):
    """One city's whole ground-imagery board.

    `fresh=True` bypasses the webcam cache only - re-querying every archival
    provider on a 60-second refresh would be several hundred pointless round
    trips for photographs that have not changed since 2019.
    """
    now = now or datetime.utcnow()
    points = _zone_points(city, zones)
    radius = twin_config.GROUND_STREET_RADIUS_M

    health = {}

    def note(key, status, count, detail=None):
        entry = health.setdefault(key, {'count': 0, 'status': status, 'detail': detail})
        entry['count'] += count
        # Worst status wins, so one zone answering does not mask five failing.
        if status == 'failed' and entry['status'] == 'ok':
            entry['status'] = 'degraded'
        elif entry['status'] == 'failed' and status == 'ok':
            entry['status'] = 'degraded'
        if detail and not entry.get('detail'):
            entry['detail'] = detail

    # -- webcams: one query per city, not per point ---------------------------
    live_rows = []
    if twin_config.WINDY_WEBCAMS_KEY:
        result = _WebcamAdapter().run(
            force=fresh, lat=city.center_latitude, lon=city.center_longitude,
            radius_m=twin_config.WEBCAM_RADIUS_M)
        rows = (result.data or {}).get('rows') or []
        live_rows = rows
        note('windy', 'ok' if result.ok else 'failed', len(rows),
             None if result.ok else (result.error or 'Windy Webcams did not answer.'))
    else:
        note('windy', 'unconfigured', 0, 'WINDY_WEBCAMS_KEY is not set, so no live frames.')

    # -- archival street imagery: every point x every provider, in parallel ---
    providers = ['kartaview']
    if twin_config.MAPILLARY_TOKEN:
        providers.append('mapillary')
    else:
        note('mapillary', 'unconfigured', 0, 'MAPILLARY_TOKEN is not set.')

    jobs = [(point, provider) for point in points for provider in providers]

    def run_job(job):
        point, provider = job
        result = _StreetAdapter(provider).run(
            lat=point['lat'], lon=point['lon'], radius_m=radius)
        return point, provider, result

    street = {}
    if jobs:
        with ThreadPoolExecutor(max_workers=twin_config.GROUND_MAX_WORKERS) as pool:
            for point, provider, result in pool.map(run_job, jobs):
                rows = (result.data or {}).get('rows') or []
                street.setdefault(point['key'], []).extend(
                    (provider, row) for row in rows)
                note(provider, 'ok' if result.ok else 'failed', len(rows),
                     None if result.ok else (result.error or 'No response.'))

    # Mapillary answering every call with an empty list is not "ok" - it is a
    # token without read scope, and saying so is the difference between the
    # owner fixing a key and assuming this city has no coverage. See the module
    # docstring for how this was established.
    if 'mapillary' in providers and health.get('mapillary', {}).get('count') == 0:
        health['mapillary'] = {
            'count': 0, 'status': 'blocked',
            'detail': 'The configured MAPILLARY_TOKEN returns an empty result for every '
                      'query (including a known-dense control point), while Mapillary\'s '
                      'own vector tiles return thousands of images for the same area. '
                      'The token needs "read" scope granted in the Mapillary developer '
                      'dashboard.',
        }

    # -- assemble -------------------------------------------------------------
    locations = []
    for point in points:
        images = []
        for provider, row in street.get(point['key'], []):
            image = _normalise(row, provider, TIER_STREET, now, point['lat'], point['lon'])
            if image is not None and (image['distance_m'] is None
                                      or image['distance_m'] <= radius * 2):
                images.append(image)
        images.sort(key=lambda i: (i['distance_m'] if i['distance_m'] is not None else 1e9))
        # De-duplicate by provider id - the same frame can come back from two
        # neighbouring points when zone centres sit close together.
        images = _dedupe(images)[:twin_config.GROUND_IMAGES_PER_POINT]

        # The satellite crop is appended AFTER the cap, never inside it. It is
        # the one image guaranteed to exist and guaranteed to be of this exact
        # place, so it must not be the thing a busy location truncates away -
        # and a location with no street photography at all now still has an
        # image of itself instead of falling back to the shared city webcam.
        shot = aerial.crop_for_point(point['lat'], point['lon'], label=point['name'])
        if shot is not None:
            images.append(dict(shot, tier=TIER_STREET, provider_key='aerial',
                               # Esri publishes World Imagery as an undated
                               # mosaic on this endpoint, so there is no age to
                               # report and none is invented.
                               age_label='no capture date', age_seconds=None))
            note('aerial', 'ok', 1)

        if not images:
            continue
        entry = dict(point)
        entry['images'] = images
        entry['subtitle'] = ('Street-level, nearest first' if len(images) > 1
                             else 'Satellite view only — no street photography here')
        locations.append(entry)

    # Live webcams are their own locations. They are genuinely elsewhere in the
    # city, and pinning them to a zone centre they do not stand in would be the
    # same quiet lie the drawer already refuses to tell.
    webcam_names = _webcam_names(live_rows)
    for row, webcam_name in zip(live_rows, webcam_names):
        image = _normalise(row, 'windy', TIER_LIVE, now, row.get('lat'), row.get('lon'))
        if image is None:
            continue
        locations.append({
            'key': 'webcam:%s' % row.get('id'),
            'name': webcam_name,
            'kind': 'webcam',
            'lat': row.get('lat'), 'lon': row.get('lon'),
            'subtitle': 'Live frame, refreshes automatically',
            'images': [image],
        })

    report_locations = _report_images(Report, city, now)
    note('report', 'ok', sum(len(l['images']) for l in report_locations))
    locations.extend(report_locations)

    operator_locations = _operator_images(city.slug, now)
    if operator_locations:
        note('operator', 'ok', len(operator_locations))
    else:
        note('operator', 'unconfigured', 0,
             'No operator has supplied a live still for this city '
             '(TWIN_CCTV_STREAMS_FILE).')
    locations.extend(operator_locations)

    # Live first, then the freshest real photograph, then everything else by
    # distance from the city centre so the board reads outward from the middle.
    def rank(location):
        best = max(location['images'], key=lambda i: i['tier'])
        age = min((i['age_seconds'] for i in location['images']
                   if i['age_seconds'] is not None), default=10 ** 9)
        distance = (haversine_m(city.center_latitude, city.center_longitude,
                                location['lat'], location['lon'])
                    if location.get('lat') is not None else 10 ** 9)
        return (-best['tier'], age if best['tier'] >= TIER_REPORT else 0, distance)

    locations.sort(key=rank)

    images_total = sum(len(l['images']) for l in locations)
    live_total = sum(1 for l in locations for i in l['images'] if i['live'])

    return {
        'city': city.slug,
        'city_name': city.name,
        'generated_at': now.isoformat() + 'Z',
        'refresh_seconds': twin_config.GROUND_WEBCAM_TTL_S,
        'locations': locations,
        'location_count': len(locations),
        'images_total': images_total,
        'live_total': live_total,
        'sources': [{
            'key': key,
            'label': _PROVIDER_META.get(key, {}).get('label', key.title()),
            'live': _PROVIDER_META.get(key, {}).get('live', False),
            'status': value['status'],
            'count': value['count'],
            'detail': value.get('detail'),
        } for key, value in sorted(health.items())],
        'note': 'Every frame carries its own source and capture time. Sentinel never '
                'connects to a camera device and never proxies a stream; live frames '
                'are loaded by the browser straight from the publisher.',
    }


def _webcam_names(rows):
    """Distinct, honest names for a city's webcams.

    Both Hyderabad cameras are published under the bare title "Hyderabad" and
    sit on the same rooftop three metres apart, so neither the title nor the
    coordinates separate them - an operator would get two identical tiles and
    no way to tell which is which. Windy's own category ("Indoor") separates
    this pair; the camera id is the last resort, and it is at least a real
    identifier the operator can look up rather than an invented label.
    """
    titles = [(r.get('title') or 'Live webcam').strip() for r in rows]
    names = []
    for row, title in zip(rows, titles):
        if titles.count(title) == 1:
            names.append(title)
            continue
        category = row.get('category')
        if category and sum(1 for r, t in zip(rows, titles)
                            if t == title and r.get('category') == category) == 1:
            names.append('%s · %s' % (title, category))
        else:
            names.append('%s · cam %s' % (title, str(row.get('id'))[-4:]))
    return names


def _dedupe(images):
    seen, out = set(), []
    for image in images:
        if image['id'] in seen:
            continue
        seen.add(image['id'])
        out.append(image)
    return out
