# MAX.md — Sentinel AI: handoff for the production build

**Who this is for:** the agent that is building these features into the real
Sentinel AI codebase (the production analyst dashboard).

**What this file covers:** everything that was built and tested locally in the
prototype (`SentinelAI-SHIH/`):

- the Urban Digital Twin backend
- the two AI agents
- every live data source, and where its data comes from
- the Hyderabad and Bengaluru camera layers
- where the Windy maps sit on the dashboard
- the security fixes
- the bugs we hit along the way

> **Start here.** The production app **already has the base Urban Digital
> Twin**: the hex grid, scoring, the console and the map. What it does **not**
> have yet is the agent and intelligence layer we built on top of it:
>
> - the two AI agents (LangGraph DAGs)
> - RAG
> - the flag queue and analyst dispatch
> - official CAP alerts
> - live stations and transit
> - anomaly baselines
> - the forecast physics
> - the security fixes
>
> **Your four tasks, in order:**
>
> 1. **Section 14:** port all of that into the existing twin.
> 2. **Section 15:** the 3D map upgrade.
> 3. **Section 16:** replace the three Windy maps with a smaller, researched,
>    more useful weather-map slot.
> 4. **Section 17:** make every "live" map actually live and local (three
>    dashboard feeds are mock or off-target today), upgrade the place search,
>    add watched places, and show the agent's activity.
>
> Sections 1–13 are the reference that all four tasks rely on. **Section
> 4.4** is the audit of what every map on the dashboard really shows. Read
> it before you touch a map.

The owner will send you the API keys separately. Keys go in `.env` only and
are never committed. This file names the variables, never their values.

---

## 0. Ground rules. Read these before you write any code

1. **Match the existing UI exactly.** Use the analyst dashboard's current
   look:
   - dark cards: `#1a2234` body, `#151b2b` header, `1px solid
     rgba(255,255,255,0.1)` border, 12px radius
   - 15px bold `#f8fafc` card titles
   - the small outlined "Open Full ↗" pill buttons
   - the pulsing status dot

   Inside the twin console, use the classes in `static/css/twin.css`
   (`twin-icon-btn`, `twin-flags-panel`, `twin-drawer-*`, `twin-cctv-*`,
   `twin-muted`, `twin-toast`). Don't add a new theme, font, palette or
   design language.
2. **Don't change the layout or structure.** Don't reorder, resize, merge,
   split or remove any dashboard row, card, map, chart or table. Don't
   restructure templates, routes or navigation. New things only go into the
   **existing extension points**:
   - a new **map layer**: register it in `static/js/twin-layers.js` and
     toggle it from the existing layer control
   - a **new action**: add a `twin-icon-btn` to the twin header's existing
     icon cluster
   - **per-cell information**: add a section inside the existing drill-down
     drawer (`partials/twin_console.html`)
   - a **basemap or view option**: add it to the existing basemap
     `<select data-twin-basemap>`
   - **3D upgrades to the dashboard's city flood maps**: add layers and
     settings inside those maps' existing init code, with the card itself
     unchanged

   **The one exception** is the Windy rows (rows 7–8 in section 8). Section
   16 authorises you to replace them. Even there, use the same card styling,
   keep the slot in the same position, and take up no more vertical space
   than the two rows do now.
3. **Keep the safety rules** (sections 5 and 7):
   - no model ever computes a number that matters
   - nothing reaches the public without an analyst's click
   - the server never proxies camera streams
4. **Only Hyderabad and Bengaluru.** The twin models only these two cities.
   Don't add data sources, cameras or features that don't serve them.
5. If the production codebase differs from the prototype (file names, app
   factory, roles), map each item to its production equivalent. Keep the
   behaviour, not the file path.

---

## 1. What was built, in one screen

| Area | What it does | Main files |
|---|---|---|
| Urban Digital Twin | H3 hex grid (resolution 8) over **Hyderabad (GHMC)** and **Bengaluru (BBMP)**. Every cell gets a live 0–100 risk score from weather, flood, air quality, citizen reports, official alerts and transit, for now and +3h, +6h and +24h | `twin/` package |
| Triage agent | LangGraph DAG. Reads what is true now (CAP alerts, high-scoring cells, stalled transit, station readings), groups related items into events, scores them, and files flags | `twin/agent/graph.py`, `nodes.py` |
| Forecast agent | Carries rain along the wind vector (advection) and reads heat-threshold crossings, to say *where* and *in how many hours*. Files flags in the same queue | `twin/forecast.py`, `twin/agent/forecast_graph.py`, `forecast_nodes.py` |
| Flag queue and dispatch | The agents raise `pending` flags. An analyst reviews them, previews the blast radius, and dispatches in-app and WhatsApp alerts. Cooldowns apply and every send is audited | `twin/dispatch.py`, routes under `/flags/*` |
| Official alerts | NDMA SACHET CAP feeds for Telangana and Karnataka. Parsed, deduplicated, superseded on update, and expired at `cap:expires` | `twin/ingest/sachet.py`, `twin/alerts.py` |
| Live point layers | Air-quality stations (CPCB, OpenAQ, AQICN), GTFS-RT transit, and GDACS and USGS events near the cities | `twin/ingest/stations.py`, `transit.py`, `global_events.py`, `twin/live.py` |
| Anomaly baselines | 5 years of Open-Meteo archive per cell, giving a sigma for "unusual for *this* place" | `twin/anomaly.py`, `scripts/backfill_baselines.py` |
| Cameras (Hyderabad and Bengaluru) | Mapped CCTV positions from OpenStreetMap, plus an operator feed file for real ICCC or police streams once access exists | `twin/ingest/cctv.py`, `twin/cameras.py` |
| Street imagery | Mapillary (discovered through vector tiles), with KartaView as the fallback | `twin/ingest/streetview.py`, `mapillary_tiles.py` |
| RAG | Local embeddings over `data/twin/corpus/`, used for SOP citations in briefs | `twin/agent/rag.py` |
| Maps | Twin console (MapLibre, satellite basemap, 3D hexes and buildings, NASA GIBS) embedded in the analyst dashboard. The three Windy iframes sit below the city flood maps | `templates/partials/twin_console.html`, `templates/analyst_dashboard.html` |
| Place search | One search box per city pane. Today it calls Nominatim from the browser on each keystroke; section 17.2 makes it local-first with a server geocoder proxy | `static/js/twin-console.js` (`wireSearchBox`) |
| Dashboard maps outside the twin | Heatmap, warning map and city flood maps. Section 4.4 audits where each one's data comes from; three feeds are mock or off-target | `templates/analyst_dashboard.html`, `static/js/god-mode-maps.js`, `app.py`, `utils.py` |
| Security | Fixes for debug RCE, an open redirect, session forgery, CSRF gaps and a forgeable webhook | `app.py`, `config.py`, `templates/base.html` |

**The design rule behind almost every decision:** *an analyst must be able
to explain any number in an enquiry.* Every score, wind vector and arrival
time comes from deterministic arithmetic. The LLM only writes the paragraph
that explains those numbers.

---

## 2. Where everything lives (prototype file map)

```
SentinelAI-SHIH/
├── app.py                      # host Flask app: twin wiring, CSRF, dispatch channel, security fixes
├── config.py                   # SECRET_KEY hardening
├── run_server.py               # supported launcher (loopback bind, debug is opt-in)
├── requirements.txt            # twin, agent and RAG dependencies added at the bottom
├── .env.example                # every variable, explained (no values)
├── SYSTEMS.md                  # prose design notes
├── twin/
│   ├── __init__.py             # create_twin_blueprint(app, db, scheduler, ...), the single entry point
│   ├── config.py               # ALL tunables: cities, zones, weights, bands, source URLs, env switches
│   ├── models.py               # twin_* tables (section 9)
│   ├── routes.py               # /api/twin/* JSON API + /digital-twin page
│   ├── engine.py               # compute pass: adapters → scoring → twin_cell_state
│   ├── scoring.py              # pure functions: sub-scores + composite (section 6)
│   ├── grid.py / geo.py        # H3 grid clipped to admin polygons; geo helpers
│   ├── jobs.py                 # APScheduler jobs, registered on the HOST scheduler
│   ├── live.py                 # station/transit observations → cells, TTL expiry
│   ├── alerts.py               # CAP alert persistence, supersede, expire
│   ├── anomaly.py              # baseline sigma
│   ├── forecast.py             # advection and heat-crossing physics
│   ├── dispatch.py             # the ONLY path to real people's phones
│   ├── cameras.py              # operator-supplied live feeds (JSON file)
│   ├── stream.py               # SSE stream for live updates
│   ├── security.py             # adopts the host's login_required/role_required
│   ├── seed.py / serializers.py
│   ├── agent/                  # graph.py, nodes.py, forecast_graph.py, forecast_nodes.py,
│   │                           # llm.py, rag.py, flagstore.py
│   └── ingest/                 # one adapter per external source (section 4)
├── data/twin/
│   ├── boundaries/*.geojson    # city and clip polygons (GHMC, BBMP)
│   ├── cache/                  # adapter disk cache (served in degraded mode)
│   ├── corpus/                 # RAG documents (empty; its README has no extension on purpose)
│   └── lgd_districts.json      # learned LGD district codes for matching CAP alerts
├── migrations/versions/20260903_01_twin_initial.py, 20260917_01_twin_live_agent.py
├── scripts/                    # fetch_boundaries, seed_twin, import_twin_grid,
│                               # backfill_baselines, learn_lgd_codes
├── static/js/
│   ├── twin-layers.js          # layer registry and paint expressions (pure data)
│   ├── digital-twin.js         # TwinMap class: map construction, basemaps, sources, layer order
│   ├── twin-console.js         # console: drawer, flags, player, horizons, search
│   ├── twin-stream.js          # SSE client
│   └── god-mode-maps.js        # GodModeMap (dashboard heatmap and warning maps)
├── static/css/twin.css
├── templates/
│   ├── partials/twin_console.html   # embeddable console (variants: page | embedded | compact)
│   ├── digital_twin.html            # full-screen page at /digital-twin
│   ├── analyst_dashboard.html       # hosts the console, the flood maps and the Windy embeds
│   └── base.html                    # CSRF meta tag + fetch/XHR token wrapper
└── tests/twin/                 # pytest suite (section 13)
```

---

## 3. How the twin is wired into the host app

In `app.py`, inside a `try`, so the twin can never take down the other 119
routes:

```python
from twin import create_twin_blueprint
create_twin_blueprint(app, db, scheduler,
                      login_required=login_required, role_required=role_required)
```

- **Models** are defined against the host's `db`, so there is one metadata
  object and one Alembic history.
- **Jobs** register on the host's APScheduler. Under multi-worker Gunicorn,
  set `TWIN_SCHEDULER_ENABLED=1` on exactly one process.
