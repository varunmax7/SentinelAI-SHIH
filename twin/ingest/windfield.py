"""Hourly wind/cloud/rain/apparent-temperature lattice, for the forecast agent.

Reuses `ingest/open_meteo.py`'s own coarse H3 resolution-6 sampling - the
same ~5-6 km lattice the scoring engine already shares one weather reading
across every child cell with - rather than standing up a second, separate
grid. One extra Open-Meteo call per city per poll, at the same sample points
the twin already queries.
"""

from datetime import datetime

from .base import IngestAdapter
from .open_meteo import FORECAST_URL, MAX_POINTS_PER_CALL, _as_list, _chunks

HOURLY_FIELDS = 'wind_speed_10m,wind_direction_10m,cloud_cover,precipitation,apparent_temperature'


class WindFieldAdapter(IngestAdapter):
    """Hourly series per sample point, out to `forecast.MAX_LEAD_HOURS`."""

    source_key = 'open_meteo_windfield'
    ttl_seconds = 15 * 60

    def fetch(self, points=None, hours=13, **kwargs):
        points = points or []
        results = {}
        for chunk in _chunks(points, MAX_POINTS_PER_CALL):
            payload = self.get_json(FORECAST_URL, params={
                'latitude': ','.join('%.4f' % p[1] for p in chunk),
                'longitude': ','.join('%.4f' % p[2] for p in chunk),
                'hourly': HOURLY_FIELDS,
                'forecast_days': 2,
                'timezone': 'UTC',
            })
            for (key, lat, lon), entry in zip(chunk, _as_list(payload)):
                parsed = _parse_hourly(entry, hours)
                if parsed is not None:
                    parsed['lat'] = lat
                    parsed['lon'] = lon
                    results[key] = parsed
        return results or None


def _now_index(times):
    """Index of the current hour in an Open-Meteo hourly `time` array.

    `_hour_index` in open_meteo.py finds this by matching `current.time`,
    which this adapter has no `current` block to supply (only `hourly` is
    requested - lighter, and this adapter needs the whole series, not a
    snapshot). Matched directly against wall-clock UTC instead: Open-Meteo's
    hourly stamps are `YYYY-MM-DDTHH:00`, the same prefix `strftime` produces.
    Falls back to 0 (this call's first hour) only if the current hour is
    genuinely outside the returned window, which `forecast_days=2` should
    never actually hit.
    """
    prefix = datetime.utcnow().strftime('%Y-%m-%dT%H:00')
    for i, stamp in enumerate(times):
        if stamp == prefix:
            return i
    return 0


def _parse_hourly(entry, hours):
    hourly = entry.get('hourly') or {}
    times = hourly.get('time') or []
    if not times:
        return None
    start = _now_index(times)
    end = start + hours

    def series(field):
        return (hourly.get(field) or [])[start:end]

    return {
        'times': times[start:end],
        'wind_speed_kmh': series('wind_speed_10m'),
        'wind_direction_deg': series('wind_direction_10m'),
        'cloud_cover_pct': series('cloud_cover'),
        'precipitation_mm': series('precipitation'),
        'apparent_temperature_c': series('apparent_temperature'),
    }
