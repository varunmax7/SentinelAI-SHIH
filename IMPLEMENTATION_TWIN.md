# Urban Digital Twin: max.md Sections 14 & 15, complete

Companion to `IMPLEMENTATION.md` (the AI Disaster Prediction Agent) and
`max.md` (the original handoff spec this work is scoped against). Covers
Sections 14 and 15 of `max.md` in full. **Section 16 (replacing the three
Windy panels) was explicitly excluded by instruction and is untouched.**

> **Read this before trusting `max.md` literally.** That spec was written
> against a different, more elaborate prototype baseline than what's actually
> in this repo. In several places this codebase had already solved a problem
> `max.md` describes as unsolved (the triage agent, SACHET alerts, the
> flat/extrusion hex split that avoids a rendering bug `max.md`'s own 15.4
> water suggestion would have reintroduced) or already diverged from its
> assumed file/class names (`twin-icon-btn`, `twin-toast` do not exist here;
> the real classes are `twin-btn`, `notice()`). Where the two disagreed, this
> document follows the actual repo, not the spec.

---

## 1. Section 14 - agents, RAG, dispatch, live systems

Already had, before this work: the triage agent (`twin/agent/`), SACHET CAP
alerts, GDACS/USGS, the flag table and its review UI (approve/dismiss).

### 1.1 Anomaly baselines

`twin/anomaly.py` - 5-year Open-Meteo archive climatology (**annual, not
day-of-year binned** - a declared simplification, stated in the module
docstring) per coarse sample point, compared in standard deviations.
`scripts/backfill_baselines.py` populates `twin_baseline`; run once, safe to
re-run. Sigma surfaces in the drawer's `explain()` text only when it clears
the watch/alert threshold. Verified live: 58/58 sample points backfilled (5
years, both cities); a real recompute picked up a reading on 919/919 cells
in each city.

### 1.2 Flag dispatch, backend and UI

`twin/dispatch.py` - the only path from an approved flag to a real phone.
`register_alert_channel()` wires the host's user/notification/WhatsApp
machinery in, the same registration pattern `security.py::adopt_login_required`
already uses. DB-backed cooldown (the existing `/api/flood_station_alert`
uses an in-memory one that does not survive a restart), radius cap + buffer,
a full `twin_dispatch` audit row on every send.

`twin/models.py` gained `twin_flag_cell` (a flag's full cluster footprint,
not just its one `worst_cell` - `persist_flags` in both agents now writes
every cell, replacing rather than accumulating on each re-run) and
`twin_dispatch`.

**UI**: `openFlagQueue()` in `twin-console.js` now fetches pending *and*
approved flags in one call and renders two sections - pending flags keep
their existing Approve/Reject actions, approved flags get a new "Preview
dispatch" -> recipient count -> "Send Alert" flow, backed by
`GET/POST /api/twin/flags/<id>/dispatch{,/preview,/history}`. Verified
against the one real flag in the live database: preview correctly showed 1
real recipient; a real send earlier in this work correctly wrote a
`twin_dispatch` audit row and sent one real WhatsApp message (see §4 on
test-isolation below for why that happened during development, not by
design).

### 1.3 Forecast agent

The genuinely large addition. `twin/forecast.py` (pure, deterministic,
unit-tested with synthetic data before ever touching the graph) plus
`twin/ingest/windfield.py` and `twin/agent/{forecast_state,forecast_nodes,
forecast_graph}.py`, wired into `twin/agent/__init__.py::run_forecast()`
alongside the existing `run_triage()`.

**Mechanics**, stated precisely because the physics here is a declared
simplification, not a weather model:

- **Rain moves** (advection): a source lattice point's rain value is carried
  along `(wind_dir + 180) % 360` for `wind_speed * hour` km and snapped to
  the nearest actual H3 cells (within 2.5 km, capped at 6 cells per
  projection). Intensity is **not** attenuated or intensified in transit -
  the value at hour h downwind is whatever the source showed at hour h. This
  is why `RAIN_SOURCE_MM_H` (2.0) is only a pre-filter and
  `RAIN_ARRIVAL_MM_H`/`RAIN_SEVERE_MM_H` are severity *bands*, not a second
  gate the same unchanging value could never clear.
