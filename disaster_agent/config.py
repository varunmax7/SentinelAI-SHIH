"""Static configuration for the Disaster Prediction Agent.

Same philosophy as `twin/config.py`: every environment variable is optional,
the agent runs fully keyless against Open-Meteo, and an LLM key only upgrades
the *narrative* step - the deterministic wind/cloud/fire model underneath it
runs identically with or without one.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is optional
    pass


def _env_flag(name, default=True):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ('0', 'false', 'no', 'off', '')


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


# --- Feature flags -----------------------------------------------------------
AGENT_ENABLED = _env_flag('DISASTER_AGENT_ENABLED', True)
SCHEDULER_ENABLED = _env_flag('DISASTER_AGENT_SCHEDULER_ENABLED', True)

# How often the three-step cycle (ingest -> project -> narrate) runs on its own.
CYCLE_INTERVAL_MIN = _env_int('DISASTER_AGENT_CYCLE_MIN', 20)

# The horizons the projection step scores every region at, in hours.
HORIZONS = (1, 3, 6, 24)

# --- Step 1: ingest ----------------------------------------------------------
# Kept well under Flask's own request timeout: this call sits on the request
# path the first time an analyst opens the panel before any cache exists.
HTTP_TIMEOUT_S = _env_float('DISASTER_AGENT_HTTP_TIMEOUT_S', 8.0)
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
# How far ahead the hourly forecast is pulled. This is the ceiling on how far
# window.py can say a hazard lasts: past it there is no data, and the window is
# reported `open_ended` rather than given an invented end time. Three days is
# Open-Meteo's free default and covers every horizon in HORIZONS with room to
# see the far side of a 24-hour event.
FORECAST_DAYS = _env_int('DISASTER_AGENT_FORECAST_DAYS', 3)

# --- Step 2: deterministic projection -----------------------------------------
# A source region's hazard signal must clear this (0-100) before it is worth
# projecting downwind at all - otherwise every lightly-breezy region "projects"
# a trace of risk onto its neighbours and the hotspot list is just noise.
SOURCE_SIGNAL_MIN = _env_float('DISASTER_AGENT_SOURCE_MIN', 35.0)
# A projected region must clear this before it is written out as a hotspot.
HOTSPOT_THRESHOLD = _env_float('DISASTER_AGENT_HOTSPOT_THRESHOLD', 50.0)
# Bearing tolerance either side of the wind's downwind heading, degrees. Wider
# than a pencil-beam because real hazards (rain bands, smoke plumes, storm
# cells) fan out, not travel as a point.
BEARING_TOLERANCE_DEG = _env_float('DISASTER_AGENT_BEARING_TOLERANCE_DEG', 55.0)
# How many hotspots (across all horizons) get a narrative written per cycle.
# LLM calls are the one part of the cycle with a real cost; everything upstream
# of this cap is free.
MAX_NARRATED_HOTSPOTS = _env_int('DISASTER_AGENT_MAX_NARRATED', 10)
# A hotspot already narrated in a previous cycle is re-narrated only if its
# risk score moved by more than this many points, or its leading contributing
# source changed - otherwise the previous brief is reused as-is and no LLM
# call is made. Mirrors twin/agent/graph.py's "a quiet run must cost zero
# tokens" rule: weather rarely swings enough between 20-minute cycles to make
# a materially different paragraph true.
REUSE_RISK_DELTA = _env_float('DISASTER_AGENT_REUSE_RISK_DELTA', 6.0)
# LLM calls that DO need to happen this cycle run concurrently, this many at
# once, so narrating N hotspots costs one round-trip's wall-clock time instead
# of N sequential ones.
NARRATE_MAX_WORKERS = _env_int('DISASTER_AGENT_NARRATE_WORKERS', 4)

# --- Step 3: narrative ---------------------------------------------------------
# Reuses the twin's OpenRouter key/model - one LLM account for the app, not two.
def _twin_config():
    from twin import config as twin_config
    return twin_config


def llm_available():
    return bool(_twin_config().LLM_API_KEY)


def llm_model():
    return _twin_config().AGENT_MODEL


def llm_api_key():
    return _twin_config().LLM_API_KEY


def llm_timeout_s():
    return _twin_config().LLM_TIMEOUT_S


# --- Access control ------------------------------------------------------------
AGENT_ROLES = ('official', 'analyst', 'admin', 'coordinator')
