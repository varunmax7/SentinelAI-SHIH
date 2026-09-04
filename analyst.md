# Sentinel AI — Hyderabad & Bengaluru Urban Digital Twin

**Implementation, integration and defect-remediation guide.**

> This document is written for the engineer or agent who will take the Digital Twin
> from its current prototype state to a properly integrated feature inside the
> Sentinel AI admin and analyst panels. It describes what already exists, what is
> broken, *why* it is broken, and exactly what to do about it.
>
> **Nothing in Part III is implemented yet. Do not assume any of it is done.**

---

## 0. How to read this document

| Part | Contents | Read it when |
|---|---|---|
| **I** | The system as built — stack, files, data model, API, layer stack | Before touching anything |
| **II** | Integrating the two city maps into the admin & analyst panels | You are wiring the panels |
| **III** | **Defect register** — 7 known issues, root causes, fixes, acceptance criteria | This is the actual work queue |
| **IV** | Reference — env vars, commands, licensing, MapLibre gotchas | While implementing |

Every defect in Part III has a **Symptom → Root cause → Fix → Acceptance** block.
Do not skip the root-cause paragraph: several of these have a non-obvious cause and
the obvious fix makes them worse.

---

# PART I — The system as built

## 1. Stack

### Backend

| Concern | Technology | Notes |
|---|---|---|
| Web framework | **Flask** | Twin registers as two blueprints; the host app's 119 routes are untouched |
| ORM | **Flask-SQLAlchemy** | Twin models are built by a factory so they attach to the host's `db` |
| Migrations | **Alembic / Flask-Migrate** | `migrations/versions/20260903_01_twin_initial.py` |
| Database | **SQLite** (dev) / PostgreSQL-ready | `instance/site.db`; app uses `create_all()`, not `flask db upgrade` |
| Spatial index | **H3 v4** (`h3>=4.1.0`) | Resolution 8 for the grid (~460 m across), resolution 9 for drill-down |
| Geometry | **Shapely 2.x** | Polygon clipping, cell/zone assignment |
| Scheduling | **APScheduler** | Shares the host app's existing `BackgroundScheduler` |
| HTTP client | **requests** | All ingest goes through one `IngestAdapter` base class |
| Auth | **Flask-Login** (host's) | Twin resolves the host decorator at registration time; falls back to its own |
| Realtime | **Server-Sent Events** | `text/event-stream`, with polling fallback |

### Frontend

| Concern | Technology | Notes |
|---|---|---|
| Map engine | **MapLibre GL JS 4.7.1** | **Pinned.** See §II.1 — version drift is an active hazard |
| Vector basemap | **OpenFreeMap "Liberty"** | `https://tiles.openfreemap.org/styles/liberty` — free, keyless, provides the `openmaptiles` source that 3D buildings need |
| Satellite imagery | **Esri World Imagery** | Same endpoint the existing flood widgets use |
| Place labels | **Esri World Boundaries and Places** | Raster reference layer over the imagery |
| Historical imagery | **NASA GIBS** (VIIRS/MODIS) | Date-picker; native resolution tops out ≈ zoom 9 |
| Rain radar | **RainViewer** | Keyless, manifest-driven frame lookup |
| Geocoding | **Nominatim** | Keyless, rate-limited, 400 ms debounce required |
| UI framework | **Bootstrap 5** (host's) | Twin CSS is scoped under `.twin-console` |
| Build step | **None** | Everything is CDN + plain ES2018 in `static/js/`. Keep it that way |

### Data sources (ingest)

| Source | Tier | Key required | Used for |
|---|---|---|---|
| Open-Meteo Forecast | 1 | No | Rain now / forecast → `hydro_score` |
| Open-Meteo Air Quality | 1 | No | AQI → `env_score` |
| Open-Meteo Flood (GloFAS) | 1 | No | River discharge anomaly |
| RainViewer | 1 | No | Radar tiles |
| Overpass (OpenStreetMap) | 1 | No | Critical assets, water, drains, **CCTV cameras** |
| Internal reports | 1 | n/a | Verified citizen reports → `incident_score` |
| KartaView | 2 | No | Street-level imagery |
| Mapillary | 2 | `MAPILLARY_TOKEN` | Street-level imagery (denser in Indian wards) |
| Windy Webcams | 2 | `WINDY_WEBCAMS_KEY` | Live webcams |
| TomTom | 2 | `TOMTOM_API_KEY` | Traffic flow tiles |
| **CCTV OSINT** | 2 | **No** | Camera locations, bearings, operators |

**Tier 1** feeds a sub-score; if it fails the score degrades and the cell is
flagged. **Tier 2** is presentational; if it fails you lose one layer, never a 500.

---

## 2. File inventory

```
twin/                          # The module. Self-contained.
├── __init__.py                # create_twin_blueprint() — the single entry point
├── config.py                  # Cities, zones, weights, status bands, env knobs
├── models.py                  # 7 models, built by a factory bound to the host db
├── grid.py                    # H3 grid generation + polygon clipping
├── geo.py                     # Distance, bbox, geometry helpers
├── scoring.py                 # hazard × vulnerability → risk_score
├── engine.py                  # Orchestrates ingest → score → persist
├── jobs.py                    # APScheduler registrations
├── routes.py                  # 20 HTTP routes (2 blueprints)
├── serializers.py             # Model → GeoJSON / JSON, ETag + cache headers
├── security.py                # Role gates; adopts the host's decorators
├── seed.py                    # Idempotent metadata seeding
├── stream.py                  # SSE pub/sub
└── ingest/
    ├── base.py                # IngestAdapter — cache, retry, audit, never raises
    ├── open_meteo.py          # Forecast + air quality + flood
    ├── overpass.py            # Assets, water bodies, drains
    ├── cctv.py                # ★ OSINT surveillance cameras
    ├── rainviewer.py          # Radar manifest
    ├── nasa_gibs.py           # Historical imagery date probe
    ├── streetview.py          # KartaView / Mapillary / Windy
    ├── traffic.py             # TomTom tile URL
    ├── tgdps.py               # Telangana gauge stub
    └── internal_reports.py    # Host Report model bridge + approval hook

static/js/
├── twin-layers.js             # Layer specs + paint expressions (pure data)
├── digital-twin.js            # TwinMapBase / TwinMap / TwinPane
├── twin-console.js            # TwinConsole — the controller
└── twin-stream.js             # SSE client with polling fallback

static/css/twin.css            # All console styling, scoped under .twin-console

templates/
├── digital_twin.html          # Standalone /digital-twin page
└── partials/twin_console.html # ★ The embeddable console — include this

scripts/
├── seed_twin.py               # Build the H3 grid and zones
├── fetch_boundaries.py        # Pull admin polygons from Overpass
└── import_twin_grid.py        # Import a prebuilt grid

data/twin/
├── boundaries/                # City clip polygons (GeoJSON)
└── cache/                     # Ingest disk cache (TTL per source)

tests/twin/                    # 232 tests
```

---

## 3. Data model

| Model | Purpose | Key fields |
|---|---|---|
| `TwinCity` | One city | `slug`, `bbox_min_lon/lat`, `bbox_max_lon/lat`, `default_zoom/pitch/bearing`, `h3_resolution` |
| `TwinZone` | Administrative ward/zone | `slug`, `center_latitude/longitude`, `boundary_geojson`, `boundary_source` |
| `TwinCell` | One H3 hexagon | `h3_index` (unique), `city_id`, `zone_id`, `boundary_geojson`, `elevation_m`, `dist_to_water_m`, `drain_length_m` |
| `TwinCellState` | Risk at one horizon | `cell_id`, `horizon_hours` (0/3/6/24), `risk_score`, `status`, 5 sub-scores, `raw_inputs` |
| `TwinCellHistory` | Time series | For back-testing and the timeline chart |
| `TwinInfrastructure` | Critical assets | `asset_type`, `criticality`, `cell_id` |
| `TwinDataSnapshot` | Ingest audit row | `source_key`, `status`, `latency_ms`, `records_ingested`, `error_message` |

**Cardinality today:** Hyderabad ≈ 940 cells, Bengaluru ≈ 942 cells, × 4 horizons.

**Known data gap you will hit:** only ~11 of 942 Bengaluru cells have a `zone_id`,
and every seeded zone is `boundary_source='approximate'` (a centre point, no
polygon). Anything that filters by zone must degrade gracefully — see
`twin/routes.py::_zone_bounds` for the pattern to copy.

---

## 4. HTTP API

All routes require authentication. Most require role `official`, `analyst` or
`admin`; `/refresh` and `/seed` require `official` or `admin`.

| Method | Route | Returns |
|---|---|---|
| GET | `/digital-twin` | The standalone page |
| GET | `/api/twin/cities` | City list + zones + camera/bbox metadata |
| GET | `/api/twin/<city>/zones` | Zone polygons |
| GET | `/api/twin/<city>/state` | **Risk hexagons as GeoJSON** (`?zone=&horizon=&geometry=true`) |
| GET | `/api/twin/<city>/cell/<h3>` | One cell: sub-scores, assets, reports, explanation, centre |
| GET | `/api/twin/<city>/summary` | Avg/max risk, cells by status, incident count |
| GET | `/api/twin/<city>/incidents` | Verified reports as points |
| GET | `/api/twin/<city>/infrastructure` | Critical assets as points |
| GET | `/api/twin/<city>/cameras` | **OSINT cameras as GeoJSON** |
| GET | `/api/twin/<city>/water` | **Water bodies + drains as GeoJSON** |
| GET | `/api/twin/<city>/timeline` | Risk history buckets |
| GET | `/api/twin/cctv` | Cameras near a point (`?lat=&lon=&radius=`) |
| GET | `/api/twin/streetview` | Street-level imagery near a point |
| GET | `/api/twin/compare` | Both cities side by side |
| GET | `/api/twin/health` | Per-source status for the health pill |
| GET | `/api/twin/gibs` | NASA GIBS tile template + date resolution |
| GET | `/api/twin/traffic` | TomTom availability + tile template |
| GET | `/api/twin/stream` | **SSE** — state updates and new incidents |
| POST | `/api/twin/refresh` | Recompute city state now |
| POST | `/api/twin/seed` | Build/repair the grid |

Responses over 8 KB are gzipped by an `after_request` scoped to the twin
blueprint only (`twin/routes.py::_gzip_large_json`). The SSE route is excluded.

**Live payload sizes** (gzipped / raw):

| Endpoint | Bengaluru | Hyderabad |
|---|---|---|
| `/water` | 339 KB / 1.68 MB | ~160 KB / 705 KB |
| `/cameras` | 61 KB / 765 KB | ~4 KB / 11 KB |

---

## 5. Scoring pipeline

```
risk_score = hazard × vulnerability          (0–100, clamped)

hazard        = 0.55·hydro + 0.30·incident + 0.15·env
vulnerability = 1 + 0.60 · (0.60·terrain + 0.40·infra) / 100     → spans 1.0 … 1.6

hydro    = f(rain_now, rain_forecast, discharge)   weights vary by horizon
incident = Σ severity · confidence · exp(-Δt/12h), + 0.40 × k-ring-1 neighbours
terrain  = 0.45·low_lying + 0.35·water_proximity + 0.20·drain_gap
infra    = min(100, Σ asset_criticality × 12)
env      = 0.60·AQI + 0.40·heat
```

Hazard and vulnerability **multiply** rather than sum. This is deliberate: a flat
weighted sum leaves every low-lying, hospital-dense cell permanently in `watch`
with zero rain and zero incidents.

**Status bands:** `normal` 0–24 · `watch` 25–49 · `warning` 50–74 · `critical` 75–100.

Compute runs every 5 minutes for all four horizons. Any cell whose inputs came
from a degraded source carries `degraded_inputs` and is drawn with a dashed amber
outline — officials must be able to see when the twin is guessing.

---

## 6. Map layer stack

Bottom to top. **MapLibre has no z-index** — order is fixed by the `beforeId`
argument to `addLayer`. `digital-twin.js::RASTER_BEFORE` encodes this.

```
  OpenFreeMap Liberty vector style        ← always the base, NEVER swapped
  satellite            (Esri imagery)     ← raster, default ON
  satellite-labels     (Esri places)      ← raster, always paired with satellite
  buildings-3d         (fill-extrusion)   ← needs the `openmaptiles` source, minzoom 13
  water-bodies         (fill)             ┐
  water-bodies-outline (line)             │ lazy: /water
  water-drains-glow    (line)             │
  water-drains         (line)             ┘
  radar / traffic      (raster)           ← weather & traffic sit above buildings
  twin-hexes           (fill-extrusion)   ← THE risk grid
  twin-hex-outline     (line, ≥25 only)
  twin-hexes-degraded  (line, dashed)
  zone-outline         (line)
  infrastructure       (circle)
  cctv                 (circle)           ┐ lazy: /cameras
  cctv-direction       (symbol, ≥z14)     ┘
  incidents            (circle)
  incident-labels      (symbol, ≥z12)
```

**Hard rule:** never call `map.setStyle()`. It destroys every source and layer
added above, and they must all be re-added. Basemap changes are done by
adding/removing *raster layers* on top of the permanent vector style.

---

# PART II — Integrating the maps into the admin & analyst panels

The console is a **single self-contained partial**. A host page passes no template
variables — the city list, zones and camera config all come from
`GET /api/twin/cities` at runtime.

## 1. Load MapLibre exactly once, in `<head>`, pinned

This is the single most important integration rule.

```html
{% block head_extra %}
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
{% endblock %}
```

**Why:** if a page loads MapLibre a second time — or a different version — the
second copy replaces `window.maplibregl` mid-page, and every map already built
from the first copy is silently detached. Symptoms are bizarre: zoom stops
working, layers stop updating, no console error. This exact bug existed on the
analyst dashboard (page loaded 3.6.2 at the end of `<body>`, twin loaded 4.x in
the middle).

The partial contains a guard that injects MapLibre **only if absent** and exposes
`window.TwinMapLibreReady` as a promise. If the host page loads it in `<head>`,
the guard does nothing. Keep both mechanisms.

## 2. Include the partial

```jinja
<div class="card mb-5 overflow-hidden twin-host-card">
  <div class="card-header py-3 bg-transparent d-flex justify-content-between align-items-center">
    <h6 class="m-0 fw-bold text-white">🌐 Urban Digital Twin</h6>
    <a href="{{ url_for('twin_pages.digital_twin_page') }}" class="btn btn-sm btn-outline-light">
      Full screen
    </a>
  </div>
  <div class="card-body p-0">
    {% set twin_variant = 'compact' %}
    {% include "partials/twin_console.html" %}
  </div>
</div>
```

Variants: `compact` (58 vh — dashboard cards), `embedded` (74 vh — dedicated
sections), `page` (full viewport — the standalone route).

## 3. Opt the host card out of hover transforms — **mandatory**

```css
.card.twin-host-card:hover,
.glass-card.twin-host-card:hover {
    transform: none;
}
```

**Why:** `base.html` line ~199 defines a global `.glass-card:hover { transform:
translateY(-4px) }`, and `coordination_dashboard.html` line 42 defines
`.card:hover { transform: translateY(-3px) }`. A CSS `transform` on **any**
ancestor of a MapLibre canvas:

1. drags the live canvas on every mouse-over, and
2. creates a new containing block, which **breaks MapLibre's pointer→map
   coordinate maths** — clicks and scroll-zoom land in the wrong place, or stop
   registering.

This is one of the causes of "zoom is not supported in some views" (see D3).

## 4. Role gating

`twin/security.py` currently admits `official`, `analyst`, `admin`. If you add
`coordinator` (the host's coordination APIs already accept it), add it to
`TWIN_ROLES`, not to individual routes.

Nav entries live in `base.html`: the Tools dropdown (official/analyst), the user
dropdown, and a standalone item for `admin` — because every other entry in the
Tools dropdown redirects an admin away.

## 5. Seed before you expect anything to render

```bash
python scripts/seed_twin.py                # builds the H3 grid + zones
curl -X POST localhost:5001/api/twin/refresh -d '{"city":"all"}' \
     -H 'Content-Type: application/json'   # first compute
```

Without a grid, every pane boots to "No twin cities are configured yet."

---

# PART III — Defect register

**This is the work queue.** Seven defects, in the order I would fix them.

---

## D1 — Selected/highlighted areas are filled colour blocks

> *"the highlights for the selected areas is in colored region so that also change
> it — where the highlighted area is just in the borders like a line instead of
> selecting the whole area"*

### Symptom
Clicking a hexagon (or hovering it) highlights it as a solid tinted region. The
operator loses the imagery underneath exactly where they are looking, and on a
dense grid it is hard to tell which cell is actually selected.

### Root cause
Two separate things are being conflated:

1. **There is no selection layer at all.** `digital-twin.js` fires `_onHexClick`
   and opens the drawer, but never marks the clicked cell on the map. What reads
   as "the highlight" is just the risk *fill* of that band.
2. **The risk fill is the only visual channel in use.** `twin-hexes` is a
   `fill-extrusion` with a per-band `rgba()` colour, so every cell is a filled
   block whether selected or not.

### Fix

**Step 1 — make the source support per-feature state.** GeoJSON sources need
`promoteId` before `setFeatureState` can address features by a string key:

```js
// digital-twin.js :: initTwinSources()
this.addSourceSafe("twin-hexes-src", {
  type: "geojson",
  data: this._emptyFC,
  promoteId: "h3",        // ← REQUIRED. h3_index is stable across setData().
});
```

**Step 2 — add outline-only hover and selection layers.** Two `line` layers above
`twin-hexes`, driven entirely by feature-state, drawing *nothing* when neither
state is set:

```js
// twin-layers.js
function twinHexInteractionLayer(sourceId) {
  return {
    id: "twin-hex-interaction",
    type: "line",
    source: sourceId,
    layout: { "line-join": "round", "line-cap": "round" },
    paint: {
      "line-color": [
        "case",
          ["boolean", ["feature-state", "selected"], false], "#38d9ff",
          ["boolean", ["feature-state", "hover"],    false], "#a5f3fc",
          "rgba(0,0,0,0)",
      ],
      "line-width": [
        "case",
          ["boolean", ["feature-state", "selected"], false], 2.5,
          ["boolean", ["feature-state", "hover"],    false], 1.5,
          0,
      ],
      "line-opacity": 0.95,
    },
  };
}

// A soft glow beneath it, so the outline reads over bright satellite imagery.
function twinHexInteractionGlowLayer(sourceId) {
  return {
    id: "twin-hex-interaction-glow",
    type: "line",
    source: sourceId,
    paint: {
      "line-color": "#38d9ff",
      "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 9, 0],
      "line-blur": 6,
      "line-opacity": 0.4,
    },
  };
}
```

**Step 3 — drive the state.** Track the previous id and clear it; never leave a
stale `selected`:

```js
// digital-twin.js :: TwinMap
_setHexState(h3, state) {
  if (h3 == null) return;
  this.map.setFeatureState({ source: "twin-hexes-src", id: h3 }, state);
}

selectHex(h3) {
  if (this._selectedH3 === h3) return;
  if (this._selectedH3) this._setHexState(this._selectedH3, { selected: false });
  this._selectedH3 = h3;
  this._setHexState(h3, { selected: true });
}

clearSelection() {
  if (this._selectedH3) this._setHexState(this._selectedH3, { selected: false });
  this._selectedH3 = null;
}
```

Call `selectHex(props.h3)` in the `click` handler and `clearSelection()` when the
drawer closes. Do the same pair for `hover` in `mousemove` / `mouseleave`.

**Step 4 — reduce the fill's role.** With a real selection outline in place, the
fill no longer has to carry "which one is selected". Combine with **D2**.

### Gotcha
`setFeatureState` silently no-ops if the feature is not currently loaded in a
tile, and state is **lost on `setData()`** unless `promoteId` yields stable ids.
`h3_index` is stable — but re-apply the selected state after every `fetchState()`
refresh, or a live SSE update will visually clear the operator's selection.

### Acceptance
- [ ] Clicking a hex draws a cyan outline on that hex only; the fill does not change.
- [ ] Hovering draws a thinner, paler outline.
- [ ] Selection survives an SSE state update and a horizon change.
- [ ] Closing the drawer clears the outline.
- [ ] Only one cell is ever outlined as selected, per pane.

---

## D2 — Risk overlay is too opaque; it blocks the map

> *"the highlighted areas also should not be so blocked opaque"*

### Symptom
The risk grid paints over the city. Satellite imagery, roads and buildings are
invisible under the hexagons — the operator cannot see the ground truth the
imagery was added to provide.

### Root cause
Band opacities in `twin-layers.js::STATUS_BANDS` were tuned against a flat dark
vector basemap, then the default basemap changed to satellite imagery. Current
values are already reduced (0.14 / 0.30 / 0.42 / 0.55) but are still a solid fill
across ~940 cells per city.

A second contributor: `fill-extrusion-opacity` **does not accept data-driven
expressions** in MapLibre (it throws `data expressions not supported` and the
whole layer fails to add). Per-band opacity therefore has to be baked into the
`rgba()` colour, which makes it easy to forget it is there.

### Fix

Give the operator a **fill-density control** rather than picking one compromise:

```js
// Three modes, exposed as a segmented control in the pane header:
//   "solid"    – current behaviour, for projection onto a wall
//   "balanced" – default: fill only ≥ watch, outlines for everything
//   "outline"  – no fill at all; outlines + extrusion height only
const FILL_MODES = {
  solid:    { normal: 0.14, watch: 0.30, warning: 0.42, critical: 0.55 },
  balanced: { normal: 0.00, watch: 0.16, warning: 0.24, critical: 0.34 },
  outline:  { normal: 0.00, watch: 0.00, warning: 0.06, critical: 0.10 },
};
```

Apply with `map.setPaintProperty("twin-hexes", "fill-extrusion-color", expr)`,
rebuilding the `step` expression from the chosen table. Persist the choice in
`localStorage` so it survives a page reload.

Additionally:

- **Keep `twin-hex-outline` filtered to `risk_score >= 25`.** On an ordinary day
  most of a city sits in `normal`; outlining all of them draws ~900 hairlines and
  is what makes the console read as a honeycomb rather than a city.
- **Do not** hide low-risk cells entirely by default. On a calm day that leaves an
  operator staring at an empty map wondering whether the twin is running. A faint
  wash that says "measured, and fine" is the correct default; keep the
  "Low-risk cells" toggle for those who want only actionable cells.
- Set `"fill-extrusion-vertical-gradient": true` (already set) — it darkens the
  base of each column and is what separates adjacent cells at an oblique angle.

### Acceptance
- [ ] At default settings, road geometry and building footprints are legible under `normal` and `watch` cells.
- [ ] `critical` cells remain unmistakable at a glance from a full-city view.
- [ ] The fill-density control persists across reload.
- [ ] No `data expressions not supported` error in the console.

---

## D3 — Zoom does not work in some views

> *"zoom is not supported for some views"*

### Symptom
Scroll-zoom, the +/− buttons, or pinch-zoom do nothing — or work on one pane and
not the other, or work on `/digital-twin` but not inside a dashboard card.

### Root cause
There are **five** distinct causes here. Diagnose before fixing; they need
different remedies.

1. **A CSS `transform` on an ancestor.** `base.html` has a global
   `.glass-card:hover { transform: translateY(-4px) }` and
   `coordination_dashboard.html` has `.card:hover { transform: translateY(-3px) }`.
   A transformed ancestor creates a new containing block and breaks MapLibre's
   pointer→map coordinate conversion. This is the most common cause inside
   dashboard cards. **Fix:** the `.twin-host-card` opt-out in §II.3 — apply it on
   *every* host page, not just the two that currently have it.

2. **Two MapLibre copies on the page.** See §II.1. The map object you are
   clicking belongs to a different library instance than the one handling events.
   **Fix:** load once, in `<head>`, pinned.

3. **A zero-height or hidden container at construction time.** A map built inside
   a `display:none` Bootstrap tab or a zero-height card never computes its
   transform and behaves as if input is dead. **Fix:** the `ResizeObserver` →
   `map.resize()` hook already exists in `twin-console.js::observeResize()`;
   make sure the console is not inside a collapsed accordion at boot.

4. **Raster source `maxzoom` mistaken for a zoom limit.** NASA GIBS imagery is
   native to ≈ zoom 9. `source.maxzoom` makes MapLibre over-zoom the last valid
   tile rather than request tiles that do not exist — the map *is* zooming, the
   imagery just stops sharpening. **Fix:** this is correct behaviour; surface it.
   Show a "imagery native to z9 — over-zoomed" note when the GIBS basemap is
   active above z9, so it does not read as a broken control.

5. **Touch: pinch-zoom swallowed.** Bootstrap sets `touch-action: manipulation`
   on interactive elements; MapLibre needs `touch-action: none` on its canvas
   container for `touchZoomRotate` to receive events. **Fix:**

   ```css
   .twin-console .maplibregl-canvas-container,
   .twin-console .maplibregl-canvas {
       touch-action: none;
   }
   ```

### Also do
Add an explicit zoom range and a "reset view" control so the operator always has
a way back:

```js
new maplibregl.Map({
  minZoom: 8,
  maxZoom: 18,
  maxPitch: 70,
  // …
});
```

### Acceptance
- [ ] Scroll-, button- and pinch-zoom all work on **both** panes, on all four host pages.
- [ ] Zoom still works after hovering the host card.
- [ ] Zoom works after switching Bootstrap tabs, if the console is ever placed in one.
- [ ] `window.maplibregl.version` logs the same value before and after the twin partial.

---

## D4 — Scrolling is not smooth

> *"make it nice smooth scrolling"*

### Symptom
Scrolling the dashboard past the twin gets stuck: the wheel zooms the map instead
of moving the page. Elsewhere the page stutters.

### Root cause
1. **MapLibre captures the wheel by default.** Any embedded map on a scrolling
   page traps the pointer. This is the primary cause and it is not a performance
   problem at all.
2. **`backdrop-filter: blur()` on large elements.** `twin.css` uses it on the
   drawer, the layer panel and the pane footer; `base.html` and the dashboards use
   it on every card. Each blurred layer forces an expensive off-screen composite
   on every frame, and there are two live WebGL canvases behind them.
3. **`ResizeObserver` → `map.resize()` with no debounce.** Resize fires
   continuously during a window drag, and each `resize()` triggers a full repaint
   of both maps.
4. **Two WebGL contexts that never stop.** Browsers cap around 16 contexts per
   page; the analyst dashboard already has two MapLibre maps of its own plus the
   twin's two.

### Fix

**1. Cooperative gestures — the important one.**

```js
new maplibregl.Map({
  // …
  cooperativeGestures: true,
});
```

Wheel then scrolls the *page*; **Ctrl/⌘ + wheel** zooms the map, and MapLibre
shows its own hint overlay. Enable this for the `compact` and `embedded` variants
and **disable it for the `page` variant**, where the map owns the viewport:

```js
const cooperative = root.dataset.variant !== "page";
```

**2. Trim `backdrop-filter`.** Keep it on the drawer (small, transient); drop it
from `.twin-pane-footer`, `.twin-layer-panel` and `.twin-header` and use an
opaque background instead. Visually near-identical, materially cheaper.

**3. Debounce the resize observer.**

```js
observeResize() {
  let frame = null;
  const observer = new ResizeObserver(() => {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => this.resizeMaps());
  });
  observer.observe(this.root);
}
```

**4. Contain the console and give the page smooth scroll.**

```css
html { scroll-behavior: smooth; }

.twin-console {
    overscroll-behavior: contain;   /* stop scroll-chaining out of the drawer */
    contain: paint;                 /* isolate repaints from the rest of the page */
}
```

**5. Only build the second pane's map when it is visible.** On narrow screens the
panes stack; the second is off-screen at boot. Defer its `new TwinMap(...)` to its
own `IntersectionObserver` rather than constructing both up front.

### Acceptance
- [ ] Wheel over the map scrolls the page in `compact`/`embedded`; Ctrl+wheel zooms.
- [ ] Wheel zooms directly on `/digital-twin`.
- [ ] No frame drops below 50 fps scrolling the analyst dashboard top to bottom (DevTools Performance).
- [ ] Dragging the window edge does not lock the UI.

---

## D5 — CCTV cameras are dots, not views

> *"properly integrate the cctv views for openstreetmaps so that we can see"*

### Symptom
The CCTV layer shows *where* cameras are. It does not show what they look at, and
clicking one gives metadata and a link rather than an image.

### Root cause
`twin/ingest/cctv.py` is correct and complete as an **OSINT locator** — it returns
`lat`, `lon`, `kind`, `camera_type`, `mount`, `direction`, `operator`, `zone`,
`stream_url`, `osm_url` — but nothing consumes `direction` beyond a rotated
arrowhead glyph, and there is no imagery pipeline attached to a camera.

Also understand the ceiling: **OpenStreetMap does not host camera feeds.** Only a
small minority of camera nodes carry `contact:webcam`. "Seeing what a camera sees"
has to be synthesised from other open sources.

### Fix — four layers of increasing usefulness

**5.1 — View cones (do this first; it is the biggest win).**

Render each camera's field of view as a wedge polygon. This is what actually makes
surveillance coverage *visible* on a map.

```js
// Forward geodesic point. Good to well under a metre at these ranges.
function destination(lat, lon, bearingDeg, distanceM) {
  const R = 6371000, d = distanceM / R;
  const br = bearingDeg * Math.PI / 180;
  const p1 = lat * Math.PI / 180, l1 = lon * Math.PI / 180;
  const p2 = Math.asin(Math.sin(p1) * Math.cos(d) + Math.cos(p1) * Math.sin(d) * Math.cos(br));
  const l2 = l1 + Math.atan2(Math.sin(br) * Math.sin(d) * Math.cos(p1),
                             Math.cos(d) - Math.sin(p1) * Math.sin(p2));
  return [l2 * 180 / Math.PI, p2 * 180 / Math.PI];
}

// FOV and range defaults by camera type. OSM rarely tags either, so these are
// declared assumptions — label them as such in the legend, do not imply survey.
const CAMERA_OPTICS = {
  fixed:   { fov: 60,  range: 45 },
  panning: { fov: 180, range: 60 },   // a PTZ sweeps; show its whole envelope
  dome:    { fov: 360, range: 30 },
  default: { fov: 60,  range: 45 },
};

function viewCone(camera) {
  if (camera.direction == null) return null;             // no bearing → no cone
  const optics = CAMERA_OPTICS[camera.camera_type] || CAMERA_OPTICS.default;
  if (optics.fov >= 360) return null;                    // draw a circle instead
  const start = camera.direction - optics.fov / 2;
  const ring = [[camera.lon, camera.lat]];
  for (let i = 0; i <= 12; i++) {
    ring.push(destination(camera.lat, camera.lon, start + (optics.fov * i) / 12, optics.range));
  }
  ring.push([camera.lon, camera.lat]);
  return { type: "Feature", properties: { ...camera }, geometry: { type: "Polygon", coordinates: [ring] } };
}
```

Layer it as a low-opacity fill plus a 1 px edge, **`minzoom: 15`** — below that,
a few thousand cones is a solid smear:

```js
{
  id: "cctv-cone",
  type: "fill",
  source: "twin-cctv-cones-src",
  minzoom: 15,
  paint: { "fill-color": cctvColourExpression(), "fill-opacity": 0.18 },
}
```

Build the cone FeatureCollection **client-side** from the existing `/cameras`
payload — do not send it over the wire; it would multiply an already-765 KB
response by ~14.

**5.2 — "What this camera sees" (the honest proxy).**

Given a camera's position and bearing, find the nearest street-level photo whose
own compass angle points roughly the same way. That is the closest thing to a
camera's view that open data can give you.

Add to `twin/ingest/streetview.py`:

```python
def image_facing(lat, lon, bearing, tolerance_deg=45, radius_m=60):
    """Nearest KartaView/Mapillary image shot along `bearing`.

    Both providers return a per-image compass angle (`headers` on KartaView,
    `compass_angle` on Mapillary). Filtering by it is what turns "a photo near
    the camera" into "a photo of roughly what the camera is pointed at".
    """
```

Compare bearings **circularly** — `min(|a-b|, 360-|a-b|)` — or every camera
facing north gets nothing.

Wire it into a new route `GET /api/twin/cctv/view?lat=&lon=&direction=` and render
it in the drawer's camera row, captioned honestly:
*"Nearest open street-level image facing ~N (KartaView, 2020) — not a live feed."*

**5.3 — Real live feeds, where they legally exist.**

| Source | Access | Notes |
|---|---|---|
| OSM `contact:webcam` | Keyless | Already extracted into `stream_url`. Rare but genuine |
| Windy Webcams API v3 | `WINDY_WEBCAMS_KEY` | Free tier; returns a current still + a player URL. Already wired in `streetview.py` |
| Bengaluru Traffic Police public camera pages | Public web pages | **Link out only.** No API; do not scrape or proxy |
| Telangana / Hyderabad traffic portals | Public web pages | Same |

**Rules — non-negotiable:**
- Never proxy, re-host, or hotlink a third-party camera stream through the Sentinel server.
- Never attempt to reach a camera's device IP or default credentials. The layer is an
  OSINT *map of publicly documented infrastructure*, not an access tool.
- Always render `©️ OpenStreetMap contributors (ODbL)` wherever camera data appears.
- Prefer `rel="noopener"` link-outs over embeds for anything not explicitly licensed for embedding.

**5.4 — Coverage aggregate (optional, genuinely useful for ops).**

Count cameras per H3 cell and expose it as a `surveillance_coverage` property on
`/state`. An operator planning a response wants "which critical cells have no
camera coverage at all" — Bengaluru has 2,955 mapped cameras and Hyderabad 47, so
the answer differs wildly by city and is worth surfacing.

### Data reality check

| City | Mapped cameras | traffic | public | outdoor | private |
|---|---|---|---|---|---|
| Bengaluru | **2,955** | 1,028 | 1,365 | 287 | 51 |
| Hyderabad | **47** | 5 | 2 | 9 | — |

Hyderabad's OSM camera coverage is genuinely sparse. **Do not "fix" this by
inventing data.** Show the count honestly and add an "improve this map" link to
the OSM editor for the current viewport.

### Acceptance
- [ ] At z≥15, cameras with a bearing draw a translucent view cone in the direction they face.
- [ ] Clicking a camera shows type, mount, operator, bearing, and — where available — an image.
- [ ] The image is captioned with its provider, date, and whether it is live or archival.
- [ ] Cameras with no bearing render as a dot with no cone, not a north-facing one.
- [ ] ODbL attribution is visible wherever camera data is shown.
- [ ] No request from the Sentinel server to any camera host other than the documented APIs.

---

## D6 — Basemaps and street view are inconsistent between panes

> *"the maps are also inconsistent in street view"*

### Symptom
The Hyderabad and Bengaluru panes end up on different basemaps, or one shows
satellite and the other vector. Street-level imagery looks different cell to cell.

### Root cause
1. **Basemap is applied per-pane at construction.** `twin-console.js::buildPane()`
   calls `applyBasemap(value, "", [pane])` inside that pane's `whenLoaded`
   callback. The two panes load asynchronously and independently; if the operator
   changes the dropdown while the second pane is still loading, the panes diverge
   and nothing reconciles them.
2. **No persisted basemap state.** Reload and you are back to the default,
   regardless of what the operator chose.
3. **Street imagery provider varies by cell.** `streetview.py` tries Mapillary
   first *if a token exists*, else KartaView, and widens the radius only when the
   tight query finds nothing. Different cells legitimately return different
   providers with different colour, age and framing.

### Fix

**1. One source of truth, applied to every pane.**

```js
// TwinConsole
this.basemap = localStorage.getItem("twin.basemap") || "satellite";

setBasemap(choice, gibsDate) {
  this.basemap = choice;
  localStorage.setItem("twin.basemap", choice);
  Object.values(this.panes).forEach((pane) => this._applyBasemapToPane(pane));
}

// …and in buildPane's whenLoaded, always:
this._applyBasemapToPane(pane);       // reads this.basemap, never a DOM value
```

Never read the `<select>` inside a per-pane callback — read the state object.
Set the `<select>`'s value *from* the state object at boot.

**2. Reconcile on every pane load.** After a pane finishes loading, re-apply the
current basemap unconditionally. It is idempotent and it closes the race.

**3. Make street imagery consistency visible rather than hidden.** The provider
badge already exists. Extend it:
- Always show *all* available shots (Mapillary + KartaView + webcams), sorted by
  distance, rather than only the first provider that returns something.
- Show capture date on every thumbnail, not just the active one — a 2016 photo and
  a 2024 photo of the same junction are not interchangeable evidence.
- Add a "closest / newest" sort toggle.

**4. Never `setStyle()`.** If any future code path swaps the base style, every
twin layer is destroyed and the panes will diverge permanently. Add a guard
comment and, ideally, an assertion in dev builds.

### Acceptance
- [ ] Both panes show the same basemap at all times, including during load.
- [ ] Changing basemap while pane 2 is still loading leaves both correct.
- [ ] Basemap choice survives a page reload.
- [ ] The drawer lists every available image with provider and date.

---

## D7 — 3D buildings do not render properly

> *"buildings are not all 3d properly"*

### Symptom
Buildings are missing at city zoom, appear flat, or all appear the same height.

### Root cause
Four causes, all real, in order of impact:

1. **`minzoom: 13`, and the data genuinely does not exist below it.** OpenFreeMap
   Liberty's `building` source-layer is only emitted from zoom 13. The cities'
   `default_zoom` is **10.2**. So on first load there are, correctly, zero
   buildings — and nothing tells the operator why. This is almost certainly what
   "not all 3D properly" means.

2. **`render_height` is sparse in Indian cities.** The fallback chain is
   `render_height` → `building:levels × 3` → **8 m**. In wards where OSM has
   neither tag, every building becomes an identical 8 m slab.

3. **Pitch 0 makes extrusions invisible.** At a top-down view, a `fill-extrusion`
   is indistinguishable from a `fill`.

4. **A raster inserted above the building layer hides it entirely.** This was a
   live bug — satellite imagery was being inserted before `twin-hexes` rather than
   before `buildings-3d`, so it covered the buildings. `RASTER_BEFORE` in
   `digital-twin.js` now encodes the correct order; **do not change it casually.**

### Fix

**1. Tell the operator, and offer the fix.**

```js
// Disable the toggle below the data's own zoom floor, and say why.
const BUILDINGS_MINZOOM = 13;

updateBuildingToggle(pane) {
  const box = this.q(`[data-layer-panel="${pane.citySlug}"] [data-layer-toggle="buildings-3d"]`);
  const tooFar = pane.map.map.getZoom() < BUILDINGS_MINZOOM;
  box.disabled = tooFar;
  box.closest("label").title = tooFar
    ? "Building footprints are only published from zoom 13 — zoom in to see them"
    : "";
}
// Wire to map.on("zoomend"). When the operator ticks it while zoomed out,
// fly to z13.5 rather than silently doing nothing.
```

**2. Estimate heights properly.** Replace the flat 8 m default with a
tag-informed table. Indian urban form is not uniform and the current default
flattens it:

```js
const HEIGHT_BY_TYPE = [
  ["apartments",  4],   // storeys, ×3.2 m below
  ["commercial",  3],
  ["retail",      2],
  ["industrial",  2],
  ["warehouse",   2],
  ["hospital",    5],
  ["school",      3],
  ["house",       2],
  ["hut",         1],
];

// render_height → building:levels × 3.2 → type default × 3.2 → 6 m
const heightExpression = [
  "coalesce",
  ["get", "render_height"],
  ["case", ["has", "building:levels"],
    ["*", ["to-number", ["get", "building:levels"]], 3.2],
    ["*", ["match", ["get", "building"], /* …HEIGHT_BY_TYPE pairs… */ 2], 3.2]],
];
```

**Critical MapLibre gotcha:** never put a bare `null` inside `coalesce` — the
expression evaluator rejects it (*"Expected value to be of type number, but found
null instead"*) and the layer fails to add with no visible error. Use
`["case", ["has", key], …, fallback]` so `to-number` is never evaluated on an
absent property.

**3. Guarantee a non-zero pitch when buildings are on.** If pitch is 0 and the
operator enables 3D buildings, ease to 45°:

```js
if (this.map.getPitch() < 15) this.map.easeTo({ pitch: 45, duration: 600 });
```

**4. Keep the vector style permanently loaded.** `buildings-3d` names the
`openmaptiles` source by hand. If the base style is ever swapped for a raster-only
style, MapLibre skips the layer **silently** — no error, just no buildings. This is
why the architecture stacks rasters over a permanent vector style (§I.6).

### Upgrade path (optional, later)
If OSM height coverage proves inadequate for demos, evaluate:
- **Overture Maps buildings** — open licence, materially better height coverage in India.
- **Google Photorealistic 3D Tiles** — best-looking by far, needs a key and has usage terms.
- **Cesium / deck.gl `Tile3DLayer`** — if photorealistic tiles are adopted.

Do not adopt any of these without checking the licence against how Sentinel is deployed.

### Acceptance
- [ ] At z≥13.5 with pitch ≥ 30, buildings extrude in both cities.
- [ ] Below z13 the toggle is disabled with an explanatory tooltip, not silently inert.
- [ ] Ticking the toggle while zoomed out flies to a zoom where buildings exist.
- [ ] Building heights vary by type where OSM lacks explicit heights.
- [ ] Enabling satellite does **not** hide buildings.
- [ ] No expression errors in the console.

---

# PART IV — Reference

## 1. Environment variables

All optional. Everything works keyless; keyed sources simply add layers.

```bash
# --- Feature flags -----------------------------------------------------
TWIN_ENABLED=1                    # master switch
TWIN_SCHEDULER_ENABLED=1          # background compute + refresh jobs
TWIN_DEV_OPEN_AUTH=0              # dev only; refused unless app.debug/testing.
                                  # NOTE: only bypasses the twin's OWN fallback
                                  # decorators — the host's Flask-Login gate
                                  # still applies, so this will NOT let you view
                                  # /digital-twin logged out.

# --- Grid & compute ----------------------------------------------------
TWIN_H3_RESOLUTION=8              # ~460 m cells. 9 = ~174 m (≈7× more cells)
TWIN_COMPUTE_INTERVAL_MIN=5
TWIN_WEATHER_INTERVAL_MIN=15
TWIN_AIRQUALITY_INTERVAL_MIN=30
TWIN_FLOOD_INTERVAL_HOURS=6
TWIN_INCIDENT_INTERVAL_MIN=2
TWIN_RADAR_INTERVAL_MIN=10

# --- Paths & network ---------------------------------------------------
TWIN_CACHE_DIR=data/twin/cache
TWIN_BOUNDARY_DIR=data/twin/boundaries
TWIN_HTTP_TIMEOUT_S=8             # keep ≤8s: this is on the request path

# --- Ground truth ------------------------------------------------------
TWIN_STREETVIEW_RADIUS_M=350
TWIN_CCTV_RADIUS_M=400

# --- Optional keyed sources --------------------------------------------
MAPILLARY_TOKEN=                  # denser street imagery
WINDY_WEBCAMS_KEY=                # live webcams
TOMTOM_API_KEY=                   # traffic flow tiles
TOMORROW_API_KEY=
DATA_GOV_IN_KEY=
```

## 2. Commands

```bash
# Seed the grid and zones (run once, then after any H3 resolution change)
python scripts/seed_twin.py

# Pull admin boundary polygons from Overpass (slow, interactive, patient)
python scripts/fetch_boundaries.py

# Tests — 232 currently pass
python -m pytest -q
python -m pytest tests/twin/test_cctv.py -q

# Run
python app.py                     # http://127.0.0.1:5001
```

## 3. MapLibre gotchas — hard-won, do not relearn these

1. **`fill-extrusion-opacity` rejects data-driven expressions.** Bake per-feature
   opacity into an `rgba()` `fill-extrusion-color` instead.
2. **Bare `null` inside `coalesce` throws.** Use `["case", ["has", k], …, default]`.
3. **A mismatched `source` name makes `addLayer` fail silently** — the layer is
   skipped with no visible error. `"openmaptiles"` is the correct name for
   OpenFreeMap Liberty; it is not guessable.
4. **There is no z-index.** Order is set by `addLayer(layer, beforeId)` only.
5. **`setStyle()` destroys every custom source and layer.** Never call it.
6. **`promoteId` is required** on GeoJSON sources before `setFeatureState` can
   address features by a string key.
7. **A CSS `transform` on any ancestor breaks pointer coordinate maths.**
8. **A map built in a hidden or zero-height container never paints** and behaves
   as if input is dead until `resize()` is called.
9. **Raster `source.maxzoom` over-zooms rather than 404s** — required for NASA
   GIBS, whose imagery is native to ≈ z9.
10. **Loading two copies of MapLibre detaches every existing map** with no error.

## 4. Attribution obligations

These are licence conditions, not niceties. They must be visible in the UI.

| Data | Required attribution |
|---|---|
| OpenStreetMap (cameras, assets, water, drains, geocoding) | `©️ OpenStreetMap contributors (ODbL)` |
| Esri World Imagery | `©️ Esri, Maxar, Earthstar Geographics` |
| OpenFreeMap / OpenMapTiles | `©️ OpenMapTiles ©️ OpenStreetMap contributors` |
| NASA GIBS | `NASA EOSDIS GIBS` |
| KartaView | `©️ KartaView contributors (CC BY-SA)` |
| Mapillary | `©️ Mapillary contributors (CC BY-SA)` |
| RainViewer | `RainViewer.com` |
| Open-Meteo | `Open-Meteo.com (CC BY 4.0)` |

Also: the GloFAS discharge figure is a **model anomaly, not an official CWC
reading**. Label it as such wherever it appears — the existing flood widgets
already do.

## 5. Suggested order of work

1. **D3** (zoom) and **D4** (scrolling) — cheapest, and they make everything else
   testable by hand.
2. **D1** (outline selection) and **D2** (opacity) — do them together; they are
   the same visual system.
3. **D7** (3D buildings) — mostly explanation and a better height expression.
4. **D6** (basemap consistency) — a small state refactor.
5. **D5** (CCTV views) — the largest piece; do 5.1 (cones) first and ship it
   before starting 5.2.

## 6. Definition of done

- [ ] All 7 defects pass their acceptance criteria on **all four** host surfaces:
      `/dashboard`, `/analyst_dashboard`, `/coordination`, `/digital-twin`.
- [ ] `python -m pytest -q` is green, with new tests for D1, D5 and D7.
- [ ] Exactly one MapLibre copy on every page (`maplibregl.version` is stable).
- [ ] No console errors or expression warnings on any host page.
- [ ] Every data source in §IV.4 is attributed in the UI.
- [ ] Both cities render with satellite, buildings, risk grid, cameras and water
      without manual intervention after a fresh `seed_twin.py`.
- [ ] The console degrades to a labelled error, never a blank card, when the API
      is unreachable — and the host page's other panels keep working.

---

## Appendix — Design principles this module holds to

These are why the code looks the way it does. Preserve them.

- **C1 — Never take the app down.** Every ingest failure degrades one layer or one
  sub-score. `IngestAdapter.run()` never raises.
- **C3 — Show your working.** Every risk score stores the raw inputs that produced it.
- **C4 — Secure by default.** If the twin cannot determine who the caller is, it
  returns 401/403 rather than serving officials' data.
- **C6 — Additive only.** The twin adds two blueprints, its own tables, and jobs on
  the scheduler that already existed. It changes no existing route, model or
  template's shape.
- **C7 — Audit everything.** Every ingest writes a `TwinDataSnapshot`, and an audit
  failure must never destroy good data.
- **Honesty over polish.** A degraded cell is drawn as degraded. An estimated
  camera cone is labelled as an estimate. An archival photo is not presented as a
  live feed. If the twin is guessing, the operator must be able to see that it is
  guessing.