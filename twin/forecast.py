"""Forecast physics: where a hazard is headed, and how many hours out.

    sample -> advect -> detect -> threshold

All four are pure functions over plain data - no LLM, no database session -
the same separation `scoring.py` enforces for the triage agent's risk number.
The forecast agent's LLM step (`forecast_nodes.py`) narrates what these
functions already decided; it never recomputes a projection or an hour.

**Two hazard mechanics, handled differently, on purpose:**

- **Rain moves.** A rain source is carried downwind hour by hour - simple
  advection, source position + wind vector x elapsed time - and projected
  onto whichever of the city's actual H3 cells the resulting point lands
  near.
- **Heat does not move.** It is read *in place* at each lattice point, and
  reported once, on the hour it first crosses a threshold - not on every hot
  hour afterward. A city under a heat dome does not need twelve identical
  "still hot" flags.

**Rain intensity is not attenuated or intensified in transit.** The value
carried forward at hour h is whatever the source lattice point showed for
hour h - a real simplification (no convective growth/decay is modelled), and
why `RAIN_SOURCE_MM_H` acts only as a cheap pre-filter ("is this point worth
projecting at all") while `RAIN_ARRIVAL_MM_H`/`RAIN_SEVERE_MM_H` are the
severity *bands* an already-projected event is classified into - the same
band-not-gate convention `scoring.py`'s `STATUS_FLOORS` uses, chosen because
a hard "must exceed a higher threshold after not changing" gate can never
fire.

**Wind direction convention** (the bug this file exists partly to prevent a
repeat of): `wind_direction_10m` is the compass bearing the wind is blowing
*FROM*. A hazard travels the *opposite* way - `(wind_dir + 180) % 360` - and
that conversion happens in exactly one function, `_downwind_bearing`, with a
unit-checkable name, rather than being inlined and silently miscopied
somewhere.
"""

import math
from datetime import timedelta

import h3

from .geo import destination, haversine_m

# --- declared thresholds, all arguable, all named ----------------------------
MAX_LEAD_HOURS = 12
RAIN_SOURCE_MM_H = 2.0      # pre-filter: below this, not worth projecting at all
RAIN_ARRIVAL_MM_H = 4.0     # severity band floor: "warning"
RAIN_SEVERE_MM_H = 12.0     # severity band floor: "critical"
HEAT_WATCH_C = 38.0         # apparent temperature
HEAT_SEVERE_C = 42.0
# A source's cloud cover at or above this boosts confidence in a rain
# projection - overcast plus measurable rain is a more coherent system than
# rain alone, which can be a single noisy hourly reading.
CLOUD_SUPPORT_PCT = 70.0

MAX_PROJECTION_KM = 220.0   # wind_speed_kmh * MAX_LEAD_HOURS realistically caps near here anyway
SNAP_RADIUS_KM = 2.5        # the "~1.5 km error bar" this project's own field notes cite, with margin
MAX_CELLS_PER_PROJECTION = 6
GROUP_RESOLUTION = 6        # h3 res-6 cells are ~6 km across - the doc's own "group within 6 km"
CONFIDENCE_FLOOR = 0.35


def sample(windfield_by_sample):
    """Pass-through, named to match the doc's own pipeline stage - the real

    per-point series already comes out of `ingest/windfield.py` in the shape
    this module needs. Kept as a function (not inlined) so the graph node
    that calls it has a stage to call, matching triage's `gather`/`extract`
    split.
    """
    return windfield_by_sample or {}


def advect(cell_points, windfield_by_sample, max_lead_hours=None):
    """Every hour's rain/heat source, projected onto the city's actual cells.

    `cell_points`: list of (h3_index, lat, lon) for one city's seeded grid.
    Returns a flat list of raw projections - NOT yet grouped into events,
    that is `detect()`'s job. One projection: {h3_index, hazard_type, hour,
    value, confidence, source_sample, distance_km}.
    """
    max_lead_hours = max_lead_hours or MAX_LEAD_HOURS
    projections = []

    for sample_h3, field in (windfield_by_sample or {}).items():
        times = field.get('times') or []
        n = min(len(times), max_lead_hours + 1)
        sample_lat, sample_lon = field.get('lat'), field.get('lon')
        if sample_lat is None or sample_lon is None:
            continue

        for hour in range(1, n):
            wind_speed = _at(field, 'wind_speed_kmh', hour)
            wind_dir = _at(field, 'wind_direction_deg', hour)
            cloud = _at(field, 'cloud_cover_pct', hour)
            rain = _at(field, 'precipitation_mm', hour)
            apparent_temp = _at(field, 'apparent_temperature_c', hour)

            if apparent_temp is not None and apparent_temp >= HEAT_WATCH_C:
                for h3_index, _lat, _lon, distance in _nearby_cells(
                        cell_points, sample_lat, sample_lon, SNAP_RADIUS_KM):
                    projections.append({
                        'h3_index': h3_index, 'hazard_type': 'heat_wave', 'hour': hour,
                        'value': apparent_temp, 'confidence': 0.8,  # in-place reading, not projected - high confidence
                        'source_sample': sample_h3, 'distance_km': round(distance, 2),
                    })

            if (rain is not None and rain >= RAIN_SOURCE_MM_H
                    and wind_speed and wind_dir is not None):
                travel_km = wind_speed * hour
                if travel_km > MAX_PROJECTION_KM:
                    continue
                bearing = _downwind_bearing(wind_dir)
                target_lon, target_lat = destination(sample_lat, sample_lon, bearing, travel_km * 1000)
                confidence = _rain_confidence(hour, wind_speed, cloud)
                for h3_index, _lat, _lon, distance in _nearby_cells(
                        cell_points, target_lat, target_lon, SNAP_RADIUS_KM):
                    projections.append({
                        'h3_index': h3_index, 'hazard_type': 'flood', 'hour': hour,
                        'value': rain, 'confidence': confidence,
                        'source_sample': sample_h3, 'distance_km': round(distance, 2),
                    })

    return projections


