"""Live air-quality stations: OpenAQ, AQICN, CPCB (data.gov.in).

**None of these has a keyless path** - unlike every adapter in `open_meteo.py`,
`overpass.py` or `rainviewer.py`, real-time ground stations are not free
anywhere the twin has found. Each class here degrades to `None` (not an
error - a missing key hides the layer, per `IngestAdapter`'s own contract)
when its key is absent, so the app runs identically with none of them
configured; this module could not be exercised against live data while
building it, for exactly that reason, and each adapter should be treated as
reviewed-by-reading rather than field-verified until a key is set.

**AQICN: never use `/feed/geo:`.** Documented here because it was tried and
it silently returned a *Delhi* station for a Bengaluru query - the exact
failure mode a keyless fallback exists to prevent everywhere else in this
package. Only the explicit per-city `/feed/{city}/` endpoint is used.
"""

from .. import config as twin_config
from .base import IngestAdapter

OPENAQ_LOCATIONS_URL = 'https://api.openaq.org/v3/locations'
OPENAQ_LATEST_URL = 'https://api.openaq.org/v3/locations/%s/latest'
AQICN_FEED_URL = 'https://api.waqi.info/feed/%s/'
CPCB_RESOURCE_URL = 'https://api.data.gov.in/resource/%s'
# The public CPCB real-time AQI resource id on data.gov.in.
CPCB_RESOURCE_ID = '3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69'

MAX_OPENAQ_LOCATIONS = 30


class OpenAQAdapter(IngestAdapter):
    """`OPENAQ_API_KEY` required - OpenAQ v3 has no keyless tier."""

    source_key = 'openaq_stations'
    ttl_seconds = 30 * 60

    def fetch(self, lat=None, lon=None, radius_m=25000, **kwargs):
        if not twin_config.OPENAQ_API_KEY:
            return None
        headers = {'X-API-Key': twin_config.OPENAQ_API_KEY}
        locations = self.get_json(OPENAQ_LOCATIONS_URL, params={
            'coordinates': '%.5f,%.5f' % (lat, lon),
            'radius': radius_m,
            'limit': MAX_OPENAQ_LOCATIONS,
        }, headers=headers)

        rows = []
        for loc in (locations.get('results') or [])[:MAX_OPENAQ_LOCATIONS]:
            loc_id = loc.get('id')
            coords = loc.get('coordinates') or {}
            if loc_id is None or coords.get('latitude') is None:
                continue
            # /latest carries a value and a sensorsId, but never the
            # pollutant name - that only exists on the location's own
            # `sensors` list. The pm25 sensor's id has to be resolved here
            # first, then matched against /latest's rows by id.
            pm25_sensor_id = _find_pm25_sensor_id(loc.get('sensors') or [])
            if pm25_sensor_id is None:
                continue
            try:
                latest = self.get_json(OPENAQ_LATEST_URL % loc_id, headers=headers)
            except Exception:  # noqa: BLE001 - one bad location must not drop the rest
                continue
            pm25, observed_at = _latest_sensor_value(latest, pm25_sensor_id)
            if pm25 is None:
                continue
            rows.append({
                'external_id': 'openaq:%s' % loc_id,
                'name': loc.get('name'),
                'lat': coords['latitude'],
                'lon': coords['longitude'],
                'pm2_5': pm25,
                'aqi': pm25_to_us_aqi(pm25),
                'observed_at': observed_at,
            })
        return rows or None


