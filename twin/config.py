"""Static configuration for the Urban Digital Twin.

Everything here is deliberately data, not behaviour: cities, scoring weights and
status bands are the knobs an operator or analyst is most likely to want to
tune, and keeping them in one module means tuning them never requires reading
the engine.

Every environment variable is optional. The twin runs fully keyless; keyed
sources only add layers (see analyst.md §IV.1).
"""

import os

try:
    # The host app's config.py loads .env, but only when it is imported first.
    # Loading it here too makes `twin.config` correct on its own - a standalone
    # script or a test that imports the twin without the app still sees the
    # configured keys. load_dotenv does not override variables already set.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is optional
    pass


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
# Street-level imagery is fetched lazily when a drawer is opened, never on the
# dashboard's critical path, so it gets a longer budget than the global one.
STREETVIEW_TIMEOUT_S = _env_float('TWIN_STREETVIEW_TIMEOUT_S', 20.0)

CCTV_RADIUS_M = _env_int('TWIN_CCTV_RADIUS_M', 400)
# 500 m is KartaView's hard API maximum, and street-level coverage in both
# cities is sparse enough that anything smaller leaves most cells with no
# photograph of their own.
STREETVIEW_RADIUS_M = _env_int('TWIN_STREETVIEW_RADIUS_M', 500)
# Live webcams get their own, much wider radius. A street-level photo 5 km away
# is a different place and tells you nothing; a webcam 5 km away showing the
# current sky, rain and traffic is real, current context for the same city.
# Bengaluru has exactly one Windy webcam and it sits 7.6 km from the centre, so
# reusing the 350 m street-view radius meant live imagery never appeared at all.
WEBCAM_RADIUS_M = _env_int('TWIN_WEBCAM_RADIUS_M', 15000)

# --- External incident feeds ----------------------------------------------
# Which SACHET state feeds to poll. These are already scoped to the states the
# twin's two cities sit in; the all-India feed is 10x the volume for no gain.
SACHET_STATES = tuple(
    s.strip().lower() for s in
    os.environ.get('TWIN_SACHET_STATES', 'karnataka,telangana').split(',')
    if s.strip()
)
ALERT_POLL_MIN = _env_int('TWIN_ALERT_POLL_MIN', 5)
GLOBAL_FEEDS_ENABLED = _env_flag('TWIN_GLOBAL_FEEDS_ENABLED', True)

# --- Triage agent ----------------------------------------------------------
# The twin must boot and behave normally with none of this set. Disabled is a
# fully supported steady state, not a degraded one.
AGENT_ENABLED = _env_flag('TWIN_AGENT_ENABLED', True)

# The language model is served through OpenRouter, which the host app already
# uses for image analysis. KIMI_API_KEY is checked first because that is what
# this deployment sets; the other names are accepted so a differently-configured
# environment does not have to be renamed to work.
LLM_API_KEY = (os.environ.get('KIMI_API_KEY')
               or os.environ.get('OPENROUTER_API_KEY')
               or os.environ.get('TWIN_LLM_API_KEY')
               or '')

# Default is the non-reasoning Kimi. The reasoning variants (kimi-k2.5,
# kimi-k2-thinking) work too, but they spend most of max_tokens on chain of
# thought - about 5x the tokens for identical extraction output, and an empty
# `content` field if the budget runs out. This is classification and
# summarisation at temperature 0; there is nothing here to reason about.
AGENT_MODEL = os.environ.get('TWIN_AGENT_MODEL', 'moonshotai/kimi-k2-0905')
LLM_TIMEOUT_S = _env_float('TWIN_LLM_TIMEOUT_S', 90.0)
# Risk score above which a cluster becomes a flag for an admin to review.
FLAG_THRESHOLD = _env_float('TWIN_FLAG_THRESHOLD', 60.0)
# Hard cap on alerts handed to the LLM in one run, so an unusually loud feed
# day cannot turn into an unbounded bill.
AGENT_MAX_ITEMS = _env_int('TWIN_AGENT_MAX_ITEMS', 40)


def agent_available():
    """True only when the agent is switched on AND has a key to call with."""
    return bool(AGENT_ENABLED and LLM_API_KEY)


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
        # No LGD district code recorded: none of the observed Telangana alerts
        # was scoped tightly enough to attribute a code to Hyderabad with
        # confidence, and guessing one would silently mis-target alerts. The
        # polygon path covers these, with areaDesc name matching behind it.
        'lgd_district_codes': (),
        'district_names': ('hyderabad', 'secunderabad', 'rangareddy', 'ranga reddy',
                           'medchal', 'medchal-malkajgiri'),
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
        # Verified against a live SACHET alert scoped to
        # "Bengaluru Rural,Bengaluru Urban districts of Karnataka".
        'lgd_district_codes': ('525', '526'),
        'district_names': ('bengaluru', 'bangalore', 'bengaluru urban',
                           'bengaluru rural'),
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
