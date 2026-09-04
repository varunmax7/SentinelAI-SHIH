# Live incident feeds + LangGraph triage agent

A build spec for the Urban Digital Twin (`twin/`). Hand this to the IDE that
will implement it.

---

## 0. Scope — read this first

**Build:**
1. Ingest of **real, live, official public incident feeds** into the twin's
   incident layer.
2. A **LangGraph + Anthropic** agent that does four jobs: extraction,
   correlation/dedup, RAG-over-documents, and brief generation.
3. An **admin flag queue** with human approval before anything goes live.

**Do NOT build:**
- ❌ **Any Google Cloud / Maps integration.** Dropped deliberately — it
  requires a billing tier. Ignore `GOOGLE_IMAGERY_README.md` in this repo.
- ❌ **Any LLM that computes risk scores.** See §3.
- ❌ **Any trained/predictive ML model.** There is no training data —
  `twin_cell_history` has **0 rows**. Prediction comes from Open-Meteo
  forecasts through the twin's existing `horizon` machinery. Revisit in
  months, once history has accumulated.
- ❌ **Mock/seed/demo incident data.** Every incident must trace to a real
  fetched source document.

---

## 1. Why this exists

The twin's incident layer is empty. Not mocked — **empty**:

```
sqlite> select count(*) from report;
0
```

`/api/twin/<city>/incidents` → `InternalReportsAdapter` → the host app's
`Report` table filtered to `verification_status == 'approved'`. Nobody has
submitted a report, so the layer returns an empty FeatureCollection and the
`incident` sub-score contributes `0.0` to every cell.

Everything *else* is already real and live: Open-Meteo (rain, forecast, air
quality, discharge), RainViewer, NASA GIBS, OSM/Overpass (7,954 assets). The
gap is external incidents. This spec fills it.

---

## 2. The data sources — all verified live

Every endpoint below was called and confirmed working. Response sizes and
item counts are from the verification run; treat them as "this shape of
thing", not fixed values.

### 2.1 NDMA SACHET — India's official CAP alert feed ⭐ primary

Keyless. Public domain. Government-authoritative. **This is the most
important source in this document.**

| Feed | URL | Verified |
|---|---|---|
| All India | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml` | 200, 99 items |
| Karnataka (Bengaluru) | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_karnataka.xml` | 200, 10 items |
| Telangana (Hyderabad) | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_telangana.xml` | 200, 10 items |
| Full CAP XML | `.../FetchXMLFile?identifier=<guid>` | 200 |
| Alert polygon | `.../FetchPolygonXMLFile?identifier=<guid>` | 200, ~100 KB |

Use the **state feeds**, not all-India — they are already scoped to the two
cities the twin models.

A real item from the Karnataka feed:

```xml
<item>
  <title>Light Thunderstorm with surface wind is likely to occur at isolated
         places over Bengaluru Rural, Bengaluru Urban districts in next 3
         hours. Source : IMD Bengaluru</title>
  <category>Met</category>
  <link>https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1787755032813019</link>
  <author>controlroom@ndma.gov.in (IMD Bengaluru)</author>
  <guid isPermaLink="false">1787755032813019</guid>
  <pubDate>Wed, 26 Aug 2026 14:42:54 GMT</pubDate>
</item>
```

And the CAP 1.2 document behind that `<link>`:

```xml
<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <cap:identifier>IN-1787755032813019_19</cap:identifier>
  <cap:sender>Karnataka-SNDMC</cap:sender>
  <cap:status>Actual</cap:status>
  <cap:msgType>Update</cap:msgType>
  <cap:info>
    <cap:category>Met</cap:category>
    <cap:event>Light Thunderstorm with surface wind</cap:event>
    <cap:urgency>Expected</cap:urgency>
    <cap:severity>Moderate</cap:severity>
    <cap:certainty>Possible</cap:certainty>
    <cap:effective>2026-08-26T20:06:00+05:30</cap:effective>
    <cap:expires>2026-08-26T23:06:00+05:30</cap:expires>
    <cap:headline>…</cap:headline>
    <cap:instruction>Please follow SDMA guidelines.</cap:instruction>
    <cap:parameter>
      <cap:valueName>Polygon URL</cap:valueName>
      <cap:value>…/FetchPolygonXMLFile?identifier=1787755032813019</cap:value>
    </cap:parameter>
    <cap:area>
      <cap:areaDesc>Bengaluru Rural,Bengaluru Urban districts of Karnataka</cap:areaDesc>
      <cap:geocode>
        <cap:valueName>LGD District Code</cap:valueName>
        <cap:value>526</cap:value>
      </cap:geocode>
    </cap:area>
  </cap:info>