- **Seeding** tolerates an unmigrated database: it warns and skips, so
  `flask db upgrade` can still run.
- **Approved citizen reports** reach the twin through an `on_approved` hook,
  which also publishes an SSE `incident` event.
- **Dispatch channel.** The twin owns no users. At startup the host
  registers three callables with
  `twin.dispatch.register_alert_channel(...)`:
  - `recipients_near(lat, lon, radius_km)` wraps the host's
    `_users_near_point`.
  - `notify(user_id, message)` creates a `Notification` with
    `is_alert=True` and a 12h expiry.
  - `send_whatsapp(number, body)` wraps the host's `send_whatsapp_message`.
- **Embedding the console.** A page embeds it with
  `{% set twin_variant = 'compact' %}{% include "partials/twin_console.html" %}`.
  Cities come from `GET /api/twin/cities` at runtime, so no view function
  needs new template variables.
- **Drawer action buttons** reuse existing routes through
  `window.TWIN_COORDINATION_ENDPOINTS`: `new_emergency` (a form),
  `get_volunteers_near_point` and `send_global_alert`.

---

## 4. Every data source, and where its data comes from

All adapters subclass `twin/ingest/base.py::IngestAdapter`. **The base class
owns:**

- the timeout
- the disk TTL cache
- the retry
- the `twin_data_snapshot` audit row
- the guarantee that `run()` never raises

A subclass implements only `fetch_raw()` and, optionally, `neutral_value()`.
`run()` returns `(data, snapshot)`, where the snapshot status is one of:

- `ok`: fresh data from the network
- `degraded`: the network failed and the cached value was served
- `failed`: no cache existed, so `neutral_value()` was returned

A missing key hides that layer. It never causes an error.

### 4.1 Core sources (keyless; the twin works on an empty `.env`)

| Source | Endpoint | Adapter | Feeds |
|---|---|---|---|
| Open-Meteo forecast | `https://api.open-meteo.com/v1/forecast` | `ingest/open_meteo.py` | rain now and over the next 3/6/24h, temperature, apparent temperature → hydro and env scores |
| Open-Meteo air quality | `https://air-quality-api.open-meteo.com/v1/air-quality` | `ingest/open_meteo.py` | fallback AQI → env score |
| Open-Meteo flood (GloFAS) | `https://flood-api.open-meteo.com/v1/flood` | `ingest/open_meteo.py` | river discharge. The "2-year return" is a p95-of-archive proxy computed at seed time |
| Elevation | `https://api.open-meteo.com/v1/elevation`, `https://api.opentopodata.org/v1/srtm30m` (`grid.py`) | seed | low-lying term → terrain |
| Open-Meteo archive | `https://archive-api.open-meteo.com/v1/archive` | `anomaly.py` | 5-year baselines (`rain_1h/3h/24h`, `temp_max`, `aqi`) |
| Open-Meteo wind lattice | the forecast API, hourly `wind_speed_10m`, `wind_direction_10m`, cloud, rain and apparent temperature on a ~5 km lattice, one request per city | `ingest/windfield.py` | forecast agent |
| RainViewer | `https://api.rainviewer.com/public/weather-maps.json` | `ingest/rainviewer.py` | radar tile overlay |
| OSM Overpass | `https://overpass-api.de/api/interpreter` | `ingest/overpass.py`, `ingest/cctv.py` | hospitals, schools, substations and similar (criticality → infra); water bodies and drains (terrain score and water layers); CCTV positions |
| Internal reports | the host's `Report` model (approved reports only) | `ingest/internal_reports.py` | incident score, decayed with τ = 12h, plus spillover to neighbouring cells |
| **NDMA SACHET CAP** | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_%s.xml`, for the states in `TWIN_SACHET_STATES` | `ingest/sachet.py`, `alerts.py` | official IMD and state warnings → alert score, alert polygons, and the triage agent's highest-weight signal |
| NASA GIBS | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/` | `ingest/nasa_gibs.py` | dated satellite basemap option |
| Esri World Imagery + Reference | `server.arcgisonline.com/.../World_Imagery`, `.../Reference/World_Boundaries_and_Places` | JS | default satellite basemap, the same imagery as the dashboard flood maps |
| OpenFreeMap | `https://tiles.openfreemap.org/styles/liberty` | `digital-twin.js` | "Street map" basemap, and the source for the `buildings-3d` layer |
| Nominatim | `https://nominatim.openstreetmap.org/search?` | `twin-console.js` | place search, called **from the browser on every keystroke** (400 ms debounce). Nominatim's usage policy forbids autocomplete, so section 17.2 replaces this |
| GDACS / USGS | `https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH`, `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/...` | `ingest/global_events.py` | events within `TWIN_GLOBAL_EVENT_RADIUS_KM` (300 km) of either city |
| TGDPS (Telangana) | proxied at `/api/proxy/tgdps_map` | `app.py` | existing dashboard iframes |

### 4.2 Optional keyed sources (each key unlocks one layer)

| Env var | Source and endpoint | Adapter | Status in the prototype |
|---|---|---|---|
| `OPENAI_API_KEY` | OpenAI, `gpt-5-nano` at `minimal` reasoning effort | `agent/llm.py` | ✅ working |
| `MAPILLARY_TOKEN` | `https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}` + `https://graph.mapillary.com/images` | `mapillary_tiles.py`, `streetview.py` | ✅ working (needs Graph read scope) |
| `TOMTOM_API_KEY` | `https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.png`, `.../flowSegmentData/...` | `ingest/traffic.py` | ✅ working |
| `OPENAQ_API_KEY` | `https://api.openaq.org/v3` | `ingest/stations.py` | ✅ 26 locations near Bengaluru |
| `AQICN_TOKEN` | `https://api.waqi.info` | `ingest/stations.py` | ✅ city feeds work. ⚠ `/map/bounds/` returns nothing for either city. **Never** fall back to `/feed/geo:`: it returned a *Delhi* station for a Bengaluru query. The feed reports the US-EPA index, which the twin converts to the CPCB scale |
| `DATA_GOV_IN_KEY` | `https://api.data.gov.in/resource/%s` (CPCB AQI) | `ingest/stations.py` | ❌ not obtained. The public sample key is capped at 10 rows and rate-limited, so get a real one |
| `WINDY_WEBCAMS_KEY` | `https://api.windy.com/webcams/api/v3/webcams` | `streetview.py` | optional: nearby public webcams in the drawer (only within the city bbox) |
| `TOMORROW_API_KEY` | Tomorrow.io nowcast | — | optional alternative to Open-Meteo |
| `IUDX_TOKEN` | `https://api.catalogue.iudx.org.in/iudx/cat/v1`, `https://rs.iudx.org.in/ngsi-ld/v1` | `ingest/iudx.py` | the catalogue is keyless; reading resources needs an account |
| `TWIN_GTFS_RT_URLS` / `TWIN_GTFS_STATIC_URLS` / `TWIN_GTFS_RT_HEADERS` (JSON maps of city → URL) | per-deployment GTFS-Realtime | `ingest/transit.py` | no stable public feed for either city, so the layer appears only when configured. The stall rate per cell becomes the disruption score |
| `TWILIO_*` | Twilio WhatsApp and SMS | host | ❌ unset, so approved flags currently reach people in-app only |

### 4.3 Refresh cadence (`twin/jobs.py`)

| Job id | Interval | Env |
|---|---|---|
| `twin_compute_state` | 5 min | `TWIN_COMPUTE_INTERVAL_MIN` (the only job that calls the weather, flood and air sources) |
| `twin_ingest_radar_index` | 10 min | `TWIN_RADAR_INTERVAL_MIN` |
| `twin_ingest_alerts` | 5 min | `TWIN_ALERT_POLL_MIN` |
| `twin_ingest_stations` | 15 min | `TWIN_STATION_POLL_MIN` |
| `twin_ingest_transit` | 2 min | `TWIN_TRANSIT_POLL_MIN` |
| `twin_agent_triage` (triage, then forecast) | 10 min | `TWIN_AGENT_INTERVAL_MIN` |
| `twin_refresh_infrastructure` | weekly | — |

Every job body runs inside `app.app_context()` with a broad `except`. An
unhandled exception in an APScheduler job silently kills all its future
runs.

### 4.4 Every map on the dashboard: tiles, data, and whether it is real

Audited in the prototype on 2026-09-23. **"Real"** means the numbers come
from a live upstream for Hyderabad or Bengaluru. Rows marked ❌ are what
section 17.1 fixes.

**Tiles (what the map looks like):**

| Map | Basemap tiles | 3D today |
|---|---|---|
| Twin console panes + `/digital-twin` | Esri World Imagery + Esri Reference labels (default); OpenFreeMap Liberty (`tiles.openfreemap.org/styles/liberty`, "Street map"); NASA GIBS (dated) | hex extrusions, OpenFreeMap buildings from z13, pitch ≤ 45 |
| `heatmapMap`, `warningMap` (`GodModeMap`) | a satellite style defined inline in `analyst_dashboard.html` (Esri imagery + labels). The class default is CARTO Voyager (`basemaps.cartocdn.com/gl/voyager-gl-style/style.json`) | pitch 55 camera only, no terrain or buildings |
| City flood maps (Hyderabad \| Bengaluru) | Esri World Imagery | pitch 30, nothing extruded |
| TGDPS rainfall + district rainfall | iframes of TGDPS pages, proxied at `/api/proxy/tgdps_map` | — |
| Windy ×3 | `embed.windy.com` iframes, centred on India | — |
| `static/js/analyst_dashboard.js` | a Leaflet fallback on `tile.openstreetmap.org` | — |

**Data (what the map shows):**

