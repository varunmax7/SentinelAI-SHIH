"""Step 1 - INGEST: live wind, cloud and heat signal for every watched region.

This is deliberately **not** a scrape of the Windy iframes on the analyst
dashboard. Windy's embed is a cross-origin canvas - there is no pixel or DOM
access to "read wind direction off the map" even in principle. Instead this
adapter goes to Open-Meteo (the same class of open numerical-weather-model
data Windy's own temperature/wind, satellite and fire-danger layers are
rendered from), keyless and free, for the fields that matter to the three
panels:

  * live temperature map / wind        -> wind_speed_10m, wind_direction_10m
  * live satellite view (clouds)       -> cloud_cover, precipitation
  * fire danger map                    -> Fosberg Fire Weather Index, derived
                                           from temperature, humidity and wind

One HTTP call covers every region: Open-Meteo accepts comma-separated
lat/lon lists in a single request.
"""

import math

import requests

from . import config as agent_config
from .regions import as_dicts

CURRENT_FIELDS = (
    'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,'
    'cloud_cover,precipitation,surface_pressure,weather_code'
)


def fetch_region_signals(regions=None, timeout=None):
    """One live signal dict per region. Never raises - a failed HTTP call

    degrades to an empty list, and the caller (the projection step) treats no
    signal as no hotspot rather than crashing the cycle.
    """
    regions = regions if regions is not None else as_dicts()
    if not regions:
        return []

    params = {
        'latitude': ','.join('%.4f' % r['lat'] for r in regions),
        'longitude': ','.join('%.4f' % r['lon'] for r in regions),
        'current': CURRENT_FIELDS,
        'hourly': 'precipitation,cloud_cover',
        'forecast_days': 2,
        'timezone': 'UTC',
    }

    try:
        response = requests.get(
            agent_config.FORECAST_URL, params=params,
            timeout=timeout or agent_config.HTTP_TIMEOUT_S)
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001 - a bad ingest must never kill the cycle
        return []

    entries = payload if isinstance(payload, list) else [payload]
    signals = []
    for region, entry in zip(regions, entries):
        signal = _parse_entry(region, entry)
        if signal is not None:
            signals.append(signal)
    return signals


def _parse_entry(region, entry):
    current = entry.get('current') or {}
    if not current:
        return None

    temperature_c = current.get('temperature_2m')
    humidity_pct = current.get('relative_humidity_2m')
    wind_speed_kmh = current.get('wind_speed_10m')
    wind_dir_deg = current.get('wind_direction_10m')
    cloud_cover_pct = current.get('cloud_cover')
    precipitation_mm = current.get('precipitation') or 0.0
    surface_pressure_hpa = current.get('surface_pressure')

    signal = dict(region)
    signal.update({
        'temperature_c': temperature_c,
        'humidity_pct': humidity_pct,
        'wind_speed_kmh': wind_speed_kmh,
        'wind_dir_deg': wind_dir_deg,
        'cloud_cover_pct': cloud_cover_pct,
        'precipitation_mm': precipitation_mm,
        'surface_pressure_hpa': surface_pressure_hpa,
        'weather_code': current.get('weather_code'),
        'rain_forecast_3h_mm': _rain_ahead(entry, hours=3),
        'fire_weather_index': fosberg_fire_weather_index(
            temperature_c, humidity_pct, wind_speed_kmh),
    })
    return signal


def _rain_ahead(entry, hours):
    hourly = (entry.get('hourly') or {})
    values = hourly.get('precipitation') or []
    times = hourly.get('time') or []
    current_time = (entry.get('current') or {}).get('time')
    start = 0
    if current_time and times:
        prefix = current_time[:13]
        for i, stamp in enumerate(times):
            if stamp[:13] == prefix:
                start = i
                break
    window = values[start:start + hours]
    return float(sum(v or 0.0 for v in window))


# --- Fosberg Fire Weather Index -----------------------------------------------
# Fosberg (1970), the standard US fire-weather formula: moisture content from
# temperature + relative humidity, combined with wind speed. Raw FFWI rarely
# exceeds ~110 in extreme conditions, so it is rescaled to a 0-100 sub-score
# the same way every other sub-score in this app is (a declared assumption,
# named here so it can be argued with).
FFWI_RAW_MAX = 100.0


def fosberg_fire_weather_index(temperature_c, humidity_pct, wind_speed_kmh):
    """0-100 fire-danger sub-score, or None if inputs are missing."""
    if temperature_c is None or humidity_pct is None or wind_speed_kmh is None:
        return None

    temp_f = temperature_c * 9.0 / 5.0 + 32.0
    rh = max(0.0, min(100.0, humidity_pct))
    wind_mph = wind_speed_kmh * 0.621371

    if rh < 10.0:
        m = 0.03229 + 0.281073 * rh - 0.000578 * rh * temp_f
    elif rh < 50.0:
        m = 2.22749 + 0.160107 * rh - 0.014784 * temp_f
    else:
        m = 21.0606 + 0.005565 * (rh ** 2) - 0.00035 * rh * temp_f - 0.483199 * rh

    m_ratio = m / 30.0
    n = 1.0 - 2.0 * m_ratio + 1.5 * (m_ratio ** 2) - 0.5 * (m_ratio ** 3)
    n = max(0.0, n)

    raw = n * math.sqrt(1.0 + wind_mph ** 2) / 0.3002
    return max(0.0, min(100.0, raw / FFWI_RAW_MAX * 100.0))