</cap:alert>
```

The polygon document is a flat list of space-separated `lat,lon` pairs:

```xml
<alert>
  <identifier>IN-1787755032813019_19</identifier>
  <polygon>12.868094,77.835487 12.863723,77.832127 12.858955,77.831985 …</polygon>
</alert>
```

### 2.2 Secondary sources

| Source | Endpoint | Auth | Verified |
|---|---|---|---|
| **GDACS** events | `https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH` | keyless | 200, 142 KB GeoJSON |
| GDACS RSS | `https://www.gdacs.org/xml/rss.xml` | keyless | 200 |
| **USGS** quakes | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` | keyless | 200, 202 KB |
| **NASA FIRMS** fire | `https://firms.modaps.eosdis.nasa.gov/api/area/...` | free `MAP_KEY` | not tested |
| **ReliefWeb** | `https://api.reliefweb.int/v2/disasters?appname=<approved>` | **approved appname required** | 403 without |

⚠️ **ReliefWeb v1 is decommissioned** (returns HTTP 410). v2 rejects
unregistered appnames with 403. Register at
`https://apidoc.reliefweb.int/parameters#appname` or skip this source.

Build order: **SACHET first** (highest value, keyless, city-relevant), then
GDACS + USGS (trivially reliable GeoJSON). FIRMS and ReliefWeb are optional.

---

## 3. The architecture, and the one rule that governs it

### The rule: the LLM never computes risk

The twin already has its detector. `twin/scoring.py` is pure, deterministic,
unit-testable functions — `risk_score = hazard × vulnerability`, with
documented weights and an explicit `None` (unmeasured) vs `0.0` (measured as
nothing) distinction.

**Do not replace, wrap, or supplement that with an LLM.** At 1,747 cells every
5 minutes an LLM would be slow, expensive, and non-deterministic — and when
an official acts on a flag and is asked "why was this zone flagged," the
answer must be `62 mm/3h against a 30 mm threshold`, not "the model said so."
Scores must be reproducible and auditable.

The LLM's four jobs are all **language** jobs, none of them arithmetic:

| # | Job | Why an LLM |
|---|---|---|
| 1 | **Extraction** — CAP/RSS/news free text → structured `{hazard, severity, area, time_window}` | Headlines are prose; regex breaks on the variety |
| 2 | **Correlation & dedup** — one IMD warning + 3 citizen reports + a discharge spike = **one** event | Cross-source identity is genuinely hard |
| 3 | **RAG over documents** — SOPs, NDMA guidelines, past situation reports | Gives the admin precedent and context, never the score |
| 4 | **Brief generation** — the flag card the admin reads, with citations | Turning numbers + context into prose is the core competence |

### The pipeline

```
   feeds (SACHET / GDACS / USGS)
             │
             ▼
   ┌───────────────────┐
   │ ingest (adapters) │  existing IngestAdapter pattern, disk-cached
   └─────────┬─────────┘
             ▼
   ┌───────────────────────────────────────────────────┐
   │              LangGraph agent                      │
   │                                                   │
   │  normalize → extract(LLM) → geo_resolve →         │
   │  correlate(LLM) → score(DETERMINISTIC, existing)  │
   │       → threshold → retrieve(RAG) →               │
   │         draft_brief(LLM) → ⏸ HUMAN APPROVAL       │
   └─────────────────────────┬─────────────────────────┘
                             ▼
                   admin flag queue → publish → map layer
```

`score` calls the **existing** `twin/scoring.py`. It is a plain Python node
in the graph, not a tool the model may reason about.

---

## 4. LangGraph design

### 4.1 State

```python
from typing import TypedDict, Annotated
import operator

class TriageState(TypedDict):
    raw_items:    list[dict]                        # straight from the feeds
    extracted:    Annotated[list[dict], operator.add]  # after job 1
    cells:        dict[str, list[str]]              # alert_id -> [h3, …]
    clusters:     list[dict]                        # after job 2
    scored:       list[dict]                        # deterministic
    flagged:      list[dict]                        # above threshold
    context:      dict[str, list[dict]]             # RAG hits per cluster
    briefs:       list[dict]                        # after job 4
    approved:     list[dict]                        # post human gate
    errors:       Annotated[list[str], operator.add]
```

