# AI Disaster Prediction Agent

A build spec + as-built record, in the style of `RELIEF_AND_COMMISSIONER.md`.

> **Naming note.** Not `README.md`, for the same reason `RELIEF_AND_COMMISSIONER.md`
> isn't: that file already documents the whole system. This document covers
> only this one feature.

---

## 0. The ask, and what this is not

The analyst dashboard already embeds three live Windy panels: a temperature/
wind map, a satellite (cloud) view, and a fire-danger map. The ask was an AI
agent that watches those three signals continuously and predicts **where** the
next disaster is likely and **when**, surfaced as alerts on the same dashboard.

**This agent does not read the Windy iframes.** That was the first design
decision, and it is worth stating plainly because it is the thing most likely
to be assumed otherwise: `embed.windy.com` is a cross-origin `<iframe>`. There
is no pixel, canvas or DOM access into it from the host page, in this app or
any other - "watch the map and read the wind direction off it" is not an
engineering shortcut away, it is not possible for a browser page to do at all.

What the agent does instead: it goes to the same *class* of open numerical-
weather-model data Windy's own panels are rendered from (Open-Meteo, keyless),
independently, for a curated grid of regions across India, and runs its own
deterministic physics-flavoured projection plus an LLM narration step on top.
The dashboard panel it feeds sits directly under the three Windy panels, so an
analyst reads the live map and the agent's projection side by side.

**Build:**
1. A three-step pipeline - **ingest → project → narrate** - watching wind
   direction/speed, cloud cover and a fire-weather index across ~26 Indian
   regions.
2. A deterministic downwind-projection model that turns "region A has an
   elevated signal and the wind is blowing this way" into "region B is likely
   affected, within this many hours" - arithmetic only, no LLM.
3. An LLM narration step that turns the top projections into analyst-readable
   briefs, with a fully-functional offline fallback when no LLM key is set.
4. A dashboard panel: ranked hotspot cards with a one-click "Send Alert" that
   reuses the existing `/send_global_alert` broadcast path.

**Do NOT build (out of scope, and why):**
- ❌ **Pixel-scraping the Windy embed.** Impossible (cross-origin), and not
  how any of this app's other live-map panels work either - they all call a
  backend API. See §0 above.
- ❌ **A second H3 grid like `twin/`.** The twin's grid is two cities at
  ~15 km radius; these Windy panels are national. A new curated point grid
  (`disaster_agent/regions.py`) is the right scale, not a resolution bump on
  the twin's.
- ❌ **Seismic or particulate sensing.** `tsunami`, `earthquake` and
  `air_quality` stay in a region's hazard vocabulary for context but this
  agent never fabricates a source signal for them - it has no seismograph or
  PM2.5 feed. An honest gap beats an invented number. See §2.3.

---

## 1. Architecture

```
                    ┌─────────────────────────────────────────┐
                    │         disaster_agent/ (package)         │
                    └─────────────────────────────────────────┘

  STEP 1 — INGEST              STEP 2 — PROJECT             STEP 3 — NARRATE
  disaster_agent/ingest.py     disaster_agent/advect.py     disaster_agent/agent.py
  ─────────────────────────    ─────────────────────────    ─────────────────────────
  Open-Meteo, one HTTP call    Deterministic arithmetic.     twin/llm.py's
  for all 26 regions:          No LLM, no network.           StructuredLLM, reused.
                                                               Falls back to a
   wind_speed_10m               For each region with an       template narrative
   wind_direction_10m           elevated hazard signal:       when no LLM key is
   cloud_cover                                                 configured.
   precipitation                 target_bearing =
   surface_pressure               wind_dir + 180
   temperature_2m,                travel_km =
   relative_humidity_2m           wind_speed * horizon
                                  → find other watched
   + Fosberg Fire Weather          regions in that bearing
     Index, computed from          cone at that distance
     temp+RH+wind                 → accumulate risk there

        │                              │                              │
        ▼                              ▼                              ▼
   region signal                  ranked hotspot list            PredictionBrief
   dicts (26)                     [{target, hazard,               (headline,
                                    horizon, risk,                  narrative,
                                    sources[]}, ...]                 action,
                                                                     confidence,
                                                                     citations)
                                                                        │
                                                                        ▼
                                                          disaster_agent/models.py
                                                          DisasterPrediction rows,
                                                          upserted by
                                                          (region, hazard_type)
                                                                        │
                                                                        ▼
                                                          disaster_agent/routes.py
                                                          /api/disaster-agent/*
                                                                        │
                                                                        ▼
                                                          analyst_dashboard.html
                                                          hotspot cards + Send Alert
```