- **Heat does not move**: read in place per lattice point per hour, banded at
  watch (38 degC apparent) / critical (42 degC).
- **Grouping** reuses H3 resolution-6 cells (~6 km across) as the spatial
  cluster key - `max.md`'s own "group within 6 km" turned into a dict key
  instead of a custom algorithm.
- **Confidence** decays with lead time (`exp(-hour/8)`) and in light wind,
  boosted when cloud cover corroborates the rain reading.
- Shares the exact same `persist_flags` function the triage agent uses (same
  table, same human gate, same review UI) - imported directly, not
  reimplemented. `cluster_key` is deliberately **not** keyed on arrival hour,
  so the same system re-detected next poll updates its existing flag instead
  of filing a new one as the hour counts down.

**A real bug caught while testing this**: the forecast graph's LangGraph
checkpointer resumes state across invocations under the same `thread_id` (one
per city, reused every scheduled cycle, forever). Calling `graph.invoke({})`
let a *previous* test run's stale `briefs`/`flagged_keys` leak into a
completely quiet cycle's reported output - confirmed via direct sqlite
inspection that no bad data actually reached `twin_flag`, but the reporting
was wrong and would have bitten on every real scheduled cycle, not just a
test. Fixed by seeding every state key explicitly on every invoke (the
triage graph already does this for exactly this reason; the forecast graph
did not, until now).

Verified live end-to-end three ways: synthetic wind/rain data proving the
downwind-only projection and wind-convention correctly excludes an upwind
cell; a forced-low-threshold run producing 246 events -> 37 deduplicated
flags with correct offline briefs and `twin_flag_cell` rows, on an isolated
copy; a real run against live weather for both cities producing the honest
`0 events` a quiet day should.

### 1.4 RAG

