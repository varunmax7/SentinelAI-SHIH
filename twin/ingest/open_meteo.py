"""Open-Meteo adapters: forecast, air quality, river discharge, elevation.

All keyless, all CC BY 4.0 - attribution `Open-Meteo.com (CC BY 4.0)` is a
licence condition and is rendered in the console footer.

**Sampling.** Querying 919 points per city per cycle would be both rude and
slow. Rainfall and AQI vary over kilometres, not hundreds of metres, so the
adapters sample at H3 resolution 6 (~36 km^2, roughly 6 km across) and every
res-8 cell reads its parent's sample. That is a declared approximation; the
per-cell `raw_inputs` records which sample point a cell used so the drawer can
show it.
"""

import h3

from .base import IngestAdapter

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_QUALITY_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
FLOOD_URL = 'https://flood-api.open-meteo.com/v1/flood'
ELEVATION_URL = 'https://api.open-meteo.com/v1/elevation'
OPEN_ELEVATION_URL = 'https://api.open-elevation.com/api/v1/lookup'

SAMPLE_RESOLUTION = 6
# Open-Meteo caps a multi-location request; keep well inside it.
MAX_POINTS_PER_CALL = 60


def sample_cells(h3_indexes, resolution=SAMPLE_RESOLUTION):
    """Map every cell to a coarse sample cell. Returns (sample_index_by_cell, points).

    `points` is an ordered list of (sample_index, lat, lon) - the actual
    coordinates that get queried.
    """
    by_cell = {}
    samples = {}
    for index in h3_indexes:
        parent = h3.cell_to_parent(index, resolution)
        by_cell[index] = parent
        if parent not in samples:
            lat, lon = h3.cell_to_latlng(parent)
            samples[parent] = (lat, lon)
    points = [(key, value[0], value[1]) for key, value in samples.items()]
    return by_cell, points


def _as_list(payload):
    """Open-Meteo returns an object for one location and an array for many."""
    if isinstance(payload, list):
        return payload
    return [payload]


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


class ForecastAdapter(IngestAdapter):
    """Current precipitation + temperature, and hourly rain for the horizons."""

    source_key = 'open_meteo_forecast'
    ttl_seconds = 15 * 60

    def fetch(self, points=None, **kwargs):
        points = points or []
        results = {}
        for chunk in _chunks(points, MAX_POINTS_PER_CALL):
            payload = self.get_json(FORECAST_URL, params={
                'latitude': ','.join('%.4f' % p[1] for p in chunk),
                'longitude': ','.join('%.4f' % p[2] for p in chunk),
                'current': 'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m',
                'hourly': 'precipitation',
                'forecast_days': 2,
                'timezone': 'UTC',
            })
            for (key, _lat, _lon), entry in zip(chunk, _as_list(payload)):
                results[key] = _parse_forecast(entry)
        return results or None


def _parse_forecast(entry):
    current = entry.get('current') or {}
    hourly = (entry.get('hourly') or {}).get('precipitation') or []

    def ahead(hours):
        # `hourly` starts at 00:00 today, so index 0 is not "now". Open-Meteo
        # gives no cursor, so use the count of elapsed hours from `current.time`
        # when present and fall back to the head of the array.
        start = _hour_index(entry)
        window = hourly[start:start + hours]
        return float(sum(v or 0.0 for v in window))

    return {
        'temperature_c': current.get('temperature_2m'),
        'humidity': current.get('relative_humidity_2m'),
        'wind_speed_kmh': current.get('wind_speed_10m'),
        'weather_code': current.get('weather_code'),
        'rain_now_mm_h': current.get('precipitation') or 0.0,
        'rain_forecast_mm': {
            '0': current.get('precipitation') or 0.0,
            '3': ahead(3),
            '6': ahead(6),
            '24': ahead(24),
        },
    }


def _hour_index(entry):
    times = (entry.get('hourly') or {}).get('time') or []
    current_time = (entry.get('current') or {}).get('time')
    if current_time and times:
        prefix = current_time[:13]  # YYYY-MM-DDTHH
        for i, stamp in enumerate(times):
            if stamp[:13] == prefix:
                return i
    return 0


class AirQualityAdapter(IngestAdapter):
    source_key = 'open_meteo_air_quality'
    ttl_seconds = 30 * 60

    def fetch(self, points=None, **kwargs):
        points = points or []
        results = {}
        for chunk in _chunks(points, MAX_POINTS_PER_CALL):
            payload = self.get_json(AIR_QUALITY_URL, params={
                'latitude': ','.join('%.4f' % p[1] for p in chunk),
                'longitude': ','.join('%.4f' % p[2] for p in chunk),
                'current': 'us_aqi,pm2_5,pm10',
                'timezone': 'UTC',
            })
            for (key, _lat, _lon), entry in zip(chunk, _as_list(payload)):
                current = entry.get('current') or {}
                results[key] = {
                    'aqi': current.get('us_aqi'),
                    'pm2_5': current.get('pm2_5'),
                    'pm10': current.get('pm10'),
                }
        return results or None


