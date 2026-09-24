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
# When nothing is found within STREETVIEW_RADIUS_M, retry once at this wider
# radius before giving up - verified directly that ~50% of cells in both
# modelled cities return zero photos at 500-800 m but do have real coverage a
# little further out. Still capped and still captioned with its real distance
# (see routes.py::_view_caption's 'nearest' case) - never claimed as this
# exact spot.
STREETVIEW_FALLBACK_RADIUS_M = _env_int('TWIN_STREETVIEW_FALLBACK_RADIUS_M', 3000)

# KartaView caps its own `radius` at 500 m, which is narrower than an H3 res-8
# cell, so one centre query leaves many cells with no photograph of their own -
# and a cell with no photograph of its own shows the shared city webcam, which
# is identical everywhere. `_kartaview` therefore samples a small ring instead
# of a single point. Measured on 24 random Hyderabad cells: 14/24 cells had a
# photo with one query, 19/24 with the 5-point ring, and the median cell went
# from 1 photo to 5. Set STREETVIEW_RING_POINTS=1 to go back to one query.
STREETVIEW_RING_POINTS = _env_int('TWIN_STREETVIEW_RING_POINTS', 5)
STREETVIEW_RING_STEP_M = _env_int('TWIN_STREETVIEW_RING_STEP_M', 420)

# How close a citizen report photo has to be to count as a picture of *this*
# point in the cell drawer. Deliberately tight: a report photo two streets away
# is still useful context on the city board, but in a per-cell drawer it must
# not be presented as a view of this spot.
STREETVIEW_REPORT_RADIUS_M = _env_int('TWIN_STREETVIEW_REPORT_RADIUS_M', 700)

# The widened search, used only when the close ring found nothing at all.
# KartaView cannot be asked for a radius above 500 m, so "wider" means more
# legal 500 m queries further out rather than one bigger one. Measured on five
# Hyderabad cells with zero close coverage: four found real photographs at
# these radii, in 1-2 s. Anything found this way is flagged `widened` and
# captioned with its true distance.
STREETVIEW_WIDE_RING_STEPS_M = tuple(
    int(v) for v in os.environ.get('TWIN_STREETVIEW_WIDE_RING_STEPS_M', '1300,2600').split(',')
    if v.strip().isdigit())
STREETVIEW_WIDE_RING_POINTS = _env_int('TWIN_STREETVIEW_WIDE_RING_POINTS', 6)

# --- Aerial crop (twin/aerial.py) ------------------------------------------
# The floor under "show me this place": a satellite crop of the exact point,
# from the Esri World Imagery service already used as the basemap. Every cell
# gets one, so no cell is ever left with only the shared city webcam. ~400 m
# is about one H3 res-8 cell across.
AERIAL_SPAN_M = _env_int('TWIN_AERIAL_SPAN_M', 400)
AERIAL_SIZE_PX = _env_int('TWIN_AERIAL_SIZE_PX', 512)

# --- OSINT feeds (twin/osint.py) -------------------------------------------
# Open-source intelligence layered onto the city map: live aircraft, regional
# seismicity, open natural-event tracks, satellite thermal anomalies and
# geocoded news. Everything is filtered to this radius of the city centre and
# every feature carries its distance - a cyclone 300 km offshore is this
# city's problem, but it must never be drawn as if it were overhead.
OSINT_RADIUS_KM = _env_int('TWIN_OSINT_RADIUS_KM', 250)
OSINT_TIMEOUT_S = _env_float('TWIN_OSINT_TIMEOUT_S', 15.0)
# Per-source cap after distance sorting, so one busy feed cannot bury the
# others or push tens of thousands of points at the browser.
OSINT_MAX_PER_KIND = _env_int('TWIN_OSINT_MAX_PER_KIND', 120)

# Aircraft move; a stale position is a wrong position. OpenSky's anonymous
# tier is rate-limited, so this is the floor rather than something to lower.
OSINT_AIRCRAFT_TTL_S = _env_int('TWIN_OSINT_AIRCRAFT_TTL_S', 60)

OSINT_SEISMIC_TTL_S = _env_int('TWIN_OSINT_SEISMIC_TTL_S', 300)
OSINT_SEISMIC_DAYS = _env_int('TWIN_OSINT_SEISMIC_DAYS', 30)
# EMSC lists tremors far below anything a city would feel; 2.5 keeps the layer
# to events a resident might actually have noticed.
OSINT_SEISMIC_MIN_MAG = _env_float('TWIN_OSINT_SEISMIC_MIN_MAG', 2.5)

OSINT_EVENTS_TTL_S = _env_int('TWIN_OSINT_EVENTS_TTL_S', 900)
OSINT_EVENTS_DAYS = _env_int('TWIN_OSINT_EVENTS_DAYS', 30)

OSINT_FIRE_TTL_S = _env_int('TWIN_OSINT_FIRE_TTL_S', 1800)
OSINT_FIRE_DAYS = _env_int('TWIN_OSINT_FIRE_DAYS', 2)

