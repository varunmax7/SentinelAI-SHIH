"""Static configuration for the Urban Digital Twin.

Everything here is deliberately data, not behaviour: cities, scoring weights and
status bands are the knobs an operator or analyst is most likely to want to
tune, and keeping them in one module means tuning them never requires reading
the engine.

Every environment variable is optional. The twin runs fully keyless; keyed
sources only add layers (see analyst.md §IV.1).
"""

import os


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_flag(name, default=True):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ('0', 'false', 'no', 'off', '')


# --- Feature flags ---------------------------------------------------------
TWIN_ENABLED = _env_flag('TWIN_ENABLED', True)
TWIN_SCHEDULER_ENABLED = _env_flag('TWIN_SCHEDULER_ENABLED', True)

# --- Grid & compute --------------------------------------------------------
H3_RESOLUTION = _env_int('TWIN_H3_RESOLUTION', 8)
# Rings of hexagons around the city centre cell. 3k^2+3k+1 cells; at res 8
# (~0.76 km^2 each) k=17 gives 919 cells ~= a 15 km radius, which covers the
# built-up core of both cities without drowning the client in geometry.
GRID_RINGS = _env_int('TWIN_GRID_RINGS', 17)

COMPUTE_INTERVAL_MIN = _env_int('TWIN_COMPUTE_INTERVAL_MIN', 5)
WEATHER_INTERVAL_MIN = _env_int('TWIN_WEATHER_INTERVAL_MIN', 15)
AIRQUALITY_INTERVAL_MIN = _env_int('TWIN_AIRQUALITY_INTERVAL_MIN', 30)
INCIDENT_INTERVAL_MIN = _env_int('TWIN_INCIDENT_INTERVAL_MIN', 2)

# The horizons the engine scores every cell at, in hours. 0 is "now".
HORIZONS = (0, 3, 6, 24)

# --- Paths & network -------------------------------------------------------
CACHE_DIR = os.environ.get('TWIN_CACHE_DIR', 'data/twin/cache')
BOUNDARY_DIR = os.environ.get('TWIN_BOUNDARY_DIR', 'data/twin/boundaries')
# Kept at or below 8s deliberately: some of these calls sit on the request path
# when a lazy layer is first opened, and a slow upstream must never become a
# slow dashboard.
HTTP_TIMEOUT_S = _env_float('TWIN_HTTP_TIMEOUT_S', 8.0)

CCTV_RADIUS_M = _env_int('TWIN_CCTV_RADIUS_M', 400)
STREETVIEW_RADIUS_M = _env_int('TWIN_STREETVIEW_RADIUS_M', 350)

# --- Optional keyed sources ------------------------------------------------
MAPILLARY_TOKEN = os.environ.get('MAPILLARY_TOKEN', '')
WINDY_WEBCAMS_KEY = os.environ.get('WINDY_WEBCAMS_KEY', '')
TOMTOM_API_KEY = os.environ.get('TOMTOM_API_KEY', '')

# --- Access control --------------------------------------------------------
# Roles allowed to read twin data. Add roles here, never on individual routes.
TWIN_ROLES = ('official', 'analyst', 'admin', 'coordinator')
# Roles allowed to mutate: force a recompute, rebuild the grid.
TWIN_ADMIN_ROLES = ('official', 'admin')