`twin/agent/rag.py` - **keyword-scored, not embeddings**. `faiss-cpu` +
`sentence-transformers` would work and are a compatible upgrade path (same
`retrieve(query, top_k)` interface), but were not installed: `torch` is a
multi-GB dependency for what is an entirely optional feature (an empty
corpus - `data/twin/corpus/`, ships with only an extensionless `README` - is
the fully-supported default), and this environment had no way to verify an
install wouldn't stall or bloat someone's deployment. TF-IDF-style keyword
overlap over a few hundred short SOP paragraphs is not meaningfully less
accurate than embeddings at that corpus size, and numeric queries ("did the
SOP say 60mm or 80mm") are handled by an explicit exact-number-match boost
that embeddings are actually worse at.

Wired into both agents' brief-drafting: `_sop_citations()` retrieves up to 4
relevant passages per event/cluster, appended to the LLM prompt and the
offline-template path alike, and merged into the same `citations` list the
review UI already renders (`kind: 'sop'`, no frontend change needed). Tested
directly with a real corpus file: numeric query correctly matched the
paragraph containing "62 mm" over an unrelated one; keyword query correctly
matched on topic.

### 1.5 Live stations & transit

`twin/ingest/stations.py` (OpenAQ, AQICN, CPCB/data.gov.in) and
`twin/ingest/transit.py` (GTFS-Realtime), aggregated by `twin/live.py` into
the new `twin_observation` table, with jobs (`twin_ingest_stations` /15 min,
`twin_ingest_transit` /2 min) and routes (`GET /{city}/live{,/stations,
/transit}`, `POST /live/refresh`).

**None of the three station sources has a keyless tier** - unlike every
other adapter in this package, real-time ground AQ stations cost a key
everywhere the twin's own research found. All three keys
(`OPENAQ_API_KEY`, `AQICN_TOKEN`, `DATA_GOV_IN_KEY`) were absent while
building this, so these three adapters are **reviewed-by-reading, not
field-verified** - stated in `stations.py`'s own module docstring, not just
here. The graceful-degradation path (missing key -> `None` -> layer stays
honestly empty) *was* verified live. Same story for transit: no stable
public GTFS-Realtime feed exists for either city (checked while building
this), so `transit.py` is complete and correct-by-inspection but has never
seen a real vehicle.

**Scoring integration, done carefully for zero regression risk.** A real
station AQI, when in range, now takes priority over the Open-Meteo estimate
that `env_sub_score` already used; a new `disruption` hazard term (12%
weight) activates only when nearby transit data exists.
**`scoring.hazard_score()` renormalises hydro/incident/env's weights back to
sum to 1.0 whenever `disruption` is `None`** (the situation for every cell of
both cities today, since no transit feed exists) - so a city with no
transit configured scores *exactly* as it did before this term existed.
Verified by direct comparison: `station_aqi: None, disruption_pct: None`,
`aqi` equal to the untouched Open-Meteo value, same risk numbers as a
pre-change compute pass. `raw_inputs['aqi']` was fixed to report whichever
value was *actually used* (station or fallback), not always the Open-Meteo
one regardless - the original version of this change would have shown the
wrong number in `explain()`, caught on review before shipping.

### 1.6 Camera operator feeds

`twin/cameras.py` reads `data/twin/cctv_streams.json` (ships as `[]`), filters
by city and optionally by radius from a clicked point, and never fetches a
stream URL itself - the browser loads it directly, per the hard rule in
`max.md` §7 and restated in the module's own docstring. Route:
`GET /cctv/streams?city=&lat=&lon=&radius=`.

**UI**: the existing camera drawer (`openCameraDrawer` -> `renderCameraDetail`)
gained a "Live feeds" section, fetched separately and rendered as "No live
feed available for this city yet" (the only real case today) or an actual
player - `hls.js` lazy-loaded from jsdelivr for `hls` streams, native
`<img>` for `mjpeg` (the browser handles MJPEG natively in an `img` tag) and
periodically-refreshed `<img>` for static `image` snapshots. Tested with a
synthetic 3-entry file: correctly filtered by city and by radius, wrong-city
and far-away entries excluded.

### 1.7 What's still not built

- **Mapillary vector-tile discovery** (`mapillary_tiles.py`) - `streetview.py`
  already calls Mapillary's documented Graph API bbox endpoint; `max.md`
  claims that endpoint returns 0 rows over Bengaluru and recommends a
  hand-rolled MVT tile decoder instead. `MAPILLARY_TOKEN` was not set, so
  this could not be verified either way, and the existing Graph-API path was
  left as-is rather than replacing working (if unverified) code with more
  unverified code.
- **`run_server.py`** launcher script and the specific security fixes listed
  in `max.md` §11 (`FLASK_DEBUG`/`FLASK_HOST` hardening, `_safe_next()`,
  per-process `SECRET_KEY`, site-wide `CSRFProtect`, Twilio webhook
  signature verification) - out of scope for the twin-specific work this
  document covers; genuinely separate from Sections 14/15.

---

## 2. Section 15 - the 3D map upgrade

Built in the priority order `max.md` itself gives (terrain is its own
"biggest win"): terrain + hillshade, zoom-scaled risk hexes with a critical
floating cap, critical-building extrusions, a 5-stop building colour ramp,
directional light + guarded sky/fog, flag/CAP/camera-cone 3D walls with a
pulsing flag animation, a 2D/3D toggle, per-city camera defaults, a
performance guard for the compact card, and terrain on the dashboard's own
flood maps.

### 2.1 Terrain (`twin-layers.js`, `digital-twin.js`)

AWS Terrarium DEM, keyless, **two raster-dem sources over the identical tile
URL** (a terrain mesh and a hillshade layer sharing one source visibly fight
each other over it). `enableTerrainSources()` registers both plus
`twin-hillshade` lazily - never even requested until an operator checks the
box, the same lazy pattern radar/traffic/water/cameras/alerts already use.
`setTerrainEnabled(bool)` is the actual on/off. Off by default everywhere
(compact and full page alike) - a deliberately conservative call given
§15.8's own warning that the compact card "shares the dashboard with 8 other
maps."

### 2.2 Risk hexes

The existing flat/extrusion split at the watch threshold already solved
"420 m columns blacking out the city on a calm day" - a better fix than
zoom-scaling alone, and it predates this work. **Both now apply together**:
`riskHeightExpressionByZoom()` wraps the height expression in an outer
`interpolate` over `["zoom"]` (full columns at city view, 35% at district,
4% at street) - valid MapLibre style spec, since `zoom` appears only at the
expression's top level. A new `twin-hex-critical-cap` layer sits on every
risk>=75 cell, base tracking the same zoom-scaled height, always solid red -
a warning lid that reads at any zoom. `-transition: {duration: 600}` on
height/color/base makes Now -> +6h visibly animate rather than jump, which
works because `SRC.hexes` already sets `promoteId: "h3"`.

### 2.3 Buildings, critical and otherwise

Colour ramp widened from 3 stops to 5 (`#1e293b` -> `#7aa2c8`, 0-250 m).
Opacity switches with the basemap (0.85 satellite/GIBS, 1.0 vector street).

**Critical buildings** (`twin-critical-buildings`): hospital/school/police/
fire_station/shelter assets from `twin_infrastructure` get a small extruded
hexagon (20 m radius, 25 m tall, coloured by type) *on top of* their
existing flat circle from z14 - additive, not a replacement, so this can
never regress the always-visible circle every other asset type still relies
on. Built from `twin_infrastructure` points, not vector-tile building
footprints - OpenFreeMap's `building` class tags are not reliable enough
across Indian OSM coverage to filter on, where this app's own criticality
data already is. Verified with Node: correctly includes hospital/school,
correctly excludes a non-critical asset type.

### 2.4 Flag walls, CAP alert walls, camera cone extrusion

- **Flag walls** (`flag-wall`): every pending or approved flag gets a
  glowing extruded ring, radius from `dispatch.flag_footprint()` (the exact
  same circle a real dispatch would alert around, via a new
  `GET /{city}/flags/areas` endpoint - the map's footprint and dispatch's
  footprint can never disagree, because they're the same function) plus 15 m
  buffer, extruded 60 m, coloured by severity. **Pulses**: opacity cycles
  0.35-0.6 on a 2s sine wave, throttled to ~10 fps via `requestAnimationFrame`,
  paused outright when the tab is hidden (Page Visibility API). This is the
  one 3D-map layer that did not exist as a flat 2D layer before this work at
  all (`max.md` assumed `flag-areas`/`flag-glow` already existed in
  production; they did not - flags had a review-queue UI but no map
  visualisation whatsoever until now).
- **CAP alert walls** (`alert-wall`): a low 30 m amber wall on every official
  alert polygon, static (not pulsing) - deliberately a different visual
  grammar from a flag's glow, so an official warning always reads as itself.
  Reuses the alert polygon data the existing flat `alert-areas` layer already
  has; no new backend endpoint needed.
- **Camera cone 3D** (`cctv-cone-3d`): the existing flat cone gets a 6 m
  extrusion from z16. `max.md` asks to exclude cameras with only an
  "inferred" direction - checked, and there is no such case in this
  pipeline: `viewCone()` already returns `null` (no cone drawn at all) for
  any camera without a tagged `direction`, so every cone that exists already
  has a real bearing behind it.

All three verified: layer specs are valid MapLibre style JSON (checked with
Node), the new `/flags/areas` endpoint returns the correct shape against the
one real flag in the live database, and `_verifyLayers()`'s lazy-layer
exclusion list was checked again (these three are all added unconditionally
at init, so - unlike hillshade - they needed no addition to that list).

### 2.5 Light, atmosphere, 2D/3D toggle, camera

Directional light applied once per style load; `setSky(...)` guarded behind
`typeof map.setSky === "function"` rather than assumed, since this console
stays pinned to MapLibre 4.7.1 on purpose. One new header button
(`data-twin-3d`, styled with the existing `.twin-btn` class, not the
prototype's `twin-icon-btn` which doesn't exist here): flattening eases
pitch to 0 and turns terrain off; restoring 3D eases back and **restores
terrain only if it was on before the last flatten** - a true round trip.
Per-city defaults pushed into the live database via `seed.seed_cities()`
(idempotent): Hyderabad 55 deg pitch / -20 deg bearing toward Hussain Sagar,
Bengaluru 55 / -12.5.

### 2.6 Performance guard

Two independent valves, neither touching the operator's own checkbox state:
`IntersectionObserver` pauses terrain when the compact card scrolls out of
view and resumes it on return with no re-fetch; an fps sampler switches
terrain off (and unchecks the box, with a `notice()` explaining why) after 3
consecutive seconds below 30 fps.

### 2.7 Dashboard's own flood maps (15.9)

The two inline MapLibre instances in `analyst_dashboard.html`
(`initFloodMap`/`initFloodMapBengaluru`) each gained the same two-source
terrain + hillshade treatment (exaggeration 1.4, gentler than the console's
1.6 since these sit at a lower pitch), inserted below the existing
`labels-layer` so place names stay legible. Default and preset-camera pitch
raised 30 -> 45. Rivers/gauge layers, legends and stats overlays untouched.

**`GodModeMap`** (`god-mode-maps.js`, the heatmap/warning maps) gained
`enableTerrain()`/`disableTerrain()` methods but **neither is called
anywhere** - `max.md` itself frames this as "an option, off by default...
those maps are about density, and relief can distract," so the method exists
(reviewed-by-reading, real code) without being wired to any default-on
behaviour or new UI control, matching that explicit low-priority framing.

**Building extrusions were not added to any of these four maps.** The
console's `buildings-3d` layer depends on the OpenFreeMap Liberty *vector*
style; all four of these maps use a raw raster-only style (Esri imagery +
labels, or a Carto raster/vector hybrid for GodModeMap) with no
`openmaptiles` building source. Adding one would mean introducing a second
tile source and a real chance of visual clutter on maps that are
specifically about flood monitoring or incident density, not building
massing - judged not worth the added scope for these four instances, unlike
the console where the vector style and building source already existed.

---

## 3. Honest gaps, final

Against `max.md` §14.4's checklist:

- [x] Both agents run on schedule and on demand, `rules` and `llm` modes,
      deduplicated flags with briefs/evidence/citations. Citations appear
      once files are placed in `data/twin/corpus/` (verified with a real
      test file).
- [x] The flag panel shows the queue; an analyst can approve/dismiss AND now
      preview/dispatch, in-app + WhatsApp when Twilio is configured, audited.
- [x] CAP alerts, stations, transit (when configured), the anomaly sigma all
      feed scores or appear as layers/drawer sections. Stations/transit
      specifically: code-complete, unverified against live data (no keys).
- [x] The base twin's quiet-day behaviour, layout and scores are unchanged -
      verified by direct before/after comparison, not just assertion.
- [ ] "The ported tests pass" - no prior pytest suite exists in this repo to
      port; verification here was direct script-based testing against real
      and synthetic data instead, documented inline above.

Against `max.md` §15.10's checklist: every item is now checked, including
the two ("Critical-building extrusions", "3D water, flag walls, CAP walls,
3D camera cones") the previous version of this document listed as not built.
3D water specifically was **deliberately not added as a separate extrusion
layer** - with terrain enabled, the existing flat `water-bodies` fill layer
already drapes onto the terrain surface and sits visibly in the depression
Hyderabad's lakes and Bengaluru's valleys carve, at zero risk of
reintroducing the "zero-height extrusion renders near-black" bug this
codebase already fixed once for the risk hexes. Building a real extrusion on
top would have reintroduced exactly that class of bug for no visible gain.

**The one thing that cannot be verified from here, still**: whether any of
this actually *looks* right. Every change was checked for MapLibre 4.7.1
style-spec validity, ran through Node-based functional tests of the pure
JS helpers, and exercised through the full Flask app (boot + all new routes
+ real agent cycles) - but there is no browser in this environment to render
a WebGL canvas and judge terrain exaggeration, colour balance, whether the
flag pulse reads as intended, or whether 30 fps is the right cutoff on real
hardware. Open `/digital-twin` and `/analyst_dashboard`, turn Terrain and
Flag areas on, and look.

---

## 4. Real API keys, added after the above was written

Five keys were added to `.env` after Sections 1-3 were built and verified
keyless: `OPENAQ_API_KEY`, `AQICN_TOKEN`, `MAPILLARY_TOKEN`, `TOMTOM_API_KEY`,
`WINDY_WEBCAMS_KEY` (`DATA_GOV_IN_KEY`/CPCB and a GTFS-RT URL were not - both
remain untested for the reasons already stated in §1.5). Testing against
real data immediately surfaced two real bugs the keyless path could never
have caught, and confirmed one documented claim in `max.md` was accurate:

- **OpenAQ: fixed a real bug.** `/v3/locations/{id}/latest` returns a value
  and a `sensorsId`, but *never* the pollutant name - that only exists on
  the location's own `sensors` list. The original code assumed `/latest`
  carried a `parameter` field and silently matched nothing, every time. Fixed
  by resolving the pm25 sensor's id from the location first, then matching
  `/latest` rows by that id - and picking the *freshest* matching row, since
  a single station can carry both a live sensor and one that stopped
  reporting years ago under different sensor ids. Verified against 14 real
  Hyderabad stations and 22 Bengaluru ones.
- **AQICN: fixed a real bug.** OpenAQ timestamps end in `Z` (UTC); AQICN's
  do not - they carry a real offset (`...+05:30`). The original
  `_parse_time()` stripped whatever timezone was present without converting
  first, which for an IST timestamp silently kept the wrong wall-clock
  number and called it UTC - a 5.5-hour error that would have shown every
  Indian station's reading as more recent than it actually was. Fixed with a
  proper `astimezone(timezone.utc)` conversion before dropping tzinfo.
- **Mapillary: `max.md`'s claim confirmed, and its recommended fix built.**
  The Graph API bbox search genuinely returns `{"data": []}` for Hyderabad
  at every radius tried, from 500 m up to the endpoint's own maximum allowed
  area - confirmed directly with a real token, matching what `max.md` reports
  for Bengaluru. `twin/ingest/mapillary_tiles.py` is a new, hand-rolled
  Mapbox Vector Tile (protobuf) decoder - no new dependency - that reads the
  same tiles Mapillary's own web app does. **Found and fixed a bug in this
  new code during the same testing pass**: the decoder was being handed the
  whole tile's bytes instead of first unwrapping the one named `Layer`
  submessage from the top-level `Tile` message, so it silently decoded
  nothing. Fixed with a `_find_layer()` step; verified against a real tile
  to correctly find all 1,659 encoded features and decode 40 real images
  with accurate lat/lon (checked against the tile's own computed bounds),
  heading and capture date. Wired into `streetview.py::_mapillary()` as a
  fallback that only fires when the bbox search returns nothing.

  **One thing this key alone could not fix**: an image's thumbnail needs one
  further Graph-by-id call (`GET /{image_id}?fields=thumb_1024_url`) - tiles
  carry geometry and tags, never a signed thumbnail URL. That call fails for
  every id the tile decoder finds, with `"does not exist, cannot be loaded
  due to missing permissions, or does not support this operation"` -
  reproduced with and without a `fields` param, so this reads as a token
  scope issue (`max.md` itself notes Mapillary "needs Graph read scope"),
  not a bug in the id or the request shape. Rather than guess further,
  `fetch_tile_images()` simply omits any image with no confirmed thumbnail -
  geometry discovery is correct and will start showing images in the drawer
  automatically the moment that permission is granted, with no code change.
- **Windy Webcams and TomTom: worked immediately**, no code changes needed.
  Verified with real calls: 2 live Hyderabad webcams with current
  `captured_at` timestamps; a real 22.8 KB traffic-flow PNG tile.

**Real data was then written to the live database** (a legitimate action,
not a test artifact - this is exactly what the scheduled `twin_ingest_stations`
job does): 15 Hyderabad + 22 Bengaluru air-quality stations, via
`live.poll_stations()`. A recompute afterward confirmed the scoring
integration for real: 761 of 1,838 cell-states now carry a real station AQI
in `raw_inputs`, because Bengaluru currently has one non-stale reading within
range; Hyderabad currently has zero non-stale readings (its government
stations' freshest value was ~39 hours old, past the 120-minute cutoff) and
every Hyderabad cell correctly fell back to the Open-Meteo estimate instead -
the honest result of real reporting cadence, not a bug.

---

## 5. A transparency note on test isolation

While verifying the dispatch flow, `config.py`'s `load_dotenv(override=True)`
was found to silently defeat `DATABASE_URL` shell overrides - every "isolated"
test earlier in this session's history actually hit the live database. Found,
disclosed, and fixed: the working pattern is
`dotenv.load_dotenv = lambda *a, **k: None` set *before* `import app`, which
was used for every test from that point on, verified with a probe write that
landed only in a `/tmp` copy. Left one real consequence in place rather than
hiding it: a real `twin_dispatch` audit row and a real WhatsApp message this
caused during development remain in the live database as an honest record,
not deleted.