class FloodAdapter(IngestAdapter):
    """GloFAS river discharge.

    This is a **model anomaly, not an official CWC gauge reading**, and must be
    labelled as such everywhere it is shown.
    """

    source_key = 'open_meteo_flood'
    ttl_seconds = 6 * 3600

    def fetch(self, latitude=None, longitude=None, **kwargs):
        payload = self.get_json(FLOOD_URL, params={
            'latitude': '%.4f' % latitude,
            'longitude': '%.4f' % longitude,
            'daily': 'river_discharge,river_discharge_mean',
            'forecast_days': 2,
        })
        daily = payload.get('daily') or {}
        discharge = (daily.get('river_discharge') or [None])[0]
        mean = (daily.get('river_discharge_mean') or [None])[0]
        return {
            'river_discharge': discharge,
            'river_discharge_mean': mean,
            'anomaly_score': _discharge_anomaly(discharge, mean),
            'note': 'GloFAS model anomaly, not an official CWC gauge reading',
        }


def _discharge_anomaly(discharge, mean):
    """0-100 anomaly. 0 when at or below the seasonal mean, 100 at 3x mean."""
    if not discharge or not mean or mean <= 0:
        return 0.0
    ratio = float(discharge) / float(mean)
    if ratio <= 1.0:
        return 0.0
    return max(0.0, min(100.0, (ratio - 1.0) / 2.0 * 100.0))


# The elevation endpoint accepts up to 100 coordinate pairs per call.
ELEVATION_BATCH = 100
# Open-Meteo rate-limits by request count, not by coordinate count. A city needs
# ten batches; firing them back to back trips a 429 and loses the lot.
ELEVATION_PAUSE_S = 1.2


class ElevationAdapter(IngestAdapter):
    """Terrain elevation for the low-lying sub-score.

    Static data, so it is cached for a week and kept for three months past that.
    One call handles **one batch**, deliberately: batching inside `fetch` would
    put ten HTTP calls behind a single cache key, and a rate-limit on the tenth
    would throw away the nine that succeeded. Per-batch keys make the seed
    resumable - re-run it and only the missing batches go back to the network.
    """

    source_key = 'open_meteo_elevation'
    ttl_seconds = 7 * 24 * 3600
    stale_grace_seconds = 90 * 24 * 3600

    def __init__(self, *args, **kwargs):
        super(ElevationAdapter, self).__init__(*args, **kwargs)
        # Terrain lookups run at seed time, never on the request path, so they
        # can afford to wait longer than the global request-path budget.
        self.timeout = max(self.timeout, 30.0)

    def cache_key(self, points=None, **kwargs):
        # Key on the cells themselves so a batch is reusable regardless of the
        # order the seeder happened to hand them over in.
        keys = sorted(p[0] for p in (points or []))
        return super(ElevationAdapter, self).cache_key(cells=keys)

    def fetch(self, points=None, **kwargs):
        points = points or []
        if not points:
            return None
        payload = self.get_json(ELEVATION_URL, params={
            'latitude': ','.join('%.5f' % p[1] for p in points),
            'longitude': ','.join('%.5f' % p[2] for p in points),
        })
        elevations = payload.get('elevation') or []
        results = {}
        for (key, _lat, _lon), value in zip(points, elevations):
            results[key] = value
        return results or None


class OpenElevationAdapter(IngestAdapter):
    """Fallback terrain source, used when Open-Meteo's daily quota is spent.

    Terrain is the one static input the twin genuinely needs to be *different*
    per cell - if every cell falls back to the neutral 50, the low-lying term
    stops discriminating and flood risk flattens across the city. A second
    keyless provider is cheap insurance against one quota.
    """

    source_key = 'open_elevation'
    ttl_seconds = 7 * 24 * 3600
    stale_grace_seconds = 90 * 24 * 3600

    def __init__(self, *args, **kwargs):
        super(OpenElevationAdapter, self).__init__(*args, **kwargs)
        self.timeout = max(self.timeout, 30.0)

    def cache_key(self, points=None, **kwargs):
        keys = sorted(p[0] for p in (points or []))
        return super(OpenElevationAdapter, self).cache_key(cells=keys)

    def fetch(self, points=None, **kwargs):
        import requests

        points = points or []
        if not points:
            return None
        response = requests.post(
            OPEN_ELEVATION_URL,
            json={'locations': [{'latitude': p[1], 'longitude': p[2]} for p in points]},
            timeout=self.timeout,
            headers={'Content-Type': 'application/json'},
        )
        response.raise_for_status()
        rows = response.json().get('results') or []
        # The API preserves request order, but it also echoes coordinates, so
        # zip on order and trust the echo only for length.
        results = {}
        for (key, _lat, _lon), row in zip(points, rows):
            elevation = row.get('elevation')
            if elevation is not None:
                results[key] = float(elevation)
        return results or None


def fetch_elevations(points, force=False, pause=ELEVATION_PAUSE_S):
    """Elevation for many points, one rate-limited batch at a time.

    Returns (values_by_key, results). Each batch is tried against Open-Meteo and
    then, if that fails, against Open-Elevation. A batch that fails on both is
    simply absent from the mapping - the caller fills what it can and the next
    run picks up the rest, rather than the whole city ending up with no terrain
    data.
    """
    import time

    providers = [ElevationAdapter(), OpenElevationAdapter()]
    values = {}
    results = []
    batches = list(_chunks(list(points), ELEVATION_BATCH))

    for i, batch in enumerate(batches):
        hit_network = False
        for adapter in providers:
            result = adapter.run(points=batch, force=force)
            results.append(result)
            hit_network = hit_network or bool(result.latency_ms)
            if result.ok and result.data:
                values.update(result.data)
                break
        # Only pause between batches that actually hit the network.
        if pause and i < len(batches) - 1 and hit_network:
            time.sleep(pause)
    return values, results
