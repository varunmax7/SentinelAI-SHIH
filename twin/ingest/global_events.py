"""Global event feeds: GDACS and USGS.

Both are keyless GeoJSON and both are *global*, so unlike SACHET they say
nothing about a city until they are filtered to one. The filtering happens at
ingest, against the city bbox, so a magnitude-6 quake in Chile never reaches the
database at all.

They are secondary to SACHET by some distance: GDACS events are country-scoped
and slow-moving, and USGS quakes near Bengaluru or Hyderabad are rare. They earn
their place by being trivially reliable and by covering hazard classes IMD does
not issue warnings for.
"""

from datetime import datetime, timezone

from .base import IngestAdapter

GDACS_URL = 'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH'
USGS_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson'

# GDACS event type codes.
GDACS_EVENT_TYPES = {
    'EQ': 'earthquake',
    'TC': 'cyclone',
    'FL': 'flood',
    'VO': 'volcano',
    'DR': 'drought',
    'WF': 'wildfire',
}

# GDACS publishes a three-colour alert level rather than CAP severities.
GDACS_ALERT_TO_PRIORITY = {'Red': 'critical', 'Orange': 'high', 'Green': 'medium'}


def _epoch_ms_to_utc(value):
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _iso_to_utc(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class GdacsAdapter(IngestAdapter):
    source_key = 'gdacs'
    # Global disaster events move over days, not minutes.
    ttl_seconds = 900

    def cache_key(self, **kwargs):
        # No arguments: one global feed, one cache entry. Keeping this explicit
        # so a caller passing a db handle or a model class cannot make the key
        # unstable across restarts.
        return super(GdacsAdapter, self).cache_key()

    def fetch(self, **kwargs):
        payload = self.get_json(GDACS_URL)
        out = []
        for feature in payload.get('features', []):
            geometry = feature.get('geometry') or {}
            coords = geometry.get('coordinates') or []
            if geometry.get('type') != 'Point' or len(coords) < 2:
                continue
            props = feature.get('properties') or {}
            event_id = props.get('eventid')
            episode = props.get('episodeid')
            if event_id is None:
                continue
            alert_level = props.get('alertlevel')
            out.append({
                # eventid alone is not unique - GDACS reissues an event as new
                # episodes, and each is a distinct row.
                'source_uid': 'gdacs-%s-%s' % (event_id, episode),
                'event': GDACS_EVENT_TYPES.get(props.get('eventtype'), props.get('eventtype')),
                'headline': (props.get('htmldescription') or props.get('name') or '').strip() or None,
                'sender': props.get('source') or 'GDACS',
                'category': 'Geo',
                'severity': alert_level,
                'priority': GDACS_ALERT_TO_PRIORITY.get(alert_level, 'low'),
                # GDACS publishes no per-event certainty; these are observed,
                # already-happening events, so confidence is high but not 1.0 -
                # the *location* is a country centroid, not a survey.
                'confidence': 0.8,
                'effective_at': _iso_to_utc(props.get('fromdate')),
                'expires_at': _iso_to_utc(props.get('todate')),
                'area_desc': props.get('country'),
                'lat': coords[1],
                'lon': coords[0],
                'raw_url': props.get('url', {}).get('report') if isinstance(props.get('url'), dict) else None,
            })
        return out


class UsgsQuakeAdapter(IngestAdapter):
    source_key = 'usgs_quakes'
    ttl_seconds = 300

    def cache_key(self, **kwargs):
        return super(UsgsQuakeAdapter, self).cache_key()

    def fetch(self, **kwargs):
        payload = self.get_json(USGS_URL)
        out = []
        for feature in payload.get('features', []):
            geometry = feature.get('geometry') or {}
            coords = geometry.get('coordinates') or []
            if len(coords) < 2:
                continue
            props = feature.get('properties') or {}
            magnitude = props.get('mag')
            occurred = _epoch_ms_to_utc(props.get('time'))
            out.append({
                'source_uid': 'usgs-%s' % feature.get('id'),
                'event': 'earthquake',
                'headline': props.get('title'),
                'sender': 'USGS',
                'category': 'Geo',
                'severity': ('M%.1f' % magnitude) if magnitude is not None else None,
                'priority': _magnitude_priority(magnitude),
                # A recorded seismic event is an observation, not a forecast.
                'confidence': 1.0,
                'effective_at': occurred,
                # A quake is instantaneous. The shaking is over, so the alert is
                # given a short fixed window rather than left open forever.
                'expires_at': _add_hours(occurred, 6),
                'area_desc': props.get('place'),
                'lat': coords[1],
                'lon': coords[0],
                'magnitude': magnitude,
                'depth_km': coords[2] if len(coords) > 2 else None,
                'raw_url': props.get('url'),
            })
        return out


def _magnitude_priority(magnitude):
    if magnitude is None:
        return 'low'
    if magnitude >= 6.0:
        return 'critical'
    if magnitude >= 5.0:
        return 'high'
    if magnitude >= 4.0:
        return 'medium'
    return 'low'


def _add_hours(moment, hours):
    if moment is None:
        return None
    from datetime import timedelta
    return moment + timedelta(hours=hours)