# --- Cities ----------------------------------------------------------------
# `zones` are administrative areas used for the zone filter and the drill-down
# list. Each carries a centre point only; cells are assigned to the nearest
# centre (a Voronoi partition), so every zone is honestly flagged
# boundary_source='approximate' and the UI must say so. Do not present these as
# surveyed ward boundaries.
CITIES = [
    {
        'slug': 'hyderabad',
        'name': 'Hyderabad',
        'state': 'Telangana',
        'center_latitude': 17.3850,
        'center_longitude': 78.4867,
        'default_zoom': 10.6,
        'default_pitch': 45.0,
        'default_bearing': -12.5,
        'zones': [
            ('charminar', 'Charminar', 17.3616, 78.4747),
            ('secunderabad', 'Secunderabad', 17.4399, 78.4983),
            ('kukatpally', 'Kukatpally', 17.4948, 78.3996),
            ('serilingampally', 'Serilingampally', 17.4839, 78.3428),
            ('lb-nagar', 'L. B. Nagar', 17.3457, 78.5522),
            ('khairatabad', 'Khairatabad', 17.4126, 78.4610),
            ('musheerabad', 'Musheerabad', 17.4046, 78.5012),
            ('rajendranagar', 'Rajendranagar', 17.3157, 78.4023),
        ],
    },
    {
        'slug': 'bengaluru',
        'name': 'Bengaluru',
        'state': 'Karnataka',
        'center_latitude': 12.9716,
        'center_longitude': 77.5946,
        'default_zoom': 10.6,
        'default_pitch': 45.0,
        'default_bearing': -12.5,
        'zones': [
            ('east', 'Bengaluru East', 12.9784, 77.6408),
            ('west', 'Bengaluru West', 12.9850, 77.5460),
            ('south', 'Bengaluru South', 12.9081, 77.5855),
            ('yelahanka', 'Yelahanka', 13.1007, 77.5963),
            ('mahadevapura', 'Mahadevapura', 12.9899, 77.6963),
            ('bommanahalli', 'Bommanahalli', 12.8993, 77.6205),
            ('rr-nagar', 'Rajarajeshwari Nagar', 12.9264, 77.5188),
            ('dasarahalli', 'Dasarahalli', 13.0298, 77.5124),
        ],
    },
]

CITIES_BY_SLUG = {c['slug']: c for c in CITIES}


# --- Scoring ---------------------------------------------------------------
# risk = hazard x vulnerability. See analyst.md §I.5 for why these multiply
# rather than sum: a weighted sum parks every low-lying, hospital-dense cell in
# `watch` forever, with zero rain and zero incidents.
HAZARD_WEIGHTS = {
    'hydro': 0.55,
    'incident': 0.30,
    'env': 0.15,
}

VULNERABILITY_WEIGHTS = {
    'terrain': 0.60,
    'infra': 0.40,
}
# vulnerability = 1 + VULNERABILITY_SPAN * weighted(terrain, infra)/100
VULNERABILITY_SPAN = 0.60

TERRAIN_WEIGHTS = {
    'low_lying': 0.45,
    'water_proximity': 0.35,
    'drain_gap': 0.20,
}

# Hydrology weights vary by horizon: right now, observed rain dominates; a day
# out, only the forecast and the river model carry any information.
HYDRO_WEIGHTS_BY_HORIZON = {
    0:  {'rain_now': 0.60, 'rain_forecast': 0.20, 'discharge': 0.20},
    3:  {'rain_now': 0.35, 'rain_forecast': 0.45, 'discharge': 0.20},
    6:  {'rain_now': 0.20, 'rain_forecast': 0.55, 'discharge': 0.25},
    24: {'rain_now': 0.05, 'rain_forecast': 0.60, 'discharge': 0.35},
}

# Incident decay: an unresolved report stops describing the present after a
# while. 12 h half-life-ish exponential, plus a fraction of the neighbours'
# contribution so a hotspot reads as an area rather than a single hexagon.
INCIDENT_DECAY_HOURS = 12.0
INCIDENT_NEIGHBOUR_WEIGHT = 0.40

# Criticality points per asset, capped at 100 for the infra sub-score.
ASSET_CRITICALITY_STEP = 12.0

ENV_WEIGHTS = {'aqi': 0.60, 'heat': 0.40}

# --- Status bands ----------------------------------------------------------
STATUS_BANDS = [
    ('critical', 75.0),
    ('warning', 50.0),
    ('watch', 25.0),
    ('normal', 0.0),
]


def status_for_score(score):
    """Map a 0-100 risk score onto its status band."""
    for name, floor in STATUS_BANDS:
        if score >= floor:
            return name
    return 'normal'


ASSET_CRITICALITY = {
    'hospital': 5,
    'clinic': 3,
    'fire_station': 5,
    'police': 4,
    'school': 3,
    'college': 3,
    'university': 3,
    'shelter': 4,
    'water_works': 4,
    'power_substation': 5,
    'metro_station': 3,
    'railway_station': 4,
    'bus_station': 2,
    'bridge': 3,
    'pumping_station': 4,
}