def _downwind_bearing(wind_from_deg):
    """The bearing a hazard travels, given the compass bearing wind blows

    FROM. Named and isolated on purpose - see the module docstring.
    """
    return (wind_from_deg + 180.0) % 360.0


def _rain_confidence(hour, wind_speed_kmh, cloud_pct):
    """0-1. Decays with lead time (further out is less certain) and in light

    wind (a becalmed system's future position is genuinely less predictable
    than a brisk one's); boosted when cloud cover corroborates the rain
    reading rather than it being an isolated noisy value.
    """
    time_decay = math.exp(-hour / 8.0)
    wind_confidence = min(1.0, (wind_speed_kmh or 0.0) / 15.0)
    base = 0.85 * time_decay * (0.5 + 0.5 * wind_confidence)
    if (cloud_pct or 0.0) >= CLOUD_SUPPORT_PCT:
        base += 0.12
    return round(max(0.05, min(0.95, base)), 3)


def _at(field, key, index):
    series = field.get(key) or []
    return series[index] if index < len(series) else None


def _nearby_cells(cell_points, lat, lon, radius_km):
    """The city's own cells within `radius_km` of (lat, lon), nearest first,

    capped at `MAX_CELLS_PER_PROJECTION` - one projection lighting up dozens
    of cells would read as an alert covering half the city instead of the
    specific area a moving system is headed toward.
    """
    hits = []
    for h3_index, clat, clon in cell_points:
        distance = haversine_m(lat, lon, clat, clon) / 1000.0
        if distance <= radius_km:
            hits.append((h3_index, clat, clon, distance))
    hits.sort(key=lambda row: row[3])
    return hits[:MAX_CELLS_PER_PROJECTION]


def detect(projections):
    """Raw projections, grouped into events: same hazard, same hour, within

    ~6 km of each other (an h3 resolution-6 parent cell, which is exactly
    that size - reusing it turns "spatial clustering" into a dict key rather
    than a custom algorithm).
    """
    groups = {}
    for projection in projections:
        parent = h3.cell_to_parent(projection['h3_index'], GROUP_RESOLUTION)
        key = (projection['hazard_type'], projection['hour'], parent)
        groups.setdefault(key, []).append(projection)

    events = []
    for (hazard_type, hour, _parent), group in groups.items():
        cells = sorted({p['h3_index'] for p in group})
        worst = max(group, key=lambda p: p['value'] or 0.0)
        events.append({
            'hazard_type': hazard_type,
            'hour': hour,
            'cells': cells,
            'worst_cell': worst['h3_index'],
            'value': worst['value'],
            'confidence': round(max(p['confidence'] for p in group), 3),
            'source_samples': sorted({p['source_sample'] for p in group}),
        })
    return events


def severity_for(hazard_type, value):
    """Band, not gate - see the module docstring. `None` means "not yet

    event-worthy", the same way a triage cluster below `TWIN_FLAG_THRESHOLD`
    never reaches the brief-writer.
    """
    if value is None:
        return None
    if hazard_type == 'flood':
        if value >= RAIN_SEVERE_MM_H:
            return 'critical'
        if value >= RAIN_ARRIVAL_MM_H:
            return 'warning'
        return None
    if hazard_type == 'heat_wave':
        if value >= HEAT_SEVERE_C:
            return 'critical'
        if value >= HEAT_WATCH_C:
            return 'watch'
        return None
    return None


def threshold(events, confidence_floor=None):
    """Events that clear both the severity band and the confidence floor -

    the forecast agent's equivalent of triage's `TWIN_FLAG_THRESHOLD` cutoff,
    and the second of the two conditional edges that keep a quiet forecast
    pass at zero LLM calls.
    """
    confidence_floor = confidence_floor if confidence_floor is not None else CONFIDENCE_FLOOR
    out = []
    for event in events:
        severity = severity_for(event['hazard_type'], event['value'])
        if severity is None or event['confidence'] < confidence_floor:
            continue
        out.append(dict(event, severity=severity))
    out.sort(key=lambda e: (e['severity'] == 'critical', e['confidence']), reverse=True)
    return out


def arrival_time(now, hour):
    return now + timedelta(hours=hour)