`run_prediction_cycle()` in `agent.py` is the whole pipeline in one call, and
is what both the scheduler and the dashboard's "Run Now" button invoke.

### 1.1 Why this shape

The design mirrors `twin/agent/` deliberately (see `twin/agent/graph.py` and
`twin/agent/schemas.py`), because that package already worked out the right
separation of concerns for this app:

> "None of these schemas has a field for a coordinate or a risk number. The
> model classifies and writes prose; the grid and the scorer own geography and
> arithmetic." — `twin/agent/schemas.py`

`disaster_agent/schemas.py` follows the same rule. `PredictionBrief` has a
`headline`, `narrative`, `recommended_action`, `confidence_label` and
`citation_sources` - and nothing else. Every number and place name in a
prediction is decided by `advect.py`'s arithmetic *before* the LLM ever sees
it; the model's only job is to narrate numbers it is handed, and it is told
explicitly not to invent one that wasn't supplied (see the system prompt in
`agent.py`). That is also why the feature works with zero LLM key: the
deterministic half is the whole prediction, the narration is presentation.

### 1.2 Files

```
disaster_agent/
  __init__.py     factory: create_disaster_agent_blueprint(app, db, ...)
  config.py       env-driven thresholds, all optional (keyless by default)
  regions.py      ~26 watched regions + their hazard_bias susceptibility prior
  ingest.py       STEP 1 - Open-Meteo adapter + Fosberg Fire Weather Index
  advect.py       STEP 2 - deterministic downwind projection
  schemas.py      Pydantic output schema for STEP 3 (no coords/scores)
  agent.py        STEP 3 - LLM narration + offline fallback + orchestrator
  models.py       DisasterPrediction table (factory bound to the host's db)
  security.py     role gate, same contract as twin/security.py
  routes.py       /api/disaster-agent/{predictions,status,run,dismiss}
  jobs.py         one interval job on the host's existing APScheduler
```

Zero new dependencies: `requests` and `pydantic` are already in
`requirements.txt` for `twin/`, and `disaster_agent/agent.py` imports
`twin.llm.StructuredLLM` directly rather than re-implementing an OpenRouter
client. Dropping the `twin/` package into another app is required for this
reuse to resolve; if that's undesirable, `_default_llm()` in `agent.py` is the
one place to swap in a self-contained client instead.

---

## 2. Step 1 — Ingest

### 2.1 What is measured

One Open-Meteo `/v1/forecast` call, all 26 regions batched into a single
request via comma-separated `latitude`/`longitude` lists:

| Windy panel               | Field(s) pulled                                   |
|----------------------------|----------------------------------------------------|
| Live Temperature Map (wind)| `wind_speed_10m`, `wind_direction_10m`             |
| Live Satellite View (clouds)| `cloud_cover`, `precipitation`, 3h rain forecast  |
| Fire Danger Map            | Fosberg Fire Weather Index, derived below          |

`surface_pressure` and `temperature_2m`/`relative_humidity_2m` are pulled too
- the former as a coarse storm-intensification proxy, the latter as the
Fosberg index's inputs.

### 2.2 Fosberg Fire Weather Index

Windy's fire-danger layer is itself a model output (ECMWF), not a satellite
reading, so the honest equivalent is to compute the same *kind* of index from
first principles rather than approximate their specific model. Fosberg (1970)
is the standard, publicly documented formula (still used by NOAA/USFS):
equilibrium moisture content from temperature + relative humidity, combined
with wind speed. Implementation in `ingest.py::fosberg_fire_weather_index`,
rescaled from its raw range (~0-110) to this app's usual 0-100 sub-score - a
declared assumption, named as a constant (`FFWI_RAW_MAX`) so it can be argued
with, the same convention `twin/scoring.py` uses throughout.

### 2.3 What is deliberately not measured

No seismic feed, no satellite-derived active-fire-pixel feed (e.g. NASA
FIRMS), no particulate/AQI feed. `regions.py` tags a region's `hazard_bias`
with `tsunami`, `earthquake` or `air_quality` where geographically relevant
(Port Blair is seismically active; Delhi NCR has a known air-quality problem)
so that context is visible on a prediction card, but `advect.py::COMPUTABLE_HAZARDS`
never generates a *source* signal for those three - there is no live input to
ground one in. Wiring in FIRMS or a seismic feed is the natural next step (see
§6) and slots into `ingest.py` without touching `advect.py`'s interface.

