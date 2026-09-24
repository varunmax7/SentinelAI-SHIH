"""Anomaly baselines: is this reading unusual for *this* place?

A flat "38 degC is hot" ignores that 38 degC is an ordinary May afternoon in
Hyderabad and a genuine anomaly for Bengaluru's climate. This module compares
a live reading against a sample point's own multi-year climatology, in
standard deviations (sigma), so "unusual" means something specific and
arguable rather than a global threshold pretending both cities are the same
place.

**Scope of this baseline, stated plainly:**

- It is an **annual** climatology (mean/std over `TWIN_BASELINE_YEARS` years
  of daily readings), not day-of-year binned. A June downpour is judged
  against the point's whole-year normal, not a June-specific one. Binning by
  month is the natural next step - it only changes the backfill script and
  the lookup key, not this module's shape.
- It uses the same coarse H3 resolution-6 sample points
  `ingest/open_meteo.py` already shares a weather reading across every child
  cell with (`sample_cells()`). A baseline is a 5-year statistic, not a live
  measurement, so it does not need per-cell precision, and computing it at
  805-cells-per-city precision would mean 805x the archive calls for no
  discriminating power.
- **Rain sigma compares the next-24h forecast total against the baseline's
  daily total**, not "rain that has actually fallen today" - Open-Meteo's
  forecast adapter does not currently fetch a same-day running total, and
  the 24h-forecast horizon is the closest existing figure to "a day's worth
  of rain" the engine already computes. Documented here so the comparison is
  never mistaken for something more precise than it is.
- **Temperature sigma compares the current reading against the baseline's
  daily *maximum*** - a deliberately conservative comparison, since a
  midday reading is usually below that day's eventual peak, so this
  understates rather than overstates how anomalous a moment is.
"""

import statistics
from datetime import datetime, timedelta

import requests

from . import config as twin_config

ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
MIN_SAMPLE_DAYS = 30  # below this, a mean/std is noise, not a baseline


def fetch_climatology(lat, lon, years=None, timeout=None):
    """Mean/std of daily rainfall and daily max temperature at (lat, lon),

    over the last `years` years. Returns None on any failure - a bad point
    must never abort the rest of a backfill run.
    """
    years = years or twin_config.BASELINE_YEARS
    # Archive calls return years of daily data in one response and run
    # offline (the backfill script), never on a request path, so they get a
    # much longer budget than the global HTTP timeout.
    timeout = timeout or twin_config.HTTP_TIMEOUT_S * 6

    end = datetime.utcnow().date() - timedelta(days=3)  # archive lags a few days
    try:
        start = end.replace(year=end.year - years)
    except ValueError:  # Feb 29 with no leap year that far back
        start = end.replace(year=end.year - years, day=28)

    params = {
        'latitude': '%.4f' % lat,
        'longitude': '%.4f' % lon,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'daily': 'precipitation_sum,temperature_2m_max',
        'timezone': 'UTC',
    }

    try:
        response = requests.get(ARCHIVE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001
        return None

    daily = payload.get('daily') or {}
    rain = [v for v in (daily.get('precipitation_sum') or []) if v is not None]
    temp = [v for v in (daily.get('temperature_2m_max') or []) if v is not None]
    if len(rain) < MIN_SAMPLE_DAYS or len(temp) < MIN_SAMPLE_DAYS:
        return None

    return {
        'years': years,
        'sample_days': len(rain),
        'rain_daily_mean_mm': statistics.fmean(rain),
        'rain_daily_std_mm': statistics.pstdev(rain) or 0.0001,
        'temp_max_mean_c': statistics.fmean(temp),
        'temp_max_std_c': statistics.pstdev(temp) or 0.0001,
    }


def sigma(value, mean, std):
    """Standard deviations `value` sits from `mean`, or None if any input

    is missing. `None` means unmeasured; it must never be silently read as 0.
    """
    if value is None or mean is None or not std:
        return None
    return (value - mean) / std


def label_for(sigma_value):
    if sigma_value is None:
        return None
    if sigma_value >= twin_config.ANOMALY_SIGMA_ALERT:
        return 'alert'
    if sigma_value >= twin_config.ANOMALY_SIGMA_WATCH:
        return 'watch'
    return 'normal'


def anomaly_for_cell(baseline, rain_forecast_24h_mm, temperature_c):
    """One cell's anomaly reading, or None if it has no baseline yet.

    Only a *positive* sigma (wetter/hotter than normal) is treated as
    noteworthy here - the twin's hazards are heavy rain and heat, not their
    opposites, so an unusually dry or cool reading is reported in the raw
    numbers but never labelled `watch`/`alert`.
    """
    if baseline is None:
        return None

    rain_sigma = sigma(rain_forecast_24h_mm, baseline.rain_daily_mean_mm, baseline.rain_daily_std_mm)
    temp_sigma = sigma(temperature_c, baseline.temp_max_mean_c, baseline.temp_max_std_c)

    positive = [(name, value) for name, value in (('rain', rain_sigma), ('temp', temp_sigma))
               if value is not None and value > 0]
    dominant_metric, dominant_sigma = max(positive, key=lambda kv: kv[1]) if positive else (None, None)

    return {
        'rain_sigma': round(rain_sigma, 2) if rain_sigma is not None else None,
        'temp_sigma': round(temp_sigma, 2) if temp_sigma is not None else None,
        'dominant_metric': dominant_metric,
        'sigma': round(dominant_sigma, 2) if dominant_sigma is not None else None,
        'label': label_for(dominant_sigma),
        'baseline_years': baseline.years,
        'baseline_sample_days': baseline.sample_days,
    }


def baselines_by_sample_cell(models, city):
    """{sample_h3: TwinBaseline row} for one city, one query."""
    rows = models.TwinBaseline.query.filter_by(city_id=city.id).all()
    return {row.sample_h3: row for row in rows}