| Map | Endpoint | Upstream | Real? |
|---|---|---|---|
| Twin console | `/api/twin/*` (section 10) | section 4.1/4.2 adapters | ✅ real, both cities, with `ok/degraded/failed` status |
| `heatmapMap` | `DASHBOARD_DATA.reports` rendered into the page | host `Report` rows | ✅ real, framed on Bengaluru only |
| `warningMap`: incident heat | `/api/live_hazard_incidents` | host `Report` rows (approved **and pending**, last 500) | ⚠ real, but pending reports are unverified and are drawn as if confirmed |
| `warningMap`: temperature circles | `/api/weather_data` | Open-Meteo `current=` for **8 coastal cities** (Chennai, Mumbai, Kolkata, Kochi, Visakhapatnam, Mangalore, Thiruvananthapuram, Goa) | ❌ neither Hyderabad nor Bengaluru. **Uncached**: 8 upstream calls per request |
| `warningMap`: "government hazards" | `/api/live_govt_hazards` | **hardcoded list** (a Bay of Bengal cyclone, a Kolkata flood, a Mumbai quake, a Western Ghats landslide, a tsunami), with **random** timestamps and confidence on every call | ❌ mock, presented as IMD/NDMA/USGS |
| `warningMap`: warning circles | `/api/weather_warnings` → `get_weather_warnings()` | **hardcoded list** (Bay of Bengal, Arabian Sea, Kerala) | ❌ mock |
| `warningMap` polling | `updateLiveWeather()` calls the three endpoints above **every 3.5 s**, then clears and redraws every layer | — | ❌ about 197k Open-Meteo calls a day per open tab, roughly 20× Open-Meteo's free daily limit |
| City flood maps: station dots | `/api/live_flood_gauges/{telangana,bengaluru}` → `utils.fetch_live_flood_gauges` | Open-Meteo **Flood API (GloFAS modelled discharge)** at fixed points in `TELANGANA_GAUGE_STATIONS` / `BENGALURU_GAUGE_STATIONS` (`utils.py`), classed against each point's own mean/p75 | ⚠ real model output, **not gauge readings**. The legend says "CWC/KSNDMC", but no CWC or KSNDMC data is fetched. The Bengaluru "stations" are lakes and junction drains (Bellandur, Silk Board…) that GloFAS's ~5 km river grid can't resolve |
| TGDPS iframes | `/api/proxy/tgdps_map` | TGDPS AWS network | ✅ real, Telangana only |
| Windy | iframe | Windy/ECMWF | ✅ real, but national view (section 16) |

**Rule for every map after section 17:** each value on screen is either
live for Hyderabad or Bengaluru, labelled with its source and age, or it is
not drawn.

---

## 5. The two AI agents

Both are LangGraph DAGs. Both write to `twin_flag` with `status='pending'`.
**Neither can send anything to the public.**

### 5.1 Triage agent: what is happening now

```
gather → extract → correlate → score → threshold
                                          │ nothing ≥ TWIN_FLAG_THRESHOLD (55) → END (zero tokens)
                                          ▼
                              retrieve (RAG) → draft_brief → persist
```

- **gather:** CAP alerts in force, cells near the threshold, stalled
  transit, station readings.
- **extract:** the LLM reads the alert prose. Without an LLM, it uses the
  CAP structured fields (`cap:severity`, `cap:certainty`, `cap:area`, LGD
  district codes).
- **correlate:** the LLM groups related items. Without an LLM, it uses
  spatial clustering.
- **score:** always `twin/scoring.py`. Never the model.
- **draft_brief:** a deterministic template built from the evidence. The
  LLM only rewrites the prose.

### 5.2 Forecast agent: what is coming, and how long we have

```
sample → advect → detect → threshold → retrieve → draft_brief → persist
```

| Node | Does |
|---|---|
| sample | hourly wind, cloud, rain and apparent temperature on a ~5 km lattice (`windfield.py`) |
| advect | carries each raining lattice point downwind hour by hour, up to `MAX_LEAD_HOURS = 12` |
| detect | groups projections within 6 km into events, each with cells, an arrival hour and a confidence |
| threshold | drops events below the confidence floor, off the grid, or below every severity band |

The constants are in `twin/forecast.py`:

- rain source ≥ 2 mm/h, arrival ≥ 4 mm/h, severe ≥ 12 mm/h
- heat watch at 38 °C and severe at 42 °C (apparent temperature)
- cloud source at 70%