# GDELT permits one request every five seconds per caller and answers 429 in
# plain text when pushed. An hour's cache keeps this well inside that with
# many analysts on the page at once.
OSINT_NEWS_TTL_S = _env_int('TWIN_OSINT_NEWS_TTL_S', 3600)
OSINT_NEWS_DAYS = _env_int('TWIN_OSINT_NEWS_DAYS', 3)
OSINT_NEWS_MAX = _env_int('TWIN_OSINT_NEWS_MAX', 40)
# GDELT's rate limit is per caller, not per query, so collecting two cities
# back-to-back throttles the second one. This spaces every GDELT call this
# process makes; their published minimum is 5 s.
OSINT_NEWS_MIN_INTERVAL_S = _env_float('TWIN_OSINT_NEWS_MIN_INTERVAL_S', 6.0)
# After a 429 the block outlasts GDELT's published five-second window, so the
# next call is refused locally for this long rather than spending the gate
# wait to earn another 429.
OSINT_NEWS_COOLDOWN_S = _env_float('TWIN_OSINT_NEWS_COOLDOWN_S', 300.0)
# Without hazard vocabulary the feed is mostly cricket and municipal politics.
OSINT_NEWS_TERMS = tuple(
    t.strip() for t in os.environ.get(
        'TWIN_OSINT_NEWS_TERMS',
        'flood,flooding,waterlogging,rain,cyclone,landslide,fire,collapse,'
        'evacuation,rescue,storm,disaster').split(',') if t.strip())

# Free key: firms.modaps.eosdis.nasa.gov/api/map_key. Without it the thermal
# anomaly layer reports `unconfigured` and draws nothing - it never guesses.
FIRMS_MAP_KEY = os.environ.get('FIRMS_MAP_KEY', '')
FIRMS_PRODUCT = os.environ.get('FIRMS_PRODUCT', 'VIIRS_SNPP_NRT')

# Per-point OSINT, shown in the cell drawer (twin/osint.py::near_point).
# Wider than a cell because the things it reports are wide: an aircraft at
# cruise 20 km away is overhead as far as an operator is concerned, and a
# tremor is felt far past its epicentre.
OSINT_NEAR_RADIUS_KM = _env_int('TWIN_OSINT_NEAR_RADIUS_KM', 25)
OSINT_NEAR_MAX = _env_int('TWIN_OSINT_NEAR_MAX', 20)
OSINT_NEAR_NEWS = _env_int('TWIN_OSINT_NEAR_NEWS', 5)
# How close a live camera must be before it can be said to cover a point at
# all. Beyond this it is listed as "the nearest camera is N km away", never as
# a view of this place.
OSINT_CAMERA_COVER_KM = _env_float('TWIN_OSINT_CAMERA_COVER_KM', 1.5)

# --- City-wide ground imagery board (twin/ground.py) -----------------------
# The drawer answers "what does this hexagon look like"; the board answers
# "show me the city". Its cost is one query per point per provider, so the
# point count is what bounds it - eight zone centres per city, two providers,
# all cached, is ~16 round trips on a cold build and zero on a warm one.
GROUND_POINTS_PER_CITY = _env_int('TWIN_GROUND_POINTS_PER_CITY', 12)
GROUND_IMAGES_PER_POINT = _env_int('TWIN_GROUND_IMAGES_PER_POINT', 6)
# Wider than STREETVIEW_RADIUS_M would allow per-point, but KartaView's own API
# hard-caps `radius` at 500 m, so this is the ceiling that actually applies.
GROUND_STREET_RADIUS_M = _env_int('TWIN_GROUND_STREET_RADIUS_M', 500)
# A live frame older than this is no longer "now". Kept short deliberately:
# the LIVE badge is a claim, and a cache that outlives the claim breaks it.
GROUND_WEBCAM_TTL_S = _env_int('TWIN_GROUND_WEBCAM_TTL_S', 60)
# Archival photography does not change. Re-querying it on every board build
# would be hundreds of round trips for identical answers.
GROUND_ARCHIVE_TTL_S = _env_int('TWIN_GROUND_ARCHIVE_TTL_S', 24 * 3600)
# How far back a citizen report photo still counts as useful ground truth.
# Thirty days, not the 72 h `internal_reports.py` uses for *scoring*: a report
# old enough to stop moving a risk number is still the best photograph anyone
# has of that street, and every tile carries its own real age, so nothing here
# can read as more current than it is.
GROUND_REPORT_LOOKBACK_H = _env_int('TWIN_GROUND_REPORT_LOOKBACK_H', 720)
GROUND_REPORT_LIMIT = _env_int('TWIN_GROUND_REPORT_LIMIT', 24)
GROUND_MAX_WORKERS = _env_int('TWIN_GROUND_MAX_WORKERS', 8)

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
OPENAQ_API_KEY = os.environ.get('OPENAQ_API_KEY', '')
AQICN_TOKEN = os.environ.get('AQICN_TOKEN', '')
DATA_GOV_IN_KEY = os.environ.get('DATA_GOV_IN_KEY', '')