---

## 3. Step 2 — Project (deterministic)

### 3.1 The model

A simplified Gaussian-plume-style advection, in `advect.py::_project_one`:

```
target_bearing = (wind_dir_deg + 180) % 360   # wind_dir is FROM; hazard moves TOWARD
travel_km      = wind_speed_kmh * horizon_hours

for every other watched region B:
    bearing_delta = |target_bearing - bearing(source -> B)|   (circular)
    if bearing_delta > BEARING_TOLERANCE_DEG (55°):  skip      # not downwind
    distance_mismatch = |distance(source, B) - travel_km|
    if distance_mismatch > tolerance:                 skip     # wrong distance for this horizon
    alignment        = 1 - bearing_delta / BEARING_TOLERANCE_DEG
    distance_weight  = 1 - distance_mismatch / tolerance
    contribution     = source_strength * alignment * distance_weight
```

A region also always re-projects onto **itself** ("origin" role) at a horizon-
decayed weight - the source of an elevated signal is itself at risk, not only
its downwind neighbours.

A region only ever receives a hazard type listed in its own `hazard_bias`
(`regions.py`) - the bearing cone can point from a coastal cyclone source
straight at an inland region, and that region simply cannot receive a
`cyclone` projection because `'cyclone' not in target['hazard_bias']`. This is
what stops the model from ever proposing "cyclone risk in Rajasthan."

### 3.2 Source strength

`advect.py::source_strengths` turns raw signal into a 0-100 strength per
hazard type, only for hazards the region is biased toward:

| Hazard      | Inputs                                             |
|-------------|-----------------------------------------------------|
| cyclone / storm_surge | wind speed, low surface pressure, rain    |
| flood       | precipitation (now + 3h forecast) + cloud cover      |
| landslide   | same as flood, weighted 1.1x (saturated slopes)      |
| heat_wave   | temperature, 28-46°C band                            |
| wildfire    | Fosberg Fire Weather Index directly                  |

A source must clear `DISASTER_AGENT_SOURCE_MIN` (default 35/100) before it
projects anything; a target must clear `DISASTER_AGENT_HOTSPOT_THRESHOLD`
(default 50/100) before it is written out as a hotspot. Both are env-tunable,
named constants - the same "declared threshold, not a measurement" convention
`twin/scoring.py` documents at its own top.

### 3.3 Output

One entry per `(region, hazard_type)` pair, kept at whichever horizon (1, 3, 6
or 24h) scored highest, so the hotspot list never shows four near-duplicate
cards for the same emerging event at every horizon. Ranked by risk score,
each entry carries its full `sources` list (which regions contributed, their
raw wind/cloud/fire readings, distance and bearing alignment) - this is what
Step 3 is handed, and what the dashboard's source chips render verbatim.

---

## 4. Step 3 — Narrate

### 4.1 With an LLM key configured

Reuses `twin.llm.StructuredLLM` against the same OpenRouter key/model the
triage agent already uses (`twin.config.LLM_API_KEY` / `AGENT_MODEL` - one LLM
account for the app, not two). The prompt (`agent.py::_build_prompt`) states
the target region, hazard type, horizon, deterministic risk score and every
contributing source's raw numbers; the system prompt instructs the model to
never invent a figure and to lower `confidence_label` rather than assert
certainty when sources are thin or disagree.

### 4.2 Without one (offline mode)

`agent.py::_offline_brief` builds the same shape of brief from a template,
using only numbers already computed - no LLM call at all. `generated_offline`
is stored on every row and rendered as a `TEMPLATE` tag on the dashboard card,
so an analyst is never shown a template sentence under the impression a model
wrote it. This mirrors `twin_flag.generated_offline`.

---

## 5. Persistence, API, scheduling

**`disaster_prediction` table** (`disaster_agent/models.py`): one row per
`(region_slug, hazard_type)`, upserted every cycle. A row the current cycle
does not refresh is marked `status='expired'` rather than deleted, so there is
an audit trail of what the agent used to project. An analyst can `dismiss` a
row they don't find credible (`status='dismissed'`), which the next cycle
leaves alone rather than resurrecting.

**API** (`disaster_agent/routes.py`, gated by `agent_access_required()` -
same role list as the analyst dashboard itself):