Confidence decays with lead time and in light wind. Heat doesn't travel, so
it is read **in place** and flagged when it *crosses* a threshold ("passes
42 °C at 14:00"), not on every hot hour. `TWIN_FORECAST_ENABLED=0` turns
this agent off.

### 5.3 Behaviour to preserve (each of these was a real bug or requirement)

- **Conditional edge.** When nothing clears the threshold, no LLM node runs.
  A calm city costs zero tokens.
- **Fallbacks.** Without LangGraph, the nodes run in plain sequence. Without
  a key, briefs come from templates. Each flag records `agent_mode` (`llm`
  or `rules`), and the UI shows it.
- **Lenient JSON parsing.** A bad model response falls back to the
  deterministic path. It never raises.
- **Flag upsert key (`_cluster_key`).** Bucket on a coarse **H3
  resolution-5 cell containing the cluster centre**. Keying on the arrival
  hour or on `cells[0]` created duplicate flags on every run (observed
  live: 7 new flags instead of 7 updates).
- **Wind convention.** `wind_direction_10m` is where the wind blows
  *from*, so a 90° wind moves air **westward**. Convert in one tested
  function (`windfield.wind_vector`).
- **Hyderabad snapping.** The GHMC clip polygon is far smaller than the
  city bbox, so projections landed just off the grid and were dropped. Snap
  them to cells within the method's ~1.5 km error bar.

### 5.4 RAG

`twin/agent/rag.py` uses FAISS with `all-MiniLM-L6-v2`
sentence-transformers. It is local and keyless, with a keyword fallback.

- The corpus is `data/twin/corpus/` (`.md`, `.txt`, `.json`). Load SOPs,
  escalation matrices, shelter registers and past sitreps there.
- Numeric queries are **keyword-scored**, so a query for "62 mm" cites the
  measurement rather than a similar-sounding sentence.
- Top-k is 4.

### 5.5 Flag → review → dispatch

1. `GET /api/twin/<city>/flags` returns the queue plus flag-area GeoJSON
   (the `flag-areas` and `flag-glow` layers). A badge appears on the header
   flag button. The panel never opens by itself.
2. `POST /api/twin/flags/<id>/review` approves, dismisses or adds a note.
3. `GET /api/twin/flags/<id>/dispatch/preview` shows how many people will be
   alerted and how far away they are, before anything is sent.
4. `POST /api/twin/flags/<id>/dispatch` sends, and only on an analyst's
   click. Guard rails:
   - a server-side cooldown (`TWIN_DISPATCH_COOLDOWN_MIN=30`)
   - a radius cap (`TWIN_DISPATCH_MAX_RADIUS_KM=25`)
   - a buffer around the area (`TWIN_DISPATCH_BUFFER_KM=1.5`)
   - an audit row in `twin_dispatch` for every send

   **There is no code path from a scheduler to dispatch.**

### 5.6 How the agents run live, end to end

One 10-minute tick of `twin_agent_triage`, per city:

1. The compute pass (every 5 min) has already written fresh
   `twin_cell_state`. The alert, station and transit jobs have already
   written `twin_external_alert` and `twin_observation`. **The agents never
   call an external API for scores.** The only external fetch they make is
   the forecast agent's Open-Meteo wind lattice.
2. Triage runs its DAG (5.1). If nothing clears the threshold, it ends with
   zero tokens.
3. Forecast runs its DAG (5.2) on the wind lattice.
4. Both upsert into `twin_flag` by `cluster_key`. New or changed flags
   publish an SSE `flags` event (`twin/jobs.py`), and the console's badge
   updates without a reload.
5. The analyst opens the panel, reviews, previews, and dispatches (5.5).

**SSE events published today** (`twin/stream.py`, consumed by
`twin-stream.js`, with a 60 s poll fallback): `state_update` (compute
pass), `incident` (approved report), `alerts`, `transit`, `flags`.

**Gap:** `GET /agent/status` reports only configuration (engine, model,
corpus, threshold). It has no last-run time, duration, mode, flag counts or
next-run time, and no event marks a run starting or finishing. The analyst
can't tell whether the agent is working. Section 17.4 fixes this.

---

## 6. Scoring model (`twin/scoring.py`, weights in `twin/config.py`)

- **`risk = hazard × vulnerability`.** It is not a weighted sum of five
  terms.
- **hazard** is a weighted blend that renormalises over the terms actually
  present:
  - `hydro` 0.55
  - `alert` 0.35
  - `incident` 0.30
  - `env` 0.15
  - `disruption` 0.12

  An absent term drops out and the rest are rescaled.
- **vulnerability** is `1 + 0.60 × (0.60·terrain + 0.40·infra)/100`, which
  ranges from 1.0 to 1.6.
- **hydro** weights `(rain_now, rain_forecast, discharge)` at `0.40/0.40/0.20`,
  and at `0.25/0.35/0.40` for the +24h horizon.
- **terrain** is `low_lying` 0.45, `water_prox` 0.35, `drain_gap` 0.20.
- **env** is `aqi` 0.60, `heat` 0.40.
- **incident severity** is low 25, medium 50, high 75, critical 100. Decay
  has τ = 12h and neighbouring cells get weight 0.40.
- `None` means **unmeasured** and `0.0` means **measured as nothing**.
  Keep the two distinct.
- **Status bands:**

  | Band | Score | Colour |
  |---|---|---|
  | normal | below 25 | `#22c55e` |
  | watch | 25 to 49 | `#eab308` |
  | warning | 50 to 74 | `#f97316` |
  | critical | 75 and above | `#ef4444` |

  The JS copy in `twin-layers.js` uses lower opacities (0.14 to 0.55) on
  purpose, because it sits over satellite imagery. Keep the Python and JS
  copies in sync by hand.
- **Anomaly.** A reading is compared with the cell's own 5-year baseline in
  standard deviations (sigma): watch at 1.5σ, alert at 2.5σ. Run
  `python scripts/backfill_baselines.py` once. Until then, nothing can be
  called "unusual".

---

## 7. Cameras: Hyderabad and Bengaluru only

We searched for live CCTV feeds for these two cities (as of 2026-09-21):

| Source | Result |
|---|---|
| Bengaluru Traffic Police | a viewer only, no API |
| GHMC | nothing published |
| TS Police | nothing published |
| data.gov.in | nothing published |
| OpenCity | camera positions only, no feeds |
| global open-webcam datasets | nothing in either city |

**No public live CCTV feed exists for Hyderabad or Bengaluru**, so the
production build has no live public feed layer. Implement only these two:

| Layer | Source | Map layer | Notes |
|---|---|---|---|
| **Mapped camera positions** (`ingest/cctv.py`) | OSM Overpass surveillance tags (`man_made=surveillance`, `surveillance:type=camera`, with direction and operator where tagged), inside each city bbox | `cctv`, `cctv-direction` (min zoom 14), `cctv-cone` (min zoom 15) | Keyless. Positions and ownership only, no video. One city-wide query in the prototype returned ~2,950 positions. The drawer lists the cameras near the selected cell as "OSINT · OpenStreetMap" |
| **Operator feeds** (`twin/cameras.py`) | a JSON file at `TWIN_CCTV_STREAMS_FILE` (`data/twin/cctv_streams.json`), empty by default. Fill it when real access is granted (GHMC/Bengaluru ICCC, police, campus) | `cctv-streams` + the drawer's "Live feeds" block + `twin-stream-modal` player | Entry: `{id, name, city, lat, lon, direction, url, type: hls\|mjpeg\|image, operator, attribution}`. **The server never fetches, re-hosts or proxies these URLs.** The browser plays them directly, loading hls.js from jsdelivr only for HLS |

**Don't port from the prototype:**

- `twin/ingest/cctv_live.py` (the ten foreign road-authority catalogs)
- the Hong Kong "Not local" reference feed
- the camera coverage panel and its `/cctv/coverage` and `/cctv/providers`
  routes
- the `TWIN_CCTV_LIVE_*` and `TWIN_CCTV_REFERENCE_*` env vars

None of those serve either city. When the operator file is empty, the
drawer's "Live feeds" block still renders, saying *"No live feed available
for this city yet"*, so an empty layer never looks like a broken one.

**Street imagery (ground truth for a cell):**

- Mapillary is the primary source. The documented Graph bbox endpoint
  returns **0 rows with HTTP 200** over Bengaluru, so discovery goes
  through vector tiles instead. `mapillary_tiles.py` is a hand-rolled MVT
  decoder with no new dependency. One Bengaluru tile holds 15,412 photos,
  the nearest 23 m away, with bearings.
- KartaView (`api.openstreetcam.org/2.0/photo/`) is the keyless fallback.
- Search radius is 350 m (`TWIN_STREETVIEW_RADIUS_M`), with one retry at
  ~900 m.
- Bearings that were inferred rather than published are marked as guesses.

---

## 8. Maps and the analyst dashboard layout. Keep this order exactly

`templates/analyst_dashboard.html`, from top to bottom:

1. Stats row (four `stat-card`s).
2. **Urban Digital Twin card.** Header "🌐 Urban Digital Twin — Hyderabad &
   Bengaluru", a green "● LIVE" chip, and a "Full screen" link to
   `/digital-twin`. The body is the console partial with
   `twin_variant='compact'`.
3. Maps row: `heatmapMap` (incident hotspots) | `warningMap`. Both are built
   by `GodModeMap` in `static/js/god-mode-maps.js` (pitch 55, bearing
   −12.5).
4. TGDPS live rainfall iframe (`/api/proxy/tgdps_map?path=aws.jsp`).
5. District live rainfall iframe.
6. City flood monitoring maps: Hyderabad | Bengaluru. These are MapLibre
   with Esri imagery at pitch 30, with CWC/KSNDMC station legends and
   stats overlays.
7. **Windy: Live Temperature Map** (full width, 50vh, min 400px).
8. **Windy: Live Satellite View | Windy: Fire Danger Map (FIRMS)** (two
   columns, 55vh, min 420px).
9. Charts row (three), then the detail table, then modals.

**Windy embed URLs (keyless iframes):**

| Map | Embed URL | "Open Full" link |
|---|---|---|
| Temperature | `https://embed.windy.com/embed.html?type=map&location=coordinates&metricRain=mm&metricTemp=%C2%B0C&metricWind=km/h&zoom=5&overlay=temp&menu=&message=true&marker=&calendar=now&city=&shiftLon=0&shiftLat=0&lat=20.5937&lon=78.9629&detailLat=20.5937&detailLon=78.9629` | `https://www.windy.com/?temp,20.5937,78.9629,5` |
| Satellite | same as temperature, with `zoom=6&overlay=satellite&lat=17.5&lon=78.5` | `https://www.windy.com/?satellite,17.5,78.5,6` |
| Fire danger | `https://embed.windy.com/embed2.html?lat=20.5937&lon=78.9629&zoom=5&overlay=firedanger&product=ecmwf&menu=&message=true&marker=&calendar=now&pressure=&type=map&location=coordinates&detail=&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1` | `https://www.windy.com/?firedanger,20.5937,78.9629,5` |

⚠ **Rows 7–8 above are what the prototype has now. Section 16 replaces
them.** The URLs are kept here as the starting point.

Windy is for the analyst's eye only. An iframe can't be sampled or cited, so
the forecast agent computes from Open-Meteo's hourly series instead. Don't
wire the agent to Windy.

**MapLibre is loaded once, at version 4.7.1.** The dashboard loads it in
`<head>`. `twin_console.html` injects it **only if `window.maplibregl` is
absent**, and exposes `window.TwinMapLibreReady`. A second copy would detach
every map already built. Everything in section 15 works on 4.7.1, so **don't
upgrade MapLibre, and don't add a globe view**.

**Twin console map as it stands** (`digital-twin.js`, `twin-layers.js`):

- **Basemaps:** Satellite (Esri, the default), Street map (OpenFreeMap
  Liberty), NASA GIBS (with a date picker).
- **Layer order**, bottom to top: satellite → satellite-labels →
  buildings-3d → radar/traffic → hexes → points and flags.
- **Layer IDs:** `satellite`, `buildings-3d`,
  `alert-zones(+outline)`, `twin-hexes`, `twin-hex-outline` (only cells
  scoring ≥ 25), `twin-hexes-degraded` (dashed amber outline on cells
  missing an input), `zone-outline`, `radar`,
  `water-bodies(+outline)`, `water-drains(+glow)`, `infrastructure`,
  `cctv`, `cctv-direction`, `cctv-cone`, `cctv-streams`,
  `transit-vehicles`, `transit-stalled-halo`, `air-stations(+labels)`,
  `incidents(+labels)`, `flag-areas`, `flag-glow`.
- **Current 3D:**
  - `twin-hexes` is a `fill-extrusion` whose height is interpolated from
    the risk score (0 → 60 → 150 → 330 → 420 m).
  - `buildings-3d` extrudes OpenFreeMap buildings from min zoom 13, using
    `render_height`, falling back to `building:levels × 3`, then to 8 m. It
    uses a flat slate colour ramp at opacity 0.92.
  - The camera is capped at pitch 45.
  - The dashboard flood maps are pitch 30 with no 3D at all.
- **MapLibre limitation:** `fill-extrusion-opacity` can't be data-driven,
  and `addLayer` throws if you try. Bake the alpha into
  `fill-extrusion-color` as `rgba()`.
- **Header controls:**
  - horizon buttons (Now/+3h/+6h/+24h); the KPI row shows the signed
    change against "now"
  - basemap select
  - link-cameras toggle (so the Hyderabad and Bengaluru panes pan and zoom
    together)
  - recompute
  - flag queue with badge
  - health pill
  - clock

---

## 9. Database (every table is prefixed `twin_`)

Migrations: `20260903_01_twin_initial.py` and
`20260917_01_twin_live_agent.py`.

| Table | Purpose |
|---|---|
| `twin_city`, `twin_zone` | 2 cities and 14 zones, seeded at registration |
| `twin_cell` | H3 res-8 cells clipped to the GHMC and BBMP polygons (805 in Hyderabad) |
| `twin_cell_state` | latest score per cell per horizon, with sub-scores and an explanation |
| `twin_cell_history` | time series behind `/timeline` |
| `twin_infrastructure` | OSM assets with a criticality weight |
| `twin_data_snapshot` | one audit row per adapter run (status, record count, age). Drives the health pill |
| `twin_external_alert`, `twin_alert_cell` | CAP alerts. `UNIQUE(source, source_uid)` makes re-polling an upsert, and an update supersedes the alert it names in `cap:references` |
| `twin_observation` | station readings and vehicles. `observed_at` is the **source's** timestamp. Readings older than 120 min are served as stale; vehicles older than 30 min are deleted |
| `twin_baseline` | per-cell climatology for the anomaly sigma |
| `twin_flag`, `twin_flag_cell` | agent output (see below) |
| `twin_dispatch` | who sent what, to how many people, over which cells, and how many WhatsApp messages were sent or failed |

`twin_flag` columns: `cluster_key`, `hazard_type`, `risk_score` (from
scoring, never an LLM), `severity`, `anomaly_sigma`, `confidence`,
`brief_md`, `citations`, `evidence`, `agent_mode`, `status`, the reviewer
fields, and `expires_at` (TTL 12h).

---

## 10. API surface (`/api/twin/*`, behind the host's login and role decorators)

| Method | Path | Returns |
|---|---|---|
| GET | `/digital-twin` | the full-screen page |
| GET | `/health` | status and age for each source |
| GET | `/cities`, `/<city>/zones` | metadata that drives the UI |
| GET | `/<city>/state?horizon=&zone=` | GeoJSON of cells with scores |
| GET | `/<city>/cell/<h3>` | drill-down: sub-scores, explanation, assets, reports |
| GET | `/<city>/summary`, `/compare`, `/<city>/timeline` | KPIs, the city comparison, history |
| GET | `/<city>/incidents`, `/<city>/infrastructure`, `/<city>/water` | map layers |
| GET | `/<city>/alerts` | CAP alerts |
| POST | `/alerts/refresh` | re-poll CAP alerts |
| GET | `/<city>/live`, `/<city>/live/<kind>` | stations and transit |
| POST | `/live/refresh` | re-poll stations and transit |
| GET | `/<city>/flags` | the flag queue |
| POST | `/flags/<id>/review` | approve, dismiss or note |
| GET | `/flags/<id>/dispatch/preview` | recipient count and distances |
| POST | `/flags/<id>/dispatch` | send |
| POST | `/agent/run` | run the agents now |
| GET | `/agent/status` | agent status |
| GET | `/gibs`, `/traffic`, `/streetview`, `/cctv`, `/<city>/cameras` | basemap info, traffic tiles, street imagery, OSM camera positions |
| GET | `/cctv/streams` | operator feeds from `cctv_streams.json` |
| GET | `/stream` | SSE for incidents and state updates |
| POST | `/seed`, `/refresh` | admin: seed the grid (behind a database lock) or recompute |

Large JSON responses are gzipped in an `after_request` hook.

---

## 11. Security fixes. Port all of them

| Issue | Fix |
|---|---|
| `app.run(debug=True, host='0.0.0.0')` offered the Werkzeug debugger (remote code execution) to the network | `FLASK_DEBUG` and `FLASK_HOST` are opt-in, defaulting to off and loopback. The app refuses to start with debug on and a non-loopback host. Launch with `run_server.py` |
| Open redirect via `/login?next=` | `_safe_next()` accepts only root-relative paths |
| `SECRET_KEY` fell back to `'dev-key-for-demo-only'` | a random key per process, with a warning |
| CSRF gaps: `/verify_report` and `/reject_report` read `request.form` directly | site-wide `CSRFProtect`. `base.html` publishes `<meta name="csrf-token">`, and a fetch/XHR wrapper adds `X-CSRFToken` to same-origin mutating requests only |
| `/webhook/whatsapp` accepted any POST | a Twilio signature is required. It fails closed when no token is set, and the route is `@csrf.exempt` |
| Still open | `scripts/import_twin_grid.py` interpolates table names into SQL. It's a local, one-shot script, so this is noted rather than fixed |

---

## 12. Environment variables

**Keys (the owner will send these):** `OPENAI_API_KEY`, `MAPILLARY_TOKEN`,
`TOMTOM_API_KEY`, `OPENAQ_API_KEY`, `AQICN_TOKEN`, `DATA_GOV_IN_KEY`,
`WINDY_WEBCAMS_KEY`, `TOMORROW_API_KEY`, `IUDX_TOKEN`, `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`, `TWILIO_PHONE_NUMBER`,
`FIREBASE_SERVER_KEY`, `SECRET_KEY`, `DATABASE_URL`.

**Switches and tunables** (defaults and explanations are in
`.env.example`):

| Group | Variables |
|---|---|
| Core | `TWIN_ENABLED`, `TWIN_H3_RESOLUTION=8`, `TWIN_SCHEDULER_ENABLED`, `TWIN_CACHE_DIR`, `TWIN_HTTP_TIMEOUT_S=8` |
| Polling | the `TWIN_*_INTERVAL_MIN` and `TWIN_*_POLL_MIN` family |
| Imagery | `TWIN_STREETVIEW_RADIUS_M` |
| Search | `TWIN_GEOCODER_CONTACT` (new in section 17.2: the contact sent in the Nominatim `User-Agent`) |
| Alerts | `TWIN_ALERTS_ENABLED`, `TWIN_SACHET_STATES=telangana,karnataka` |
| Transit | `TWIN_GTFS_*` |
| Cameras | `TWIN_CCTV_STREAMS_FILE` |
| Anomaly | `TWIN_BASELINE_YEARS=5`, `TWIN_ANOMALY_SIGMA_WATCH/ALERT` |
| Agents | `TWIN_FORECAST_ENABLED`, `TWIN_AGENT_ENABLED`, `TWIN_AGENT_INTERVAL_MIN=10`, `TWIN_FLAG_THRESHOLD=55`, `TWIN_FLAG_TTL_HOURS=12`, `TWIN_LLM_MODEL=gpt-5-nano`, `TWIN_LLM_REASONING_EFFORT=minimal` |
| RAG | `TWIN_RAG_CORPUS_DIR`, `TWIN_RAG_EMBEDDING_MODEL` |
| Dispatch | `TWIN_DISPATCH_COOLDOWN_MIN`, `TWIN_DISPATCH_MAX_RADIUS_KM`, `TWIN_DISPATCH_BUFFER_KM` |
| Server | `FLASK_DEBUG`, `FLASK_HOST` |

**Python dependencies added:** `h3`, `shapely`, `flask-compress`,
`cachetools`, `gtfs-realtime-bindings`, `langgraph`, `langchain-openai`,
`langchain-core`, `faiss-cpu`, `sentence-transformers`. The agent, RAG and
transit packages are optional at runtime.

---

## 13. Setup and tests

```bash
pip install -r requirements.txt
flask db upgrade
python scripts/fetch_boundaries.py && python scripts/seed_twin.py
python scripts/backfill_baselines.py        # once, for the anomaly sigma
python run_server.py
python -m pytest --capture=tee-sys
```

- On Windows, use `--capture=tee-sys`. Without it, the Node subprocess in
  `test_layers_js.py` fails with `WinError 50`, which looks like eight real
  failures but isn't.
- Port the tests along with the code. They pin:
  - the wind convention
  - the flag upsert key
  - CAP supersede and expiry
  - the dispatch cooldown
  - "never proxied" for operator feeds
- Leave out the prototype's `test_cctv_live.py` and
  `test_cctv_reference.py`, because those features are not being ported.

---

## 14. BUILD THIS FIRST: port the AI agents, RAG and live systems into the existing twin

The production twin is the **base** version: grid, scoring, console, map,
and the core adapters (Open-Meteo, RainViewer, Overpass, internal reports,
NASA GIBS, TomTom, street imagery, OSM CCTV). Everything below was added on
top of that base in the prototype, and **none of it is in production yet**.

**Don't rebuild or restructure the twin that's already there.** Add these
pieces into it. Before changing any shared file, diff it against the
prototype and merge the differences. Don't overwrite the file.

### 14.1 What to add

**New modules** (copy their behaviour; the file names can follow the
production repo's conventions):

| Area | Prototype files |
|---|---|
| AI agents (DAGs) | `twin/agent/__init__.py`, `graph.py` (triage), `nodes.py`, `forecast_graph.py` (forecast), `forecast_nodes.py`, `llm.py`, `flagstore.py` |
| RAG | `twin/agent/rag.py`, `data/twin/corpus/` (the folder plus its extensionless `README`) |
| Forecast physics | `twin/forecast.py`, `twin/ingest/windfield.py` |
| Flag dispatch | `twin/dispatch.py` |
| Official alerts | `twin/ingest/sachet.py`, `twin/alerts.py`, `data/twin/lgd_districts.json`, `scripts/learn_lgd_codes.py` |
| Live stations and transit | `twin/ingest/stations.py` (CPCB, OpenAQ, AQICN), `twin/ingest/transit.py` (GTFS-RT), `twin/ingest/iudx.py`, `twin/live.py` |
| Global events near the cities | `twin/ingest/global_events.py` (GDACS, USGS) |
| Anomaly baselines | `twin/anomaly.py`, `scripts/backfill_baselines.py` |
| Operator camera feeds | `twin/cameras.py` + `data/twin/cctv_streams.json` (empty until real Hyderabad or Bengaluru access exists) |
| Mapillary tile discovery | `twin/ingest/mapillary_tiles.py` |
| Launcher | `run_server.py` |

**Existing files to extend** (merge, don't replace):

| File | What was added |
|---|---|
| `twin/models.py` | tables `twin_external_alert`, `twin_alert_cell`, `twin_observation`, `twin_baseline`, `twin_flag`, `twin_flag_cell`, `twin_dispatch` (columns in section 9) |
| migrations | port `migrations/versions/20260917_01_twin_live_agent.py` so that it chains onto the production head revision. Then run `flask db upgrade` |
| `twin/config.py` | the SACHET/CAP settings, LGD codes, alert/station/transit/agent/LLM/RAG/forecast/anomaly/dispatch settings, and the new `HAZARD_WEIGHTS` terms `alert: 0.35` and `disruption: 0.12`. Copy the whole live-data and agent blocks |
| `twin/scoring.py` + `twin/engine.py` | `composite()` takes the alert and disruption terms and renormalises over the terms present. The engine gains `_fetch_alert_cells`, `_fetch_transit_disruption`, `_fetch_station_aqi` and `_load_baselines`. **Regression check:** a city with no alerts and no transit must score exactly as before |
| `twin/jobs.py` | jobs `twin_ingest_alerts` (5 min), `twin_ingest_stations` (15 min), `twin_ingest_transit` (2 min), `twin_agent_triage` (10 min; runs triage, then forecast) |
| `twin/routes.py` | `GET /<city>/alerts`, `POST /alerts/refresh`, `GET /<city>/live`, `GET /<city>/live/<kind>`, `POST /live/refresh`, `GET /<city>/flags`, `POST /flags/<id>/review`, `GET /flags/<id>/dispatch/preview`, `POST /flags/<id>/dispatch`, `POST /agent/run`, `GET /agent/status`, `GET /cctv/streams`. Don't add `/cctv/coverage` or `/cctv/providers` |
| `app.py` | `register_alert_channel(recipients_near, notify, send_whatsapp)` right after `create_twin_blueprint` (section 3), plus every security fix in section 11 |
| `config.py`, `templates/base.html` | SECRET_KEY hardening; the CSRF meta tag and fetch/XHR wrapper |
| `requirements.txt` | `gtfs-realtime-bindings`, `langgraph`, `langchain-openai`, `langchain-core`, `faiss-cpu`, `sentence-transformers` |
| `.env.example` | the alert, station, transit, agent, LLM, RAG, forecast, anomaly and dispatch blocks (section 12) |

**UI for these features** goes inside the existing console only (rule 0.2):

- **Flag queue.** A flag `twin-icon-btn` with a count badge in the header's
  end cluster. It opens a `twin-flags-panel` ("Flagged areas · nothing is
  sent without you"). Each flag card shows:
  - title, severity, confidence
  - `agent_mode` (LLM or rules)
  - the brief
  - citations
  - Approve / Dismiss / Preview & dispatch buttons, where the preview
    states the recipient count and radius before sending
- **Map layers** in the existing layer control:
  - `flag-areas` and `flag-glow`
  - `alert-zones` and its outline (CAP polygons)
  - `air-stations` and labels
  - `transit-vehicles` and `transit-stalled-halo`
  - `cctv-streams`
- **Drawer additions:**
  - alerts in force for the cell
  - the anomaly sigma ("2.7σ above normal for this cell")
  - the "Live feeds" block for operator cameras
- **Health pill:** every new source shows its `ok`, `degraded` or `failed`
  status from `twin_data_snapshot`.
- The prototype's `static/js/twin-console.js`, `twin-layers.js`,
  `digital-twin.js`, `twin-stream.js`, `static/css/twin.css` and
  `partials/twin_console.html` contain all of this. **Port the behaviour,
  but restyle it to match the production console exactly.**

### 14.2 Order of work (each step should leave the app working)

1. **Models and migration.** Run `flask db upgrade` and confirm the base twin
   still loads.
2. **Config and dependencies.** Install the requirements and copy the
   `.env.example` blocks. The owner will supply the keys.
3. **Official alerts.** Port `sachet.py` and `alerts.py`, add the
   alerts job and routes, add the `alert-zones` layer. Verify that
   `POST /api/twin/alerts/refresh` pulls Telangana and Karnataka CAP
   alerts, and that re-polling updates rows instead of duplicating them.
4. **Live stations, transit and global events.** Port `live.py` and its
   adapters, add the jobs, routes and layers. Verify that OpenAQ and AQICN
   stations appear near Bengaluru.
5. **Scoring extension.** Port `alert` and `disruption` into the scoring.
   Confirm a quiet city scores the same as before.
6. **Anomaly baselines.** Run `python scripts/backfill_baselines.py` once.
7. **Agents and RAG.** Port `twin/agent/*`, `forecast.py`, `windfield.py`
   and `rag.py`, and add the agent job and the `/agent/*` and `/flags`
   routes. Check that:
   - `POST /api/twin/agent/run` works with no LLM key (`agent_mode=rules`);
   - it works again with `OPENAI_API_KEY` set (`agent_mode=llm`);
   - running it twice **updates** flags rather than duplicating them.
8. **Dispatch.** Register the alert channel in `app.py`. Test that preview
   shows the recipient count, that the cooldown blocks a second send inside
   30 minutes, and that a `twin_dispatch` audit row is written.
9. **Console UI.** Add the flag button and panel, the layers, the drawer
   sections, and the health-pill sources, all restyled to production.
10. **Security fixes** (section 11) and **tests** (section 13).

### 14.3 Rules that must survive the port

These are the bugs and design points from section 5.3:

- **Wind direction.** `wind_direction_10m` is where the wind comes *from*.
- **Flag upsert key.** Use a coarse H3 resolution-5 cell around the
  cluster centre.
- **Hyderabad snapping.** Snap projections to grid cells within ~1.5 km.
- **Zero-token calm days.** No LLM call runs when nothing crosses the
  threshold.
- **The LLM never produces a score, coordinate or time.**
- **No automatic dispatch.** There is no scheduler → dispatch path.
- **AQICN.** Never use its `/feed/geo:` endpoint as a fallback.
- **SACHET.** Re-polling is an upsert, an `Update` supersedes the alert it
  replaces, and expired alerts stop counting.
- **Observation timestamps.** Use the source's own `observed_at`. Readings
  older than 120 min are shown as stale, and vehicles older than 30 min are
  dropped.

### 14.4 Done when

- [ ] Both agents run on schedule and on demand, in `rules` and `llm`
      modes, and write deduplicated `pending` flags with briefs, evidence
      and citations. Citations appear once SOP files are placed in
      `data/twin/corpus/`.
- [ ] The flag panel shows the queue, and an analyst can approve, dismiss,
      preview and dispatch. Dispatch reaches users in-app, plus WhatsApp
      when Twilio is configured, and is audited.
- [ ] CAP alerts, stations, transit (when configured) and the anomaly sigma
      feed the scores and appear as layers or drawer sections.
- [ ] The base twin's existing behaviour, layout and scores on a quiet day
      are unchanged.
- [ ] The ported tests pass.

---

## 15. BUILD THIS SECOND: the 3D map upgrade

**Goal:** make the 3D in the existing maps look like a real city model and
carry information, not just decoration. The maps are the twin console
(Hyderabad and Bengaluru panes, and `/digital-twin`) and the dashboard's two
city flood maps.

**Constraints:**

- Everything here works on **MapLibre 4.7.1**. Don't upgrade it, and don't
  add a globe.
- No new cards or rows. Use only the extension points in section 0.
- Every new layer registers in the `twin-layers.js` registry, respects the
  layer order in `digital-twin.js`, and has a toggle.
- Everything must still look right with the Satellite, Street and GIBS
  basemaps.

### 15.1 Real terrain (the biggest win for a flood tool)

Hyderabad sits on the Deccan plateau, with lakes and nalas cut into rolling
granite. Bengaluru's valleys are where water collects. Showing the ground's
shape makes low-lying risk visible.

- **Source:** keyless AWS Terrarium DEM tiles.

  ```js
  map.addSource("twin-dem", {
    type: "raster-dem",
    tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
    encoding: "terrarium", tileSize: 256, maxzoom: 14
  });
  ```

  Use a **second** source with the same tiles for the hillshade layer, so
  the terrain mesh and the hillshade don't fight over one source.
- **Terrain:** `map.setTerrain({ source: "twin-dem", exaggeration: 1.6 })`.
  The cities are fairly flat, so a modest exaggeration is needed before the
  relief reads at all. Tune it between 1.4 and 2.0, and make it a constant
  in `twin-layers.js`.
- **Hillshade:** add a `hillshade` layer above the imagery and below the
  buildings. Use `hillshade-shadow-color: "rgba(2,6,23,0.55)"`,
  `hillshade-highlight-color: "rgba(148,163,184,0.25)"`,
  `hillshade-exaggeration: 0.35`, and
  `hillshade-illumination-direction: 315`. Keep it subtle: the satellite
  image stays the main visual.
- **Toggle:** "Terrain" in the layer control. It's on by default in the full
  page, and on in the compact dashboard card only if the frame rate stays
  acceptable (see 15.8).
- **Check after enabling:** hex extrusions, buildings, circles and flag
  lines must sit on the terrain surface without floating or sinking. If a
  line layer z-fights, raise its `line-width` slightly or add
  `line-translate-anchor: "map"`.
- **Reuse the elevation data.** The twin already stores elevation per cell
  (section 4.1). Show it in the drawer ("Elevation 512 m · 14 m below the
  zone median") so the terrain you *see* matches the terrain *score*.

### 15.2 Buildings that read as a city

The current `buildings-3d` layer is a flat slate block at opacity 0.92.
Upgrade it:

- **Grow in with zoom** instead of popping in at z13. Interpolate height and
  base from 0 at z13 to their full value at z14.5:

  ```js
  "fill-extrusion-height": ["interpolate", ["linear"], ["zoom"],
      13, 0, 14.5, heightExpression],
  "fill-extrusion-base":   ["interpolate", ["linear"], ["zoom"],
      13, 0, 14.5, ["coalesce", ["get", "render_min_height"], 0]],
  ```

- **Colour by height, in our palette:** a slate to steel-blue ramp
  (`#1e293b` 0 m → `#334155` 15 m → `#3b4f6b` 45 m → `#4b6a8f` 120 m →
  `#7aa2c8` 250 m+). Tall towers in HITEC City, Gachibowli, the Outer Ring
  Road corridor and Whitefield should stand out from low-rise old-city
  fabric.
- **Opacity:** 0.85 over satellite, and 1.0 on the Street basemap. Set it
  when the basemap changes.
- Keep `fill-extrusion-vertical-gradient: true`. It gives the facade
  shading that separates neighbouring buildings.
- **Critical buildings.** Buildings with hospital, school, police,
  fire-station or shelter tags (`class`/`subclass` in the OpenMapTiles
  schema, or matched against `twin_infrastructure` positions) get a **second
  extrusion layer**, filtered to those classes and coloured by type:
  - hospital `#f43f5e`
  - school or shelter `#38bdf8`
  - police or fire station `#a78bfa`

  This way the analyst can see *which* buildings matter inside a
  red cell. **Expect the fallback:** OpenFreeMap serves the OpenMapTiles
  schema, whose `building` layer carries only `render_height`,
  `render_min_height`, `colour` and `hide_3d`, with no class. Hospitals and
  schools exist as points in the `poi` layer, not as building classes. Check
  with `map.querySourceFeatures` once, then use the fallback. If the vector
  tiles lack usable class tags, build a GeoJSON
  from `twin_infrastructure`, draw each asset as a small hexagon footprint
  (20 m radius, generated client-side), and extrude it to 25 m in the same
  colours.

### 15.3 Risk hexes as volumes, not pillars

Right now the hexes rise up to 420 m, which dwarfs the buildings and hides
the city at street zoom. Make the height depend on zoom:

```js
"fill-extrusion-height": ["interpolate", ["linear"], ["zoom"],
    10, riskHeightExpression(),                         // city view: full columns
    13, ["*", 0.35, riskHeightExpression()],            // district view: shorter
    15, ["*", 0.04, riskHeightExpression()]]            // street view: a thin tinted slab
```

MapLibre only allows `["zoom"]` at the top level of the expression, which
is what this does. The data expression goes inside each stop.

- **City view:** the columns show at a glance which cells are rising.
- **Street view:** each hex becomes a thin coloured "floor" under the
  buildings, so the buildings stay visible.
- **Critical cells get a floating cap:** a second `fill-extrusion` layer
  filtered to `risk_score >= 75`, with `base = height` and `height = height
  + 12`, in solid `#ef4444` at 0.9 opacity. It reads like a warning lid at
  any zoom.
- **Animate horizon changes.** The layers are already flagged
  `twinAnimatable`. Make sure height and colour transitions use
  `"fill-extrusion-height-transition": {duration: 600}`, so switching
  Now → +6h visibly grows or shrinks the columns.
- **Keep the existing rules:** the `twin-hex-outline` filter (≥ 25) and the
  degraded-cell dashed outline.

### 15.4 Water in 3D

- **Lakes and tanks.** Draw `water-bodies` as a `fill-extrusion` with
  height 0 and base 0 and colour `rgba(34,211,238,0.55)`, plus a glowing
  outline. With terrain on, the water then sits *in* the terrain
  depressions. This helps a lot in Hyderabad (Hussain Sagar, Durgam
  Cheruvu) and Bengaluru (Bellandur, Varthur).
- **Drains and nalas.** Keep the line layers and add a subtle glow. At z14
  and above, add `line-width` interpolated by zoom so the major nalas read
  as channels.
- **Hydro-pressure surface (optional, labelled honestly).** For cells whose
  **hydro sub-score** is ≥ 50, add a translucent cyan extrusion
  (`rgba(56,189,248,0.35)`) with height `hydro_score × 0.3` metres, above
  the risk slab.
  - Label it in the legend and the drawer as an **index, not a water
    depth**. We don't model depth, so never put "m" or "depth" on it.
  - Toggle: "Water pressure (index)". Off by default.

### 15.5 Flags, alerts and cameras in 3D

- **Flag areas as glowing walls.** For each pending flag, build a thin ring
  polygon (the flag area outline buffered by ~15 m) and extrude it 60 m in
  the severity colour at 0.5 opacity. Pulse its opacity between 0.35 and
  0.6 with `requestAnimationFrame`, throttled to about 10 fps. Pause the
  pulse when the tab is hidden. It should read as "this area is under
  review" from any camera angle. Keep the existing `flag-areas` and
  `flag-glow` lines underneath.
- **Official alert zones (CAP polygons).** Show these as a low wall (30 m,
  dashed-looking alternating segments are fine as flat lines) in amber, so
  an official warning is visibly different from an agent flag.
- **Camera cones.** The existing `cctv-cone` layer is flat. At z16 and
  above, extrude the cones to 6 m at low opacity (`rgba(250,204,21,0.25)`)
  so the camera's view direction reads in 3D. Only draw cones for cameras
  with a real tagged direction. Keep inferred directions flat and dashed.
- **Infrastructure pins.** Use the colour-coded hexagon pillars from 15.2
  in place of flat circles at z14 and above. Keep circles below z14.

### 15.6 Light and atmosphere

All of these are MapLibre 4.x APIs:

- **Directional light.**

  ```js
  map.setLight({ anchor: "map", position: [1.2, 200, 35],
                 color: "#dbeafe", intensity: 0.45 })
  ```

  This gives consistent facade shading.
- **Optional time-of-day light.** Rotate the light's azimuth with the local
  sun position using a small inline solar-position function. It's cheap,
  and it makes the model feel alive. Keep intensity between 0.35 and 0.5
  so night never goes black.
- **Horizon haze.** Use `map.setSky({...})` for a dark horizon blend
  (`"sky-color": "#0b1220"`, `"horizon-color": "#1a2234"`,
  `"fog-color": "#0b1220"`, `"horizon-fog-blend": 0.4`). Tilted views then
  fade into the card background colour instead of a hard edge.
  **Check first** that `setSky` exists on 4.7.1
  (`typeof map.setSky === "function"`). If it doesn't, skip this item
  quietly and don't upgrade MapLibre for it.

### 15.7 Camera and navigation

- **Pitch cap.** Raise it from 45 to 60 (`maxPitch: 70`), now that the
  terrain and zoom-scaled hexes no longer hide the city.
- **Default view per city**, from the `cityMeta.camera` settings:
  - Hyderabad: pitch 55, bearing −20, looking toward Hussain Sagar
  - Bengaluru: pitch 55, bearing −12.5
- **One new header icon button, "2D / 3D"** (`twin-icon-btn`, cube icon):
  - 2D: pitch 0, terrain off, extrusions flattened
  - 3D: everything restored
- **Drawer opening.** When a cell's drawer opens, `flyTo` the cell at
  zoom 15.5, pitch 60, and a bearing that faces the cell's nearest
  CCTV/Mapillary direction if one exists.
- Keep right-drag rotate and ctrl-drag pitch (MapLibre defaults), and add
  `NavigationControl({ visualizePitch: true })` in the existing
  map-controls corner.

### 15.8 Performance budget (the twin card shares the dashboard with 8 other maps)

- Initialise `antialias: true` on the twin maps only.
- In the **compact dashboard card**:
  - Terrain is on only while the card is in view (`IntersectionObserver`,
    the same pattern as `data-autostart="visible"`).
  - Buildings start at minimum zoom 14.
  - The flag-wall pulse is off.
- The DEM `maxzoom` is 14. Overzooming beyond that is fine.
- Measure with `map.on("render")` frame timing. Aim for 45 fps or more on a
  mid-range laptop with both panes visible. If a pane drops below 30 fps,
  auto-disable the terrain in the compact variant and show a `twin-toast`
  saying "Terrain paused to keep the dashboard responsive".
- Lazy-load everything new. No new library is needed. The hexagon
  footprints, ring buffers and sun position are about 60 lines of plain JS
  in `twin-layers.js`.

### 15.9 Dashboard city flood maps (Hyderabad | Bengaluru cards)

This is inside their existing init code in `analyst_dashboard.html`. The
cards themselves don't change.

- Add the same `raster-dem` terrain (exaggeration 1.4) and hillshade. Then
  the discharge markers (modelled GloFAS points, not CWC/KSNDMC gauges;
  see section 4.4) sit on real relief, and the river valleys they sample
  become visible.
- Raise the default pitch from 30 to 45 and keep bearing 0.
- Add the `buildings-3d` layer from 15.2 (OpenFreeMap source) from zoom 14,
  so zooming into a station shows the built-up area around it.
- Keep the Esri imagery, the legends and the stats overlays exactly as they
  are.
- Apply the same `GodModeMap` terrain and hillshade in
  `static/js/god-mode-maps.js` (heatmap and warning maps) as an option, off
  by default. Those maps are about density, and relief can distract.

### 15.10 Acceptance checklist

- [ ] Every dashboard row and card is unchanged in order and size. Changes
      are visible only *inside* the maps, in the layer control, and as the
      one new "2D / 3D" icon button.
- [ ] There is still exactly one MapLibre, version 4.7.1, on the page. No
      globe.
- [ ] Terrain, hillshade, zoom-scaled hexes, the critical caps, graded
      buildings, critical-building extrusions, 3D water, flag walls, CAP
      walls, 3D cones and lighting all render in both cities, on all three
      basemaps.
- [ ] Every new layer has a toggle and sits in the documented layer order.
      Imagery stays below the buildings, and the hexes and points stay
      above them.
- [ ] The hydro-pressure surface is labelled as an **index**, never as a
      depth.
- [ ] The performance budget in 15.8 is met, and the compact card degrades
      gracefully.
- [ ] Tests cover:
      - the zoom-scaled height expression (valid MapLibre: zoom at the top
        level)
      - the hexagon-footprint and ring-buffer generators
      - the sun-position function
      - the layer-order invariants (extend `test_layers_js.py`)
- [ ] `.env.example` documents any new tunable. No secrets are committed.

---

## 16. BUILD THIS THIRD: replace the three Windy maps with a better weather slot

**Now:** the dashboard has three Windy iframes: Live Temperature (full
width), Live Satellite, and Fire Danger (FIRMS). They are centred on all of
India. They're generic, they overlap in what they show, and two of them
barely serve an urban flood and heat desk in Hyderabad and Bengaluru.
Fire danger in particular has little use there.

**Task:** remove all three. Replace them with **one or two Windy maps,
and/or one other map that is more useful**, chosen by research against the
criteria below. The aim is a **more sophisticated analyst dashboard**: fewer
panels, each one earning its place.

### 16.1 Constraints

- **Same slot.** The replacement goes exactly where rows 7–8 are now:
  after the city flood maps, before the charts.
- **Same or less space.** It must not take more vertical space than the
  current two rows (50vh + 55vh). One full-width card, or one row of two
  `col-lg-6` cards, is ideal.
- **Same card styling.** `#1a2234` body, `#151b2b` header, 15px bold
  title, pulsing status dot, and the outlined "Open Full ↗" pill.
- **City focus.** Every map opens on **Hyderabad or Bengaluru** at city or
  regional zoom, not on the centre of India. Give each card small
  **Hyderabad | Bengaluru** switch pills in its header, styled like the
  existing header buttons. Switching changes the iframe `lat`/`lon`/`zoom`,
  or runs `flyTo` on a native map.
- **Nothing else moves.** Every other dashboard row stays as it is.
- **Maps are for viewing only.** Nothing embedded here feeds scoring or the
  agents. Those stay on Open-Meteo (section 8).

### 16.2 Research first: evaluate candidates on these criteria

For each candidate, check **and record in your PR description**:

| Criterion | How to check |
|---|---|
| Actually covers Hyderabad and Bengaluru with meaningful data | open it at both cities. Some radar networks show nothing over India |
| Can be embedded | the response has no blocking `X-Frame-Options`/CSP `frame-ancestors`, or it has a tile/WMS/WMTS endpoint we can draw natively in MapLibre |
| Fresh enough | radar/nowcast ≤ 15 min old; satellite ≤ 1h |
| Terms and key | keyless, or a key the owner can get; the terms allow dashboard use |
| Adds something the dashboard doesn't already show | we already have TGDPS rainfall, district rainfall, CWC/KSNDMC flood stations, RainViewer radar and NASA GIBS inside the twin |
| Performance | one more iframe or map must not slow the dashboard noticeably |

**Candidates to research. Not all will pass, so pick the best, and don't
use all of them:**

1. **A single Windy embed with an overlay switcher.** One iframe, plus a
   row of header tabs that swap the `overlay=` parameter in the iframe
   `src`. Candidate overlays: rain/thunder forecast, wind (with its
   particle animation), radar, satellite, and temperature or "feels like".
   Confirm each overlay name actually renders inside `embed.windy.com`
   before using it, because some don't in the embed. Also add
   `calendar=` / forecast-timeline controls if the embed supports them. This alone
   replaces all three current iframes with one card.
2. **IMD (India Meteorological Department) products.** Doppler weather
   radar imagery (check whether the Hyderabad and Bengaluru-region radars
   have current products), district-wise nowcast and thunderstorm
   warnings, and INSAT-3D imagery (IMD or ISRO **MOSDAC**). This is the
   authoritative Indian source. Check what can be framed or pulled as
   images or tiles.
3. **ISRO Bhuvan / NDEM (NRSC).** Flood-hazard, inundation and
   disaster-services layers over Telangana and Karnataka. Check for public
   WMS endpoints.
4. **NASA GPM IMERG precipitation rate through GIBS** (keyless WMTS; we
   already use GIBS in the twin). A satellite-derived rain rate that works
   where ground radar is thin. It could be a native MapLibre card with a
   time slider.
5. **A native "Rain nowcast" MapLibre map** built from the RainViewer
   radar frames the twin already indexes (past ~2h + nowcast), with
   play/pause animation and a city switch. Check first that RainViewer
   actually has returns over both cities. If it doesn't, drop this option.
6. **KSNDMC (Karnataka)** and other state disaster portals for Bengaluru.
   TGDPS already covers Telangana on the dashboard.

### 16.3 Recommended outcome (adjust based on what the research shows)

- **Card A (keep Windy, but only one).** "🌦️ Weather — Windy". A single
  embed centred on the selected city, with overlay tabs such as
  Rain/Thunder · Wind · Radar · Satellite · Feels-like, and the city pills.
  It replaces all three current Windy iframes.
- **Card B (the authoritative or local view).** The best-scoring non-Windy
  option from 16.2. In order of preference:
  1. IMD radar or nowcast for the city, if embeddable and current.
  2. Otherwise a native MapLibre **rain nowcast / GPM IMERG** map with a
     time slider.
- **Layout:** A and B side by side as one row of two `col-lg-6` cards, at
  about 55vh with a 420px minimum. Or, if only A passes research, A alone
  at full width at about 55vh.
- **Drop fire danger** unless the research finds a concrete use for it
  during Hyderabad or Bengaluru heatwaves. If it's kept, it becomes an
  overlay tab in Card A, not its own card.

### 16.4 Done when

- [ ] The three old Windy cards are gone. The new slot holds 1–2 cards in
      the same position, no taller than before, in identical card styling.
- [ ] Every map opens on Hyderabad or Bengaluru and switches between them.
- [ ] Every map has passed the embed, coverage and freshness checks
      (recorded in the PR), and none is blank over either city.
- [ ] Overlay tabs (if used) work, and the "Open Full ↗" link matches the
      current city and overlay.
- [ ] Dashboard load time is no worse than with the three iframes.

---

## 17. BUILD THIS FOURTH: live and local maps, search, watched places, agent activity

**Why:** the audit in section 4.4 found that the dashboard's warning map
mixes real incident data with **hardcoded mock hazards and random
timestamps**, and draws temperatures for eight coastal cities, none of
them ours. It also polls fast enough to exhaust Open-Meteo's free quota,
labels modelled discharge as CWC/KSNDMC gauges, and runs place search
against a service whose policy forbids autocomplete. Section 17 fixes all
of this. It also gives analysts three things they asked for: a proper
search bar, a live list of the places they watch, and proof that the agent
is working.

All of section 0 still applies. No new rows or cards. Changes go inside
existing maps, the existing search box, the layer control, the header icon
cluster, the flag panel and the drawer.

### 17.1 Make every "live" map real and local

| Item | Fix |
|---|---|
| `/api/live_govt_hazards` (mock) | **Delete the hardcoded list.** Serve official alerts from the twin: CAP alerts in force from `twin_external_alert` for both cities (polygon, severity, headline, `sent`, `expires`, source = IMD/state SDMA as stated in the CAP), plus GDACS/USGS events within 300 km (`global_events.py`). Return the **source's own timestamps**. If there are none, return an empty list, and the map shows "No official alerts in force" |
| `/api/weather_warnings` / `get_weather_warnings()` (mock) | Delete the mock. Return the same CAP alerts, filtered to the weather-type events (`cap:event` rain, thunderstorm, heat, wind). One function serves both endpoints |
| `/api/weather_data` (8 coastal cities, uncached) | Replace the city list with **Hyderabad and Bengaluru, with their zone centres** (`ZONE_DEFS`): 14 points in **one** batched Open-Meteo call (comma-separated `latitude=`/`longitude=`, as `fetch_live_flood_gauges` already does). Add a 10-minute server-side TTL cache (`cachetools`, already a dependency). Include `apparent_temperature` and `precipitation`, since heat and rain are what this desk acts on |
| `updateLiveWeather()` every 3.5 s | Poll **every 5 min** (the twin's compute cadence), pause while the tab is hidden (`visibilitychange`), and update the GeoJSON source data with `setData` instead of clearing and re-adding every layer |
| `/api/live_hazard_incidents` includes `pending` reports | Draw approved reports as they are now. Draw pending reports hollow and dashed, and add "unverified" to the popup. Never mix the two in one heat intensity |
| `warningMap` framing | Frame it on the selected city (Hyderabad \| Bengaluru pills in the card header, styled like the flood-map buttons), not on India |
| Flood "gauges" legend says CWC/KSNDMC | Relabel it honestly: "Modelled river discharge (GloFAS via Open-Meteo), relative to this point's own normal". Keep the CWC/KSNDMC buttons as **links** only. For Bengaluru, keep points on the Vrishabhavathi and Arkavathy **river** channels, and move lake and junction points (Bellandur, Silk Board…) to the watched places (17.3), where the twin's cell score describes them properly. If the owner obtains KSNDMC or CWC gauge access later, add a real adapter under `twin/ingest/` and switch the legend |
| Every popup and tooltip on these maps | Show **source** and **age** ("IMD via SACHET · 14 min ago"). If data is stale (older than 2 × its poll interval), grey the marker and say so |

Add a test that `/api/live_govt_hazards` and `/api/weather_warnings` contain
no hardcoded coordinates, and that with an empty `twin_external_alert` both
return `[]`.

### 17.2 Search bar: fast, local-first, and within the geocoders' rules

**Keep the existing search box** (`.twin-search`, one per city pane, in the
pane toolbar). Change what it searches and how results behave.

**Backend: one endpoint, local first.**
`GET /api/twin/<city>/search?q=&limit=` (behind the same roles as the rest
of `/api/twin/*`) returns grouped results. Each result has
`{kind, label, sublabel, lat, lon, cell_h3, score, status, source}`:

1. **Parsers first, no network:**
   - coordinates (`17.4239, 78.4738` or `17.4239 78.4738`)
   - an H3 index (15 hex characters starting with `8`)
   - a zone name or slug
2. **Local index, no network,** searched with case- and accent-insensitive
   prefix-then-substring matching:
   - watched places (17.3)
   - zones (`ZONE_DEFS`)
   - named `twin_infrastructure` assets (hospitals, schools, substations…)
   - named water bodies from the water layer
   - CAP alerts in force (area description)
   - pending flags (title)
   - station names
3. **Addresses:** a server-side geocoder proxy,
   `GET /api/twin/geocode?q=&city=&mode=suggest|search`:
   - **`suggest` (typeahead)** uses **Photon**
     (`https://photon.komoot.io/api/?q=&limit=6&lat=&lon=&bbox=minLon,minLat,maxLon,maxLat`),
     biased to the pane's city centre and bounded to its bbox. Photon is
     built for search-as-you-type.
   - **`search` (Enter pressed)** uses **Nominatim**
     (`format=jsonv2&viewbox=…&bounded=1&countrycodes=in`). Keep it to one
     request per second, process-wide, and send an identifying
     `User-Agent` with a contact taken from a new env var
     `TWIN_GEOCODER_CONTACT` (never hardcoded).
   - Cache both for 24h (`cachetools.TTLCache`). Photon results come back
     as GeoJSON features, so normalise them to the result shape above.
   - Drop results outside the city bbox. Mark results outside the clip
     polygon "outside the twin grid (no score)".
   - The browser **never** calls Nominatim or Photon directly any more.
4. **Every result carries its live score.** Look up the containing H3
   cell's `now` state, so each row shows a band-coloured dot and a
   number.

**Frontend (`wireSearchBox` in `twin-console.js`):**

- Local results show instantly. Address suggestions arrive after a 250 ms
  debounce, and a stale response is dropped (keep the existing request-id
  guard).
- The dropdown is grouped, each group with a small label: **Watched
  places · Zones · Assets · Alerts & flags · Addresses**.
- **Keyboard:** `/` focuses the box, ↑/↓ move, Enter selects (or runs the
  Nominatim search if nothing is highlighted), Esc closes. Use
  `role="combobox"`, `role="listbox"` and `aria-activedescendant`.
- **Empty focus** shows the city's watched places with live scores, then
  the last 5 searches (localStorage, wrapped in try/catch).
- **Selecting a result:**
  1. `flyTo` using the section 15.7 drawer camera (zoom 15.5, pitch 60)
  2. open the drawer for the containing cell
  3. drop a pulsing marker that fades after 6 s
  - A flag result opens that flag in the flag panel. An alert result
    highlights its polygon.
- **Other city:** if the best match lies in the other city's bbox, show it
  as "in Bengaluru →" and route it to that pane.
- **Styling:** use the existing `.twin-search`, `.twin-search-input`,
  `.twin-search-results` and `.twin-search-result` classes. Add only what
  the group labels and score dots need, in the twin palette.

### 17.3 Watched places: live status for the spots analysts care about

A curated list of named places per city, each tied to its H3 cell. Each
place is **always visible with its live score**, so an analyst sees "Silk
Board 68 ↑ warning" without hunting for the right hexagon.

- **Data:** `data/twin/places.json`. Each entry is
  `{slug, city, name, kind: landmark|waterlogging|lake|junction|underpass, lat, lon, h3, geocoded_by, verified}`.
- **Seeding:** `scripts/seed_places.py` geocodes the names below through
  the 17.2 Nominatim proxy (1 request/s) and computes `h3` at the twin's
  resolution. It writes `verified: false`, and lists any point that falls
  outside the clip polygon so a person can fix it. **Coordinates are
  never typed in by hand or by a model.** The owner reviews the file and
  sets `verified: true`. The UI marks unverified places with a small "?".
- **Starting list** (names only; indicative, taken from places often named
  in local flood coverage; the owner confirms or replaces it with the
  GHMC and BBMP official waterlogging-point lists):
  - **Hyderabad:** Hussain Sagar, Tolichowki, Mehdipatnam, Malakpet,
    Moosarambagh, Chaderghat, Ameerpet, Begumpet, Khairatabad, Lakdikapul,
    HITEC City, Gachibowli, Kukatpally, Durgam Cheruvu, Secunderabad,
    L.B. Nagar, Uppal, Charminar.
  - **Bengaluru:** Silk Board Junction, Bellandur, Varthur, Marathahalli,
    Mahadevapura, K R Puram, Hebbal, Koramangala, HSR Layout, Sarjapur
    Road, Whitefield, Yelahanka, Majestic, Shanthinagar, Electronic City.
- **API:** `GET /api/twin/<city>/places` returns, for each place:
  - its score for now, +3h and +6h, its band, and the signed change
  - its **top driver** (the largest sub-score, e.g. "hydro 71")
  - any CAP alerts in force over it
  - the nearest station reading with its age
  - the anomaly sigma, if baselines exist

  Recompute from `twin_cell_state`. No new external calls.
- **UI (existing extension points only):**
  - **Map layer** `places` in the registry: a symbol layer of name labels
    with a band-coloured dot, from min zoom 11. It sits above the hexes
    and below the flags, and has a toggle in the layer control, on by
    default.
  - **Header icon button** (`twin-icon-btn`, map-pin icon) opens a
    **Watched places** panel styled exactly like `twin-flags-panel`. It
    sorts by score, shows now → +6h as a tiny three-step bar, and a click
    runs the 17.2 selection behaviour. A place that crosses into
    `warning` or `critical` since the last update gets a subtle highlight.
    It does not auto-open and makes no sound.
  - **Drawer:** if the cell contains a watched place, show its name at the
    top of the drawer.
  - **Live updates:** on SSE `state_update`, refetch `/places` for that
    city (one request) and update the layer and panel in place.

### 17.4 Show that the agent is working

- **Record every run.** Write a `twin_data_snapshot` row per agent per city
  with `source_key` `agent_triage` or `agent_forecast`:
  - `started_at` and `finished_at`
  - `status`: `ok`, or `failed` with `error_message`
  - `records_ingested` = flags created or updated

  The health pill then shows the agent like any other source, with no new
  table. Take the mode (`llm`/`rules`) and the created-versus-updated split
  from the `twin_flag` rows touched during the run window.
- **Publish SSE events** `agent_run` with `phase: started|finished`,
  `agent`, `city`, `mode`, `created`, `updated`, `duration_ms`, from
  `twin/jobs.py` and from `POST /agent/run`.
- **Extend `GET /agent/status`** with, per agent and city:
  - `last_run` (the fields above)
  - `next_run_at`: read from the scheduler job's `next_run_time` on the
    scheduler process; elsewhere compute it as `finished_at` +
    `TWIN_AGENT_INTERVAL_MIN`
  - `calm`: true when the run ended at the threshold with zero tokens
- **UI:** one status line in the **flag panel header**, for example
  "Triage 14:20 · rules · 0 new, 2 updated · next 14:30" or "Calm. Nothing
  above 55, no model called". While a run is in progress, show a small
  spinner on the flag button. The existing "run now" action shows the same
  line when it finishes. No new card.

### 17.5 Done when

- [ ] No endpoint returns hardcoded hazards, warnings or random
      timestamps. `warningMap` shows only Hyderabad and Bengaluru data,
      each item with its source and age.
- [ ] One open dashboard makes at most one `/api/weather_data` upstream
      call per 10 minutes. Polling pauses in a hidden tab.
- [ ] The flood-map legend describes modelled discharge as modelled.
- [ ] Search answers coordinates, H3 ids, zones, places, assets, alerts and
      flags with no network call. Addresses go through the server proxy
      (Photon for typeahead, Nominatim on Enter at ≤ 1 request/s, both
      cached). Every result shows a live score. Keyboard and screen-reader
      navigation work.
- [ ] `data/twin/places.json` was produced by the seed script and reviewed
      by the owner. The `places` layer, the Watched places panel and the
      drawer header update on `state_update`.
- [ ] The flag panel shows when each agent last ran, in which mode, what
      it changed, and when it runs next. The health pill lists
      `agent_triage` and `agent_forecast`.
- [ ] `.env.example` documents `TWIN_GEOCODER_CONTACT`. There are tests for
      the coordinate and H3 parsers, the geocoder rate limit and cache, the
      places endpoint, the agent-run snapshot rows, and the "no mock data"
      checks in 17.1.
