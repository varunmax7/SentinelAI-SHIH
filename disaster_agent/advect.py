"""Step 2 - PROJECT: deterministic downwind propagation, no LLM involved.

    risk(target, hazard, horizon) = sum over source regions of
        source_strength * bearing_alignment * distance_match

This is a simplified Gaussian-plume-style advection: a region with an elevated
hazard signal "throws" that signal along the direction its wind is blowing
*toward* (meteorological wind direction is reported as where the wind comes
*from*, so the hazard travels at `wind_dir + 180`), out to the distance the
wind would carry it in a given horizon. Any other watched region that falls
within a bearing cone and a distance window of that projection accumulates a
share of the risk, weighted by how well-aligned and how well-distanced it is.

Everything here is arithmetic over the numbers `ingest.py` measured. No numeric
score, coordinate or region name is invented - the LLM step downstream is
handed these numbers and may only narrate them (see schemas.py), never
recompute or override them. That separation is deliberate: see
twin/agent/schemas.py for the same principle applied to the triage agent.
"""

import math

from . import config as agent_config

EARTH_RADIUS_M = 6371000.0

# Hazard types this deterministic model can actually derive from wind, cloud
# and heat signal. `tsunami`, `earthquake` and `air_quality` are left in a
# region's `hazard_bias` for context (they matter to what a region can
# experience) but this agent has no seismic or particulate ingest, so it never
# manufactures a source signal for them - an honest gap beats a fabricated one.
COMPUTABLE_HAZARDS = ('cyclone', 'storm_surge', 'flood', 'landslide',
                     'heat_wave', 'wildfire')

# Sub-score normalisation bands - the same "declared threshold" convention as
# twin/scoring.py.
WIND_STORM_MAX_KMH = 90.0
PRESSURE_LOW_HPA, PRESSURE_NORMAL_HPA = 985.0, 1015.0
RAIN_FLOOD_MAX_MM = 40.0
CLOUD_FLOOD_WEIGHT = 0.3
HEAT_MIN_C, HEAT_MAX_C = 28.0, 46.0
# A projected distance is accepted within +/-max(60%, 50km) of the wind's
# theoretical travel distance for that horizon - hazards fan out, they do not
# arrive at a single point.
MIN_DISTANCE_TOLERANCE_KM = 50.0
MAX_PROJECTION_KM = 900.0


def _clamp(v, low=0.0, high=100.0):
    return max(low, min(high, v))


def _normalise(value, low, high):
    if high == low:
        return 0.0
    return _clamp((float(value) - low) / (high - low) * 100.0)


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Initial compass bearing from point 1 to point 2, degrees 0-360."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * (EARTH_RADIUS_M / 1000.0) * math.asin(min(1.0, math.sqrt(a)))


def _bearing_delta(a, b):
    d = abs((a % 360.0) - (b % 360.0))
    return min(d, 360.0 - d)


