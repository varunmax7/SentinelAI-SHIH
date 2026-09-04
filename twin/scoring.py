"""Risk scoring.

    risk = hazard x vulnerability                        (0-100, clamped)

    hazard        = 0.55*hydro + 0.30*incident + 0.15*env
    vulnerability = 1 + 0.60 * (0.60*terrain + 0.40*infra) / 100    -> 1.0 .. 1.6

Hazard and vulnerability *multiply*. A flat weighted sum leaves every low-lying,
hospital-dense cell permanently in `watch` with zero rain and zero incidents,
which trains operators to ignore the map. Multiplying means a cell only lights
up when something is actually happening to it - vulnerability decides how hard
it is hit, not whether it is hit.

Every sub-score returns 0-100 and every threshold below is a declared
assumption, not a measurement. They are named constants so they can be argued
with.
"""

import math

from . import config as twin_config
from .geo import clamp, normalise

# --- Declared thresholds ---------------------------------------------------
# Rainfall, mm/h. IMD calls >7.5 mm/h heavy and >15 mm/h very heavy; 20 saturates.
RAIN_NOW_MAX_MM_H = 20.0
# Accumulated forecast rain over the horizon, mm.
RAIN_FORECAST_MAX_MM = 60.0
# US AQI. 300 is "hazardous".
AQI_MAX = 300.0
# Heat stress band, degrees C.
HEAT_MIN_C, HEAT_MAX_C = 25.0, 45.0
# Distance to standing water beyond which proximity stops mattering, metres.
WATER_PROXIMITY_MAX_M = 1500.0
# Storm-drain density at which a cell is considered adequately drained, m/km^2.
DRAIN_ADEQUATE_M_PER_KM2 = 8000.0
# Incident load at which the incident sub-score is effectively saturated.
INCIDENT_SATURATION = 2.0


def hydro_sub_score(rain_now_mm_h, rain_forecast_mm, discharge_anomaly, horizon_hours=0):
    """Water hazard: what is falling, what is forecast, what the river is doing."""
    weights = twin_config.HYDRO_WEIGHTS_BY_HORIZON.get(
        horizon_hours, twin_config.HYDRO_WEIGHTS_BY_HORIZON[0])

    now = normalise(rain_now_mm_h or 0.0, 0.0, RAIN_NOW_MAX_MM_H)
    fcst = normalise(rain_forecast_mm or 0.0, 0.0, RAIN_FORECAST_MAX_MM)
    disc = clamp(discharge_anomaly or 0.0)

    return clamp(weights['rain_now'] * now
                 + weights['rain_forecast'] * fcst
                 + weights['discharge'] * disc)


def incident_load(reports, now):
    """Time-decayed weight of the reports inside one cell.

    Each report contributes severity x confidence, decayed exponentially by
    age: an unresolved report stops describing the present after a while, and
    without decay a cell that flooded last Tuesday stays red forever.
    """
    total = 0.0
    for report in reports:
        age_h = max(0.0, (now - report['timestamp']).total_seconds() / 3600.0)
        decay = math.exp(-age_h / twin_config.INCIDENT_DECAY_HOURS)
        total += float(report.get('severity', 0.5)) * float(report.get('confidence', 0.5)) * decay
    return total


def incident_sub_score(own_load, neighbour_load=0.0):
    """Saturating curve over own + discounted neighbour load.

    Neighbours count at 40%: a hotspot is an area, not a hexagon, and reports
    are geocoded to whatever precision the reporter's phone managed.
    """
    combined = own_load + twin_config.INCIDENT_NEIGHBOUR_WEIGHT * neighbour_load
    if combined <= 0:
        return 0.0
    # 1 - e^-x saturates smoothly, so the 20th report in a cell does not swamp
    # the scale for every other cell in the city.
    return clamp(100.0 * (1.0 - math.exp(-combined / INCIDENT_SATURATION)))


def env_sub_score(aqi, temperature_c):
    aqi_score = normalise(aqi or 0.0, 0.0, AQI_MAX)
    heat_score = normalise(temperature_c if temperature_c is not None else HEAT_MIN_C,
                           HEAT_MIN_C, HEAT_MAX_C)
    w = twin_config.ENV_WEIGHTS
    return clamp(w['aqi'] * aqi_score + w['heat'] * heat_score)