# --- Live stations & transit -------------------------------------------------
STATION_POLL_MIN = _env_int('TWIN_STATION_POLL_MIN', 15)
TRANSIT_POLL_MIN = _env_int('TWIN_TRANSIT_POLL_MIN', 2)
# A station reading older than this is served, but marked stale - an old
# number beats no number, clearly labelled which one it is.
STATION_STALE_MIN = _env_int('TWIN_STATION_STALE_MIN', 120)
# A transit vehicle silent this long is not "stalled", it is gone - dropped
# rather than shown frozen on the map.
TRANSIT_VEHICLE_MAX_AGE_MIN = _env_int('TWIN_TRANSIT_VEHICLE_MAX_AGE_MIN', 30)
# Below this speed while a route is nominally moving, a vehicle counts as
# stalled for the disruption sub-score.
TRANSIT_STALL_SPEED_KMH = _env_float('TWIN_TRANSIT_STALL_SPEED_KMH', 3.0)

# JSON maps of city slug -> URL (and -> headers), e.g.
#   TWIN_GTFS_RT_URLS={"hyderabad": "https://.../vehicle_positions.pb"}
# No stable public GTFS-Realtime feed exists for either city as of writing
# (see IMPLEMENTATION_TWIN.md) - the transit layer is fully built and simply
# empty, not degraded, until a deployment sets these.
def _json_env(name, default=None):
    raw = os.environ.get(name)
    if not raw:
        return default or {}
    try:
        import json
        return json.loads(raw)
    except (TypeError, ValueError):
        return default or {}


GTFS_RT_URLS = _json_env('TWIN_GTFS_RT_URLS')
GTFS_STATIC_URLS = _json_env('TWIN_GTFS_STATIC_URLS')
GTFS_RT_HEADERS = _json_env('TWIN_GTFS_RT_HEADERS')

# --- Anomaly baselines -------------------------------------------------------
# Years of Open-Meteo archive history the backfill script pulls per sample
# point. Fewer years is faster to backfill but a noisier baseline.
BASELINE_YEARS = _env_int('TWIN_BASELINE_YEARS', 5)
# Sigma (standard deviations above the point's annual mean) at which a reading
# is called "unusual for this place", vs actually flagged.
ANOMALY_SIGMA_WATCH = _env_float('TWIN_ANOMALY_SIGMA_WATCH', 1.5)
ANOMALY_SIGMA_ALERT = _env_float('TWIN_ANOMALY_SIGMA_ALERT', 2.5)

# --- Operator camera feeds -----------------------------------------------------
# See twin/cameras.py. Empty JSON array by default - a fully supported
# steady state, not a degraded one, until real Hyderabad/Bengaluru access
# exists.
CCTV_STREAMS_FILE = os.environ.get(
    'TWIN_CCTV_STREAMS_FILE', os.path.join('data', 'twin', 'cctv_streams.json'))

# --- Forecast agent ------------------------------------------------------------
# Independent of TWIN_AGENT_ENABLED: triage reads what is true now, forecast
# projects what wind is carrying toward the city. Either can run without the
# other. Off is a fully supported steady state, same as the triage agent.
FORECAST_ENABLED = _env_flag('TWIN_FORECAST_ENABLED', True)

# --- RAG ---------------------------------------------------------------------
# See twin/agent/rag.py - keyword-scored retrieval, no embedding model.
RAG_CORPUS_DIR = os.environ.get('TWIN_RAG_CORPUS_DIR', os.path.join('data', 'twin', 'corpus'))

# --- Flag dispatch -----------------------------------------------------------
# Minutes before the same flag can be dispatched again. Guards against an
# analyst double-clicking Send, not against a real second wave - `force` in
# the request body bypasses it deliberately.
DISPATCH_COOLDOWN_MIN = _env_int('TWIN_DISPATCH_COOLDOWN_MIN', 30)
# Hard cap on how far a single dispatch can reach, regardless of how large the
# flag's cell footprint is.
DISPATCH_MAX_RADIUS_KM = _env_float('TWIN_DISPATCH_MAX_RADIUS_KM', 25.0)
# Added to the flag's own cell-footprint radius before searching for
# recipients, so someone just outside the flagged cells is not silently
# skipped by an exact-boundary search.
DISPATCH_BUFFER_KM = _env_float('TWIN_DISPATCH_BUFFER_KM', 1.5)

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
        # Turned to look down toward Hussain Sagar from the north-east - now
        # that terrain and zoom-scaled hexes no longer bury the city at a
        # dramatic angle, the default view can afford to be one.
        'default_pitch': 55.0,
        'default_bearing': -20.0,
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
        'default_pitch': 55.0,
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
    # Only applied when a city actually has transit data - see
    # scoring.py::hazard_score, which renormalises over hydro/incident/env
    # alone otherwise. No real GTFS-Realtime feed exists for either city as
    # of writing, so in practice this term is currently always absent and
    # every score is computed exactly as it was before this weight existed.
    'disruption': 0.12,
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