# --- source signal strength ---------------------------------------------------
def source_strengths(signal):
    """{hazard_type: 0-100} for every computable hazard this region is biased

    toward. A region never generates a signal for a hazard type outside its
    own `hazard_bias` - Rajasthan does not get a cyclone source just because
    the maths would run.
    """
    strengths = {}
    biased = set(signal.get('hazard_bias') or ())
    wind = signal.get('wind_speed_kmh') or 0.0
    pressure = signal.get('surface_pressure_hpa')
    rain = (signal.get('precipitation_mm') or 0.0) + (signal.get('rain_forecast_3h_mm') or 0.0)
    cloud = signal.get('cloud_cover_pct') or 0.0
    temp = signal.get('temperature_c')
    ffwi = signal.get('fire_weather_index')

    if 'cyclone' in biased or 'storm_surge' in biased:
        wind_score = _normalise(wind, 20.0, WIND_STORM_MAX_KMH)
        pressure_score = (_normalise(PRESSURE_NORMAL_HPA - pressure, 0.0,
                                     PRESSURE_NORMAL_HPA - PRESSURE_LOW_HPA)
                          if pressure is not None else 0.0)
        rain_score = _normalise(rain, 0.0, RAIN_FLOOD_MAX_MM)
        storm = _clamp(0.45 * wind_score + 0.35 * pressure_score + 0.20 * rain_score)
        if 'cyclone' in biased:
            strengths['cyclone'] = storm
        if 'storm_surge' in biased:
            strengths['storm_surge'] = storm

    if 'flood' in biased or 'landslide' in biased:
        flood = _clamp(_normalise(rain, 0.0, RAIN_FLOOD_MAX_MM) * (1.0 - CLOUD_FLOOD_WEIGHT)
                       + _normalise(cloud, 40.0, 100.0) * CLOUD_FLOOD_WEIGHT)
        if 'flood' in biased:
            strengths['flood'] = flood
        if 'landslide' in biased:
            # Saturated ground makes a slope let go; weighted slightly higher
            # than the flat-ground flood score for the same rainfall.
            strengths['landslide'] = _clamp(flood * 1.1)

    if 'heat_wave' in biased and temp is not None:
        strengths['heat_wave'] = _normalise(temp, HEAT_MIN_C, HEAT_MAX_C)

    if 'wildfire' in biased and ffwi is not None:
        strengths['wildfire'] = ffwi

    return strengths


# --- projection ----------------------------------------------------------------
def project_hotspots(signals, horizons=None, threshold=None):
    """Every (region, hazard_type) pair whose projected risk clears the

    hotspot threshold, one entry per pair at its highest-risk horizon, ranked
    by risk descending.
    """
    horizons = horizons or agent_config.HORIZONS
    threshold = threshold if threshold is not None else agent_config.HOTSPOT_THRESHOLD
    by_slug = {s['slug']: s for s in signals}

    best = {}  # (target_slug, hazard_type) -> hotspot dict
    for source in signals:
        strengths = source_strengths(source)
        for hazard_type, strength in strengths.items():
            if strength < agent_config.SOURCE_SIGNAL_MIN:
                continue
            for horizon in horizons:
                for target_slug, contribution, detail in _project_one(
                        source, hazard_type, strength, horizon, by_slug):
                    key = (target_slug, hazard_type)
                    existing = best.get(key)
                    if existing is None or contribution['risk_score'] > existing['risk_score']:
                        target = by_slug[target_slug]
                        best[key] = dict(contribution, target_slug=target_slug,
                                         target_name=target['name'], target_state=target['state'],
                                         target_lat=target['lat'], target_lon=target['lon'],
                                         hazard_type=hazard_type, horizon_hours=horizon,
                                         sources=[detail])
                    elif existing['horizon_hours'] == horizon:
                        existing['risk_score'] = _clamp(
                            existing['risk_score'] + contribution['risk_score'] * 0.4)
                        existing['sources'].append(detail)

    hotspots = [h for h in best.values() if h['risk_score'] >= threshold]
    hotspots.sort(key=lambda h: h['risk_score'], reverse=True)
    for h in hotspots:
        h['sources'].sort(key=lambda s: s['contribution'], reverse=True)
        # How long this is expected to last, from the same hourly forecast the
        # score came from. Attached to the hotspot (not recomputed downstream)
        # so the brief, the API and the stored row all quote one window.
        _attach_window(h, by_slug)
    return hotspots


def _attach_window(hotspot, by_slug):
    """The hazard window for the region the hotspot is *about*.

    Deliberately the target's own forecast, not the upwind source's: an
    analyst reading "Patna, flood, eases by 12:00" needs Patna's timing, not
    the timing of the region that threw the signal at it.

    A target with no forecast of its own gets no window rather than a
    borrowed one. It can only have become a target by being ingested, so this
    is defensive - but substituting another region's timing here would be
    exactly the kind of quiet fabrication the rest of this package refuses.
    """
    from . import window as hazard_window

    target = by_slug.get(hotspot['target_slug'])
    if target is None:
        hotspot['window'] = None
        hotspot['window_text'] = None
        return
    span = hazard_window.hazard_window(target, hotspot['hazard_type'])
    hotspot['window'] = span
    hotspot['window_text'] = hazard_window.describe(span, hotspot['hazard_type'])