### 4.2 Nodes

| Node | Type | Does |
|---|---|---|
| `fetch` | plain | Pull feeds via the ingest adapters (§5) |
| `normalize` | plain | CAP/GeoJSON → one internal dict shape |
| `extract` | **LLM** | Job 1 — structured output, `with_structured_output(...)` |
| `geo_resolve` | plain | Polygon/district → H3 cells (§6) |
| `correlate` | **LLM** | Job 2 — cluster cross-source duplicates |
| `score` | **plain** | Calls existing `twin/scoring.py`. **Never an LLM.** |
| `threshold` | plain | Config cutoff decides what becomes a flag |
| `retrieve` | RAG | Job 3 — vector search over the corpus |
| `draft_brief` | **LLM** | Job 4 — admin-readable brief with citations |
| `human_gate` | **interrupt** | `interrupt()` — blocks until an admin decides |
| `publish` | plain | Write approved flags, fire notifications |

Conditional edges: `threshold` routes to `END` when nothing clears the
cutoff — the common case, and it must cost zero LLM calls.

### 4.3 The human gate

Use LangGraph's checkpointer + `interrupt()`. This mirrors the
`verification_status == 'approved'` pattern already in the schema — no flag
reaches an operator without a human saying yes.

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt

def human_gate(state: TriageState):
    decision = interrupt({"briefs": state["briefs"]})
    return {"approved": [b for b in state["briefs"]
                         if decision.get(b["id"]) == "approve"]}
```

Persist the checkpointer to `instance/` so a pending flag survives a restart.

### 4.4 Model choice

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-5", temperature=0, max_tokens=2000)
```

`temperature=0` throughout — this is extraction and summarisation, not
creative writing. Use `.with_structured_output(PydanticModel)` for jobs 1 and
2 so the graph never parses free text.

---

## 5. Ingest adapters

Follow the existing pattern exactly — subclass `IngestAdapter`
(`twin/ingest/base.py`) so these inherit the timeout, disk TTL cache, and
degrade-don't-raise contract every other source already has.

New files:

```
twin/ingest/sachet.py     # SachetCapAdapter    (primary)
twin/ingest/gdacs.py      # GdacsAdapter
twin/ingest/usgs.py       # UsgsQuakeAdapter
```

Each must implement `fetch_raw`, `neutral_value`, `record_count` and override
`_cache_key` — **the base implementation hashes every kwarg including the
SQLAlchemy handle, whose repr embeds a memory address, so the key changes on
every restart.** `StreetViewAdapter` and `CctvOsintAdapter` both override it
for this reason; copy their approach.

Suggested TTLs:

| Adapter | `cache_ttl_s` | Why |
|---|---|---|
| SACHET | `300` (5 min) | Alerts are time-critical; feed updates often |
| GDACS | `900` | Global events move slowly |
| USGS | `300` | Quakes are instantaneous but the feed is cheap |

Schedule them in `twin/jobs.py` alongside the existing compute job. The twin
creates no scheduler of its own — `register_jobs(app, db, scheduler)` receives
the host's.

---

## 6. Geo resolution — CAP alert → H3 cells

This is the fiddly part. CAP gives you **two** location representations and
you need a fallback chain:

1. **Polygon** (preferred). Fetch the `Polygon URL` from `cap:parameter`.
   Parse the space-separated `lat,lon` pairs, then fill to H3 at the twin's
   resolution (`TWIN_H3_RESOLUTION=8`). `h3>=4.1.0` is already a dependency.

   ```python
   # h3 v4 API — verify exact signature against the installed version
   pairs = [tuple(map(float, p.split(","))) for p in polygon_text.split()]
   poly  = h3.LatLngPoly(pairs)
   cells = h3.polygon_to_cells(poly, res=8)
   ```

   ⚠️ CAP polygons are `lat,lon`. GeoJSON is `lon,lat`. Mixing these silently
   places Bengaluru alerts in the Indian Ocean.

2. **LGD District Code** (fallback). When there is no polygon, the alert is
   district-scoped (`526`, `525` = Bengaluru Rural/Urban). Map the code to a
   district boundary and fill that. The repo already has
   `scripts/fetch_boundaries.py` and `data/twin/boundaries/`.