| Route | Method | Purpose |
|---|---|---|
| `/api/disaster-agent/predictions` | GET | Active hotspots, `?min_risk=`, `?hazard_type=`, `?limit=` |
| `/api/disaster-agent/status` | GET | Last run time, region count, LLM availability |
| `/api/disaster-agent/run` | POST | Trigger an immediate cycle (dashboard's "Run Now") |
| `/api/disaster-agent/predictions/<id>/dismiss` | POST | Hide one prediction |

**Scheduler** (`disaster_agent/jobs.py`): one `interval` job on the host's
existing `BackgroundScheduler` (`app.py`'s `scheduler`, already running for
the twin), every `DISASTER_AGENT_CYCLE_MIN` minutes (default 20). Never starts
a scheduler of its own - same rule `twin/jobs.py` follows.

---

## 6. Dashboard integration

`templates/analyst_dashboard.html`: a new panel directly below the three Windy
iframe panels, matching their existing dark-card visual language (`#1a2234`
card, `#151b2b` header, live pulse dot). It fetches `/predictions` and
`/status` on load and every 90s, renders one card per hotspot (severity badge,
region + hazard + horizon, headline, narrative, recommended action, a risk bar,
source chips, Dismiss / 🚨 Send Alert), and a "Run Now" button for an on-demand
cycle. **Send Alert** reuses the app's existing `/send_global_alert` endpoint
unchanged - it builds the same `affected_locations` payload shape the flood-
station-alert flow already sends, so a prediction becomes a real broadcast
notification (in-app + WhatsApp, per existing logic) with no new backend alert
path to introduce or trust.

---

## 7. Configuration

Every variable optional; the agent is fully functional keyless (Open-Meteo)
and fully functional without an LLM key (template narration).

| Variable | Default | Meaning |
|---|---|---|
| `DISASTER_AGENT_ENABLED` | `1` | Master switch |
| `DISASTER_AGENT_SCHEDULER_ENABLED` | `1` | Run on the interval job |
| `DISASTER_AGENT_CYCLE_MIN` | `20` | Minutes between automatic cycles |
| `DISASTER_AGENT_SOURCE_MIN` | `35` | Source signal floor (0-100) |
| `DISASTER_AGENT_HOTSPOT_THRESHOLD` | `50` | Hotspot floor (0-100) |
| `DISASTER_AGENT_BEARING_TOLERANCE_DEG` | `55` | Downwind cone half-width |
| `DISASTER_AGENT_MAX_NARRATED` | `10` | LLM calls per cycle, cost cap |
| `DISASTER_AGENT_HTTP_TIMEOUT_S` | `8.0` | Open-Meteo call budget |

LLM key/model are **not** separately configured - `disaster_agent` reads
`twin.config.LLM_API_KEY` / `AGENT_MODEL` / `LLM_TIMEOUT_S` directly.

---

## 8. Verified

- `run_prediction_cycle()` run end-to-end against live Open-Meteo data and the
  live OpenRouter key: 26/26 regions ingested, deterministic projection
  produced a sensible top-ranked list (monsoon-season flood/landslide signal
  dominant over cyclone/wildfire, as expected for the date this was built),
  and the LLM correctly hedged confidence down when a source's raw numbers
  didn't clearly justify the hazard type - the "never invent, say so instead"
  instruction held under a real call, not just in the prompt text.
- `/analyst_dashboard` renders with the new panel present under an
  authenticated `analyst`-role session; all four new API routes return valid
  JSON under the same session.
- Every new module `py_compile`s clean; the embedded panel JS passes
  `node --check`.
- All testing ran against throwaway copies of `instance/site.db` - the live
  database was not written to during development.

## 9. Honest limitations

- **This is a projection, not a forecast model.** It is bearing-and-distance
  arithmetic over a snapshot of current conditions at ~26 points, not a
  physical atmospheric simulation. Treat it as "where to look next," not as a
  replacement for IMD/SACHET warnings - every generated brief's recommended
  action says exactly that.
- **26 points is not continuous coverage.** A hazard forming between watched
  regions, or outside all of their bearing cones, will not surface. Widening
  `regions.py` is cheap (no code change downstream); it is a completeness/cost
  trade-off, made explicit here rather than left implicit.
- **Surface pressure is a snapshot, not a trend.** A real cyclone signature is
  a *falling* pressure over hours; this reads one instant. Reliable
  intensification detection needs the ingest step to keep short history per
  region, which it does not yet do.
- **No seismic or particulate feed** (§2.3) - `tsunami`, `earthquake` and
  `air_quality` are never predicted from this data, by design, not by
  oversight. Wiring in NASA FIRMS or a seismic feed is the natural next step
  and slots into `ingest.py` without changing `advect.py`'s interface.