def downwind_candidates(source, hazard_type, strength, by_slug, horizons=None):
    """Every other watched region this source's signal is currently pointed

    at, deduped to the soonest horizon each appears at. Same bearing/distance
    math as `project_hotspots`, just not gated by `HOTSPOT_THRESHOLD` - this is
    what the dashboard's sub-threshold "who might this affect if it grows"
    dropdown is built from, so an analyst reviewing a below-threshold signal
    can still see which regions are in its path before deciding whether to
    alert one pre-emptively.
    """
    horizons = horizons or agent_config.HORIZONS
    best = {}
    for horizon in horizons:
        for target_slug, _contribution, _detail in _project_one(
                source, hazard_type, strength, horizon, by_slug):
            if target_slug == source['slug']:
                continue  # origin/self is not a "downwind" target
            if target_slug not in best or horizon < best[target_slug]['horizon_hours']:
                target = by_slug[target_slug]
                best[target_slug] = {
                    'slug': target_slug, 'name': target['name'], 'state': target['state'],
                    'lat': target['lat'], 'lon': target['lon'], 'horizon_hours': horizon,
                }
    return sorted(best.values(), key=lambda t: t['horizon_hours'])


def _project_one(source, hazard_type, strength, horizon, by_slug):
    """Yield (target_slug, {'risk_score': ...}, source_detail) for one

    source region's signal projected at one horizon.
    """
    wind_speed = source.get('wind_speed_kmh') or 0.0
    wind_dir = source.get('wind_dir_deg')
    target_bearing = (wind_dir + 180.0) % 360.0 if wind_dir is not None else None
    travel_km = min(wind_speed * horizon, MAX_PROJECTION_KM)

    # Local persistence: the source region itself stays at risk from its own
    # signal, decaying gently as the horizon stretches past "now".
    if hazard_type in (source.get('hazard_bias') or ()):
        decay = 1.0 / (1.0 + horizon / 12.0)
        yield source['slug'], {'risk_score': _clamp(strength * decay)}, {
            'region': source['name'], 'state': source['state'],
            'role': 'origin', 'contribution': strength * decay,
            'wind_speed_kmh': wind_speed, 'wind_dir_deg': wind_dir,
            'cloud_cover_pct': source.get('cloud_cover_pct'),
            'fire_weather_index': source.get('fire_weather_index'),
            'temperature_c': source.get('temperature_c'),
        }

    if target_bearing is None or travel_km <= 1.0:
        return

    tolerance_km = max(travel_km * 0.6, MIN_DISTANCE_TOLERANCE_KM)
    for target_slug, target in by_slug.items():
        if target_slug == source['slug']:
            continue
        if hazard_type not in (target.get('hazard_bias') or ()):
            continue
        bearing = _bearing_deg(source['lat'], source['lon'], target['lat'], target['lon'])
        delta = _bearing_delta(target_bearing, bearing)
        if delta > agent_config.BEARING_TOLERANCE_DEG:
            continue
        distance_km = _haversine_km(source['lat'], source['lon'], target['lat'], target['lon'])
        mismatch = abs(distance_km - travel_km)
        if mismatch > tolerance_km:
            continue
        alignment = 1.0 - delta / agent_config.BEARING_TOLERANCE_DEG
        distance_weight = 1.0 - mismatch / tolerance_km
        contribution = strength * alignment * distance_weight
        if contribution < 1.0:
            continue
        yield target_slug, {'risk_score': _clamp(contribution)}, {
            'region': source['name'], 'state': source['state'],
            'role': 'upwind source', 'contribution': contribution,
            'distance_km': round(distance_km, 1),
            'bearing_alignment_pct': round(alignment * 100.0, 0),
            'wind_speed_kmh': wind_speed, 'wind_dir_deg': wind_dir,
            'cloud_cover_pct': source.get('cloud_cover_pct'),
            'fire_weather_index': source.get('fire_weather_index'),
            'temperature_c': source.get('temperature_c'),
        }