3. **`areaDesc` string** (last resort). Only if 1 and 2 fail. Do **not** let
   the LLM invent coordinates — have it pick from a known district list, or
   drop the alert.

Then intersect the resulting cell set with `twin_cell.h3_index` for the city,
exactly as `_reports_within_city()` in `twin/routes.py` already does. Alerts
outside both cities are discarded, not stored.

---

## 7. Feeding the score

Map CAP fields onto the shape `twin/scoring.py` already consumes.
`report_contribution(priority, confidence, timestamp, in_this_cell)` needs a
priority and a confidence:

| CAP field | Maps to | Suggested |
|---|---|---|
| `cap:severity` | `priority` | Extreme→critical, Severe→high, Moderate→medium, Minor→low |
| `cap:certainty` | `confidence` | Observed→1.0, Likely→0.75, Possible→0.5, Unlikely→0.25 |
| `cap:effective` / `cap:sent` | `timestamp` | Parse as tz-aware; SACHET uses `+05:30` |
| `cap:expires` | *(new)* | Drop the contribution entirely once expired |

Keep official alerts **distinguishable from citizen reports** in the data
model — same sub-score, different provenance. An operator must be able to see
that a flag came from IMD rather than from an anonymous submission.

Respect the module's contract: `0.0` means *measured as nothing*, `None`
means *unmeasured*. A cell with no alerts passes `0.0`.

---

## 8. Data model

Reuse what exists where possible — `models.py` already has `EmergencyEvent`,
`SituationReport`, `Notification`, and `Report`.

New tables (in `twin/models.py`, following the `twin_` prefix convention):

```
twin_external_alert
  id, source ('sachet'|'gdacs'|'usgs'), source_uid, cap_identifier,
  sender, event, category, severity, certainty, urgency,
  effective_at, expires_at, headline, instruction,
  area_desc, geometry_kind ('polygon'|'district'|'point'),
  raw_url, fetched_at
  UNIQUE(source, source_uid)          -- dedup key

twin_alert_cell
  alert_id -> twin_external_alert.id, h3_index, city_id

twin_flag                              -- what the admin reviews
  id, cluster_key, city_id, h3_index, risk_score, severity,
  brief_md, citations_json,
  status ('pending'|'approved'|'rejected'), reviewed_by, reviewed_at,
  created_at
```

`UNIQUE(source, source_uid)` is what makes re-polling idempotent. SACHET's
`<guid>` is stable; CAP `msgType=Update` means **upsert, not insert** — an
Update supersedes the alert it names in `cap:references`.

---

## 9. RAG corpus (Phase 3 — defer)

Only job 3 needs a vector store. Jobs 1, 2 and 4 do not. Ship phases 1–2
first.

- **Store:** Chroma, persisted under `data/twin/rag/`. Local file, no server.
  Swap for pgvector only if/when you move to Postgres (`config.py` already
  supports `DATABASE_URL`).
- **Embeddings:** Anthropic does not serve an embeddings API — use a local
  sentence-transformers model so this stays key-light.
- **Corpus:** NDMA/SDMA SOP PDFs, past `SituationReport` rows, historical
  `twin_external_alert` headlines, ward flood notes.
- **Every retrieved chunk must carry a citation** rendered in the brief. A
  brief that cites nothing is a brief nobody can check.

Do **not** embed live numeric telemetry. Numbers belong in the deterministic
scorer; the vector store is for documents.

---

## 10. Rendering

- New route `GET /api/twin/<city>/alerts` → GeoJSON, mirroring the existing
  `/incidents` shape so the frontend reuses its rendering path.
- New route `GET/POST /api/twin/flags` → the admin queue (list, approve,
  reject). `@twin_roles_required`; approval restricted to `TWIN_WRITE_ROLES`
  (`official`, `admin`) per `twin/security.py`.
- Map layer: alert polygons as a fill layer beneath the risk grid. Layer
  order is set by `addLayer(layer, beforeId)` — **there is no z-index in
  MapLibre**, and `setStyle()` destroys every custom source and layer.
- Flag badge in the console header with a pending count; the panel already
  polls on an interval (`this.timers`).
- Push new flags over the existing SSE `/stream` endpoint — `twin/stream.py`
  already publishes `incident` events on report approval.