def low_lying_score(elevation_m, elev_min, elev_max):
    """100 at the lowest point in the city, 0 at the highest.

    Absolute elevation is meaningless for flooding; relative elevation within
    the same basin is what matters. Returns a neutral 50 when the elevation
    ingest is unavailable rather than pretending the cell is high ground.
    """
    if elevation_m is None or elev_min is None or elev_max is None or elev_max <= elev_min:
        return 50.0
    return clamp(100.0 * (elev_max - elevation_m) / (elev_max - elev_min))


def water_proximity_score(dist_to_water_m):
    if dist_to_water_m is None:
        return 50.0
    return clamp(100.0 * (1.0 - min(dist_to_water_m, WATER_PROXIMITY_MAX_M) / WATER_PROXIMITY_MAX_M))


def drain_gap_score(drain_length_m, area_km2):
    """How under-drained a cell is. No mapped drains at all -> 100."""
    if not area_km2:
        return 50.0
    density = (drain_length_m or 0.0) / area_km2
    return clamp(100.0 * (1.0 - min(density, DRAIN_ADEQUATE_M_PER_KM2) / DRAIN_ADEQUATE_M_PER_KM2))


def terrain_sub_score(low_lying, water_proximity, drain_gap):
    w = twin_config.TERRAIN_WEIGHTS
    return clamp(w['low_lying'] * low_lying
                 + w['water_proximity'] * water_proximity
                 + w['drain_gap'] * drain_gap)


def infra_sub_score(criticality_sum):
    return clamp((criticality_sum or 0.0) * twin_config.ASSET_CRITICALITY_STEP)


def hazard_score(hydro, incident, env):
    w = twin_config.HAZARD_WEIGHTS
    return clamp(w['hydro'] * hydro + w['incident'] * incident + w['env'] * env)


def vulnerability_multiplier(terrain, infra):
    w = twin_config.VULNERABILITY_WEIGHTS
    blended = w['terrain'] * terrain + w['infra'] * infra
    return 1.0 + twin_config.VULNERABILITY_SPAN * (blended / 100.0)


def compose(hydro, incident, env, terrain, infra):
    """Full risk composition. Returns (risk_score, status, vulnerability)."""
    hazard = hazard_score(hydro, incident, env)
    vulnerability = vulnerability_multiplier(terrain, infra)
    risk = clamp(hazard * vulnerability)
    return risk, twin_config.status_for_score(risk), vulnerability


def explain(inputs, sub_scores, risk, vulnerability):
    """Human-readable account of how a score was reached (principle C3).

    Rendered verbatim in the drill-down drawer. Every claim here has to be
    traceable to a value in `raw_inputs`.
    """
    bits = []
    hydro = sub_scores.get('hydro', 0.0)
    if hydro >= 50:
        bits.append("Water hazard is high (%.0f/100): %.1f mm/h falling now, %.0f mm forecast."
                    % (hydro, inputs.get('rain_now_mm_h') or 0.0, inputs.get('rain_forecast_mm') or 0.0))
    elif hydro >= 20:
        bits.append("Moderate water hazard (%.0f/100) from rainfall and river discharge." % hydro)
    else:
        bits.append("Water hazard is low (%.0f/100)." % hydro)

    incidents = inputs.get('incident_count') or 0
    if incidents:
        bits.append("%d recent verified report(s) inside or beside this cell contribute %.0f/100."
                    % (incidents, sub_scores.get('incident', 0.0)))
    else:
        bits.append("No recent verified reports in this cell.")

    env = sub_scores.get('env', 0.0)
    if env >= 40:
        bits.append("Environmental stress %.0f/100 (AQI %s, %s degC)."
                    % (env, _fmt(inputs.get('aqi')), _fmt(inputs.get('temperature_c'))))

    bits.append("Vulnerability multiplier x%.2f - terrain %.0f/100, critical infrastructure %.0f/100."
                % (vulnerability, sub_scores.get('terrain', 0.0), sub_scores.get('infra', 0.0)))
    bits.append("Resulting risk %.0f/100 (%s)." % (risk, twin_config.status_for_score(risk)))
    return " ".join(bits)


def _fmt(value):
    return "n/a" if value is None else ("%.0f" % value)