class AqicnAdapter(IngestAdapter):
    """`AQICN_TOKEN` required. City-name feed only - see the module docstring."""

    source_key = 'aqicn_stations'
    ttl_seconds = 30 * 60

    def fetch(self, city_name=None, **kwargs):
        if not twin_config.AQICN_TOKEN or not city_name:
            return None
        payload = self.get_json(AQICN_FEED_URL % city_name, params={
            'token': twin_config.AQICN_TOKEN,
        })
        if payload.get('status') != 'ok':
            return None
        data = payload.get('data') or {}
        geo = data.get('city', {}).get('geo') or [None, None]
        iaqi = data.get('iaqi') or {}
        pm25 = (iaqi.get('pm25') or {}).get('v')
        return [{
            'external_id': 'aqicn:%s' % (data.get('idx') or city_name),
            'name': data.get('city', {}).get('name') or city_name,
            'lat': geo[0], 'lon': geo[1],
            # AQICN's `aqi` field is already the US-EPA index (its own docs
            # say so) - reported as-is. pm2_5 is reported too so a future
            # CPCB-scale conversion has the raw concentration to work from;
            # none is applied here (see the module docstring on why not).
            'aqi': data.get('aqi'),
            'pm2_5': pm25,
            'observed_at': (data.get('time') or {}).get('iso'),
        }]


class CpcbAdapter(IngestAdapter):
    """`DATA_GOV_IN_KEY` required. Not obtained while building this - the

    public sample key data.gov.in issues by default is capped at 10 rows and
    aggressively rate-limited, so it was not used as a stand-in for a real
    one. Code path is complete and will activate the moment a real key is
    set; it has not been exercised against live data.
    """

    source_key = 'cpcb_stations'
    ttl_seconds = 30 * 60

    def fetch(self, state_name=None, **kwargs):
        if not twin_config.DATA_GOV_IN_KEY:
            return None
        payload = self.get_json(CPCB_RESOURCE_URL % CPCB_RESOURCE_ID, params={
            'api-key': twin_config.DATA_GOV_IN_KEY,
            'format': 'json',
            'filters[state]': state_name,
            'limit': 100,
        })
        rows = []
        for record in payload.get('records') or []:
            try:
                lat, lon = float(record.get('latitude')), float(record.get('longitude'))
            except (TypeError, ValueError):
                continue
            rows.append({
                'external_id': 'cpcb:%s' % record.get('station'),
                'name': record.get('station'),
                'lat': lat, 'lon': lon,
                'aqi': _safe_float(record.get('avg_value')) if record.get('pollutant_id') == 'AQI' else None,
                'pm2_5': _safe_float(record.get('avg_value')) if record.get('pollutant_id') == 'PM2.5' else None,
                'observed_at': record.get('last_update'),
            })
        return rows or None


def _find_pm25_sensor_id(sensors):
    for sensor in sensors:
        name = (sensor.get('parameter') or {}).get('name')
        if name in ('pm25', 'pm2.5'):
            return sensor.get('id')
    return None


def _latest_sensor_value(latest_payload, sensor_id):
    """(value, observed_at) for one sensor id from a /latest response - the

    freshest row, not the first: a location can carry both a live 2026
    sensor and a long-dead one from 2022 under different sensor ids, and
    /latest returns every one of them with no guaranteed ordering.
    """
    best_value, best_time = None, None
    for result in latest_payload.get('results') or []:
        if result.get('sensorsId') != sensor_id:
            continue
        observed_at = (result.get('datetime') or {}).get('utc')
        if best_time is None or (observed_at and observed_at > best_time):
            best_value, best_time = result.get('value'), observed_at
    return best_value, best_time


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# US-EPA AQI breakpoints for PM2.5 (ug/m3), the standard piecewise-linear
# formula every US AQI calculator uses. Kept here rather than imported since
# it is ~15 lines and pulling a dependency for it would be disproportionate.
_PM25_BREAKPOINTS = [
    (0.0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500),
]


def pm25_to_us_aqi(pm25):
    if pm25 is None:
        return None
    pm25 = max(0.0, float(pm25))
    for lo_c, hi_c, lo_i, hi_i in _PM25_BREAKPOINTS:
        if lo_c <= pm25 <= hi_c:
            return round(((hi_i - lo_i) / (hi_c - lo_c)) * (pm25 - lo_c) + lo_i)
    return 500  # above the table's top band