---

## 11. Setup

```bash
pip install langgraph langchain-anthropic langchain-core \
            feedparser lxml pydantic
# Phase 3 only:
pip install chromadb sentence-transformers
```

`.env` additions (already gitignored):

```bash
ANTHROPIC_API_KEY=
TWIN_AGENT_ENABLED=1
TWIN_AGENT_MODEL=claude-sonnet-5
TWIN_ALERT_POLL_MIN=5
TWIN_FLAG_THRESHOLD=60          # risk_score above which a flag is raised
TWIN_SACHET_STATES=karnataka,telangana
# NASA_FIRMS_MAP_KEY=           # optional
# RELIEFWEB_APPNAME=            # optional, needs approval
```

Read them in `twin/config.py` beside the existing keyed-source slots. **The
twin must still boot with none of these set** — that is constraint C5, and
`TWIN_AGENT_ENABLED=0` must be a fully supported steady state, not a degraded
one.

---

## 12. Build sequence

**Phase 1 — data, no AI.** SACHET adapter, CAP + polygon parsing, H3
resolution, `twin_external_alert` + `twin_alert_cell`, the `/alerts` route,
the map layer. *Ship this first.* It puts real official alerts on the map
with zero LLM involvement, and it is the bulk of the user-visible value.

**Phase 2 — the agent.** LangGraph skeleton, jobs 1/2/4, `twin_flag`, the
admin queue, the human gate. Add GDACS + USGS.

**Phase 3 — RAG.** Chroma, the corpus, job 3, citations in briefs.

---

## 13. Gotchas

1. **CAP XML is namespaced.** Tags are `cap:alert`, `cap:info`, `cap:area` —
   matching bare `<alert>` finds nothing and fails silently. Register
   `{"cap": "urn:oasis:names:tc:emergency:cap:1.2"}`. The *polygon* document
   is **not** namespaced (`<alert><polygon>`). They differ. This cost real
   time to discover.
2. **CAP polygons are `lat,lon`; GeoJSON is `lon,lat`.**
3. **The polygon lives at a separate URL**, in `cap:parameter` → `Polygon
   URL`, not inline in `cap:area`. One extra fetch per alert — cache it.
4. **`msgType=Update` supersedes**, it does not add. Follow
   `cap:references`. Ignoring this double-counts every updated alert.
5. **`cap:expires` is authoritative.** An expired alert must stop
   contributing to the score, not linger.
6. **SACHET timestamps carry `+05:30`.** Parse tz-aware; never assume UTC.
7. **ReliefWeb v1 returns HTTP 410.** v2 needs an approved appname (403
   otherwise).
8. **`_cache_key` must be overridden** — see §5.
9. **A quiet feed is the normal case.** Most polls return nothing new. The
   graph must short-circuit to `END` before any LLM node, or you will burn
   tokens on empty runs every 5 minutes.
10. **Never let the LLM emit coordinates or risk numbers.** Constrain it to
    picking from candidates you supply.

---

## 14. Acceptance criteria

- [ ] `select count(*) from twin_external_alert` > 0, every row traceable to
      a fetched URL
- [ ] A SACHET alert for Bengaluru renders as a polygon on the map, in the
      correct hemisphere
- [ ] Re-running ingest creates **zero** duplicate rows
- [ ] An expired alert stops contributing to `incident_score`
- [ ] With `TWIN_AGENT_ENABLED=0`, the twin boots and behaves exactly as it
      does today
- [ ] A quiet poll cycle makes **zero** Anthropic API calls
- [ ] No flag reaches the map without an admin approving it
- [ ] Every brief cites its sources
- [ ] `python -m pytest -q` still passes (232 tests at time of writing)

---

## 15. Sources

- [SACHET National Disaster Alert Portal](https://sachet.ndma.gov.in/) · [CAP feed index](https://sachet.ndma.gov.in/CapFeed)
- [GDACS](https://www.gdacs.org/) · [USGS earthquake feeds](https://earthquake.usgs.gov/earthquakes/feed/v1.0/)
- [ReliefWeb API](https://apidoc.reliefweb.int/) · [NASA FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/)
- [CAP 1.2 spec (OASIS)](http://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2.html)
- [LangGraph docs](https://langchain-ai.github.io/langgraph/) · [langchain-anthropic](https://python.langchain.com/docs/integrations/chat/anthropic/)