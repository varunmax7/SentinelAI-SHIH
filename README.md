# 🛡️ Sentinel AI — Multi-Agent Urban Disaster & Infrastructure Intelligence Platform

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite%20%2F%20PostgreSQL-Ready-003B57?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Twilio](https://img.shields.io/badge/Twilio-WhatsApp_API-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)
[![Leaflet](https://img.shields.io/badge/Leaflet.js-Maps-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)
[![MapLibre](https://img.shields.io/badge/MapLibre_GL-3D_Maps-295DAA?style=for-the-badge&logo=maplibre&logoColor=white)](https://maplibre.org)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**An enterprise-grade, AI-powered multi-agent disaster response & urban infrastructure management platform.**  
*Addressing Problem Statement **SH-SVA-03**: Unifying fragmented urban departments through autonomous incident detection, coordinated multi-agent response, and real-time city-wide digital twin intelligence.*

**119 API Routes · 23 Database Models · 50 Templates · 25 Forms · 6 Languages · 6 AI Agents · 4 Reporting Channels**

[Problem Statement](#-problem-statement-sh-sva-03) • [Solution](#-sentinel-ai-the-solution) • [App Flow](#-complete-application-flow) • [Features](#-feature-deep-dive) • [Architecture](#-system-architecture) • [Getting Started](#-getting-started) • [API Reference](#-api-reference) • [WhatsApp Bot](#-whatsapp-bot) • [Database Schema](#-database-schema) • [Deployment](#-deployment) • [Roadmap](#-roadmap)

</div>

---

## 📚 Table of Contents

| # | Section | What's Inside |
|:--|:---|:---|
| 1 | [Executive Summary](#-executive-summary) | The 60-second overview |
| 2 | [Problem Statement SH-SVA-03](#-problem-statement-sh-sva-03) | The official PS, decomposed clause by clause |
| 3 | [Requirement Traceability Matrix](#-requirement-traceability-matrix) | Every PS clause mapped to shipped code |
| 4 | [Sentinel AI: The Solution](#-sentinel-ai-the-solution) | Multi-agent architecture & digital twin |
| 5 | [Complete Application Flow](#-complete-application-flow) | End-to-end operational pipeline |
| 6 | [Feature Deep-Dive](#-feature-deep-dive) | All 28 feature clusters in detail |
| 7 | [System Architecture](#-system-architecture) | Layers, agents, integrations |
| 8 | [Data Flow Sequences](#-data-flow-sequences) | Step-by-step request traces |
| 9 | [Project Structure](#-project-structure) | Every file and what it does |
| 10 | [Database Schema](#-database-schema) | All 23 models, fields, relations |
| 11 | [User Roles & Permissions](#-user-roles--permissions) | RBAC matrix |
| 12 | [Points & Rewards Economy](#-points--rewards-economy) | Exact scoring rules |
| 13 | [Getting Started](#-getting-started) | Install → run in 5 steps |
| 14 | [Configuration Reference](#-configuration-reference) | Every env var explained |
| 15 | [API Reference](#-api-reference) | All 119 routes grouped |
| 16 | [WhatsApp Bot](#-whatsapp-bot) | Conversation flows & commands |
| 17 | [Tech Stack](#-tech-stack) | Every dependency and why |
| 18 | [Deployment](#-deployment) | Render, Heroku, Docker, ngrok |
| 19 | [Security](#-security) | Hardening posture |
| 20 | [Performance & Scalability](#-performance--scalability) | Benchmarks and limits |
| 21 | [Testing & QA Checklist](#-testing--qa-checklist) | Demo-day validation script |
| 22 | [Troubleshooting](#-troubleshooting) | Common failures and fixes |
| 23 | [Compliance & Governance](#-compliance--governance) | NDMA/SDMA alignment |
| 24 | [Roadmap](#-roadmap) | What ships next |
| 25 | [Recent Updates](#-recent-updates) | Changelog |
| 26 | [Contributing](#-contributing) | How to help |
| 27 | [License](#-license) | MIT |

---

## 🚀 Executive Summary

Sentinel AI is a **single unified command platform** that replaces the tangle of phone calls, WhatsApp groups, spreadsheets, and siloed departmental portals that Indian cities currently rely on during an urban incident or disaster.

It does five things no existing system does together:

1. **Detects incidents from four independent channels simultaneously** — a Progressive Web App form, a one-tap Voice SOS with NLP keyword extraction, an offline AI calling agent, and a full WhatsApp bot — so a citizen with no smartphone, no data plan, or no literacy in English can still raise an alarm.
2. **Validates every incident autonomously in under a second** using a 4-Parameter Accuracy System™ that cross-checks spatial corroboration, live meteorological data, the reporter's historical credibility, and NVIDIA NIM vision analysis of the reporter's photo — auto-approving anything above 85% confidence without a human in the loop.
3. **Runs a live city digital twin** — a 3D "God Mode" MapLibre GL globe layered with government TGDPS rainfall telemetry, RainViewer precipitation radar, Open-Meteo climate data, and every live incident in the database.
4. **Dispatches responders like a ride-hailing app** — geo-queries available volunteers, ranks them by distance and skill, fires a WhatsApp mission card with photo and coordinates, and tracks accept → en route → completed with GPS-verified photo proof.
5. **Simulates the future** — the Sentinel Resilience Engine takes projected rainfall and sea-level parameters and produces a full government-grade resilience report with sectoral damage forecasts across Power, Water, Telecom, and Housing, including cascade-failure analysis and time-bound action plans.

Everything is wrapped in a gamified civic layer — points, levels, badges, leaderboards, government certificates — so that the citizen network stays engaged **between** disasters, not just during them.

### At a Glance

| Metric | Value |
|:---|:---|
| **Backend routes** | 119 Flask routes (`app.py`, ~5,950 lines) |
| **Database models** | 23 SQLAlchemy models (`models.py`) |
| **Jinja2 templates** | 50 HTML templates |
| **WTForms classes** | 25 validated form definitions |
| **Languages supported** | 6 — English, Hindi, Telugu, Tamil, Malayalam, Kannada |
| **AI agents** | 6 — Detection, Prioritization, Dispatch, Alert, Analytics, Coordination |
| **Reporting channels** | 4 — PWA, Voice SOS, WhatsApp, AI calling agent |
| **External data sources** | Open-Meteo, Open-Meteo AQ, TGDPS, RainViewer, Nominatim, Esri, IMD/NDMA/USGS/GSI feeds |
| **AI verification latency** | Sub-second (4-parameter weighted scoring) |
| **Auto-approval threshold** | ≥ 85% confidence |
| **Volunteer dispatch radius** | 10 km (configurable; demo mode broadcasts wider) |
| **Completion proof radius** | Volunteer must be within 10 km of hazard with GPS + photo |
| **Government certificate threshold** | 500 points |
| **Offline capability** | Full IndexedDB queue + Service Worker shell caching |

---

## 🎯 Problem Statement: SH-SVA-03

> ### SH-SVA-03 — Urban Infrastructure Management
>
> **Urban infrastructure management is fragmented across departments, leading to delayed incident detection, inefficient response, and increased operational costs. A multi-agent AI system integrated with a city digital twin is needed to autonomously prioritize incidents, coordinate actions, and ensure timely, compliant resolution.**

### Decomposing the Problem Statement

The PS contains **six distinct engineering requirements**. Sentinel AI addresses each one explicitly:

| # | PS Clause | Engineering Requirement | Sentinel AI Response |
|:--|:---|:---|:---|
| 1 | *"fragmented across departments"* | A single shared operating picture across Fire, Police, Municipal, Health, Revenue, and Disaster agencies | **Coordination Dashboard** + Agency Registry + shared Resource Allocation ledger + SITREP system |
| 2 | *"delayed incident detection"* | Ingest incidents in seconds, not hours, from every possible channel | **4-channel omni-ingestion** (PWA / Voice SOS / WhatsApp / AI call) + sub-second AI validation |
| 3 | *"inefficient response"* | Match the right responder to the right incident automatically | **Uber-style dispatch** — geo-query, skill-match, WhatsApp mission card, lifecycle tracking |
| 4 | *"increased operational costs"* | Eliminate duplicate effort and reactive over-deployment | Deduplication via heatmap corroboration, precision geo-fencing (no mass blasts), volunteer-first response before paid crews |
| 5 | *"multi-agent AI system"* | Multiple specialised autonomous agents, not one monolithic model | **6 agents** — Detection, Prioritization, Dispatch, Alert, Analytics, Coordination |
| 6 | *"integrated with a city digital twin"* | A live, queryable, spatial model of the city | **God Mode 3D map** (MapLibre GL) + TGDPS telemetry + RainViewer radar + Urban Resilience Index zones + Resilience Engine simulation |
| 7 | *"autonomously prioritize incidents"* | Rank by severity without waiting for a human | 4-Parameter scoring → priority escalation (low → medium → high → critical), SOS auto-escalated to **critical** |
| 8 | *"coordinate actions"* | Cross-department task assignment and tracking | Emergency Events → Resource Allocations → Volunteer Assignments → SITREPs, all linked |
| 9 | *"timely, compliant resolution"* | Auditable, time-stamped, evidence-backed closure | GPS + photo proof of completion, immutable timestamps, CSV audit export, rejection reasons recorded |

### The Crisis in Numbers

India has **7,516 km of coastline** with over **170 million people** living in low-lying urban areas vulnerable to cyclones, floods, storm surges, and tsunamis. Urban infrastructure management across Indian cities suffers from systemic, cross-departmental failures:

| Problem Area | Real-World Impact |
|:---|:---|
| **🏛️ Departmental Silos** | Fire, police, municipal, health, and disaster agencies operate on separate communication channels. A single flood event requires 5+ departments to coordinate — manually, by phone. |
| **⏱️ Delayed Detection** | A field report of rising floodwater takes **hours** to be manually confirmed by authorities. Citizens call helplines, officials check social media, volunteers wait for orders. |
| **📞 Inefficient Dispatch** | Coordinators phone or message volunteers one by one, losing precious minutes while lives are at stake. No skill-matching, no distance ranking. |
| **🌐 Language Barriers** | Critical alerts in non-native languages are ignored by local communities — fishermen, farmers, coastal workers. |
| **📊 Zero Predictive Power** | Agencies react to disasters rather than simulating impacts ahead of time. No city-wide digital twin exists. |
| **💰 Operational Cost Overrun** | Redundant efforts, uncoordinated resource deployment, and reactive approaches drain government budgets. |
| **📵 Connectivity Collapse** | The moment a disaster hits, mobile data is the first casualty — yet every existing tool assumes a live connection. |
| **🔁 Duplicate Reporting** | The same pothole, the same flooded underpass, reported 40 times — with no automatic deduplication or corroboration scoring. |
| **📉 No Feedback Loop** | Citizens who report never learn what happened. Engagement dies after the first unanswered report. |

**The result:** Response times measured in hours. Lives and resources lost that could have been saved with an intelligent, unified system.

---

## 🧩 Requirement Traceability Matrix

Every requirement in SH-SVA-03 maps to specific, runnable code in this repository:

| PS Requirement | Implementation | Code Location |
|:---|:---|:---|
| Autonomous incident detection | 4-channel ingestion pipeline | `app.py::report()`, `app.py::submit_sos()`, `app.py::whatsapp_webhook()` |
| Autonomous prioritization | 4-Parameter Accuracy System™ | `utils.py::validate_report_accuracy_4params()` |
| Spatial corroboration | Heatmap density check, 5.5 km / 24 h window | `utils.py::_validate_heatmap_match()` |
| Meteorological validation | Live Open-Meteo cross-check | `utils.py::_validate_climate_alignment()` |
| Reporter credibility | Role × history × level scoring | `utils.py::_calculate_user_quality_score()` |
| Multi-agent dispatch | Geo-query + skill match + WhatsApp | `app.py::assign_volunteer_to_hazard()`, `app.py::match_volunteers()` |
| Geo-fenced alerting | Per-hazard radius rules | `utils.py::get_hazard_alert_radius()`, `utils.py::should_receive_alert()` |
| Inter-department coordination | Agencies, resources, SITREPs | `app.py::coordination_dashboard()` and `/coordination/*` routes |
| City digital twin | 3D MapLibre + live layers | `static/js/god-mode-maps.js`, `templates/analyst_dashboard.html` |
| Predictive simulation | Sentinel Resilience Engine | `app.py::simulate_impact()`, `app.py::simulate_analysis()` |
| Compliant resolution | GPS + photo proof, audit trail | `app.py::complete_rescue_assignment()`, `utils.py::sync_reports_to_csv()` |
| Resilience measurement | Urban Resilience Index zones | `models.py::ResilienceZone`, `models.py::ResilienceScore` |
| Offline resilience | IndexedDB queue + Service Worker | `static/js/offline-sync.js`, `static/sw.js` |
| Language inclusion | GPS-driven auto-translation | `translations.py`, `app.py::detect_preferred_language()` |

---

## 🧠 Sentinel AI: The Solution

Sentinel AI is not just another disaster app — it is a **multi-agent AI command system** that acts as the autonomous nervous system for urban crisis management.

### Multi-Agent Architecture

The platform deploys six specialized AI agents that work in concert. Each agent owns a distinct stage of the incident lifecycle and hands off to the next automatically.

| Agent | Role | Inputs | Outputs | Autonomy Level |
|:---|:---|:---|:---|:---|
| **🔍 Detection Agent** | Ingests citizen reports (PWA, Voice SOS, WhatsApp, AI calling agent), satellite data, TGDPS rainfall feeds, and weather APIs. Cross-validates using 4-parameter AI scoring. | Text, photo, video, GPS, audio transcript | Structured `Report` with hazard type, coordinates, confidence score | Fully autonomous |
| **📋 Prioritization Agent** | Ranks incidents by severity, proximity to critical infrastructure, corroboration density, and weather alignment. Auto-approves high-confidence reports (≥85%). | Confidence score, hazard type, corroboration count | `priority` (low/medium/high/critical), `verification_status` | Fully autonomous |
| **🚁 Dispatch Agent** | "Uber-style" volunteer matching — queries available responders within radius, ranks by distance, fires WhatsApp assignment cards, tracks acceptance and completion. | Verified hazard, volunteer registry, GPS | `VolunteerAssignment` records, WhatsApp mission cards | Semi-autonomous (official can override) |
| **📡 Alert Agent** | Geo-fenced push notifications — alerts only users within the hazard impact radius, not mass blasts. Attaches disaster photo and safe rescue coordinates. | Hazard location, per-hazard radius table, user home locations | In-app notifications, WhatsApp messages, push tokens | Fully autonomous |
| **📊 Analytics Agent** | Powers the Analyst Dashboard — live satellite overlays, TGDPS real-time rainfall maps (state + district level), climate source integration, matplotlib charts, risk simulators. | Report history, weather feeds, user engagement | Charts (PNG), JSON stats, URI scores | Continuous |
| **🤝 Coordination Agent** | Manages inter-departmental resource allocation, SITREP generation, agency registry, and supply-chain tracking across the response lifecycle. | Emergency events, agency capabilities, resource inventories | Resource allocations, SITREPs, coordination dashboard state | Semi-autonomous |

### Agent Handoff Protocol

```
   CITIZEN INPUT
        │
        ▼
┌───────────────────┐   confidence + hazard_type    ┌────────────────────┐
│  DETECTION AGENT  │ ────────────────────────────► │ PRIORITIZATION     │
│  • parse channel  │                                │ AGENT              │
│  • extract GPS    │                                │ • score ≥ 85% →    │
│  • NLP keywords   │                                │   auto-approve     │
│  • 3-param score  │                                │ • else → queue     │
└───────────────────┘                                └─────────┬──────────┘
                                                               │ approved
                            ┌──────────────────────────────────┼──────────────┐
                            ▼                                  ▼              ▼
                  ┌──────────────────┐            ┌──────────────────┐  ┌────────────────┐
                  │  ALERT AGENT     │            │  DISPATCH AGENT  │  │ ANALYTICS      │
                  │  • geo-fence     │            │  • 10 km query   │  │ AGENT          │
                  │  • per-hazard km │            │  • skill match   │  │ • URI recalc   │
                  │  • WhatsApp+push │            │  • WhatsApp card │  │ • charts       │
                  └──────────────────┘            └────────┬─────────┘  └────────────────┘
                                                            │ accepted
                                                            ▼
                                                  ┌──────────────────────┐
                                                  │ COORDINATION AGENT   │
                                                  │ • allocate resources │
                                                  │ • generate SITREP    │
                                                  │ • track to closure   │
                                                  └──────────────────────┘
```

### The City Digital Twin

The digital twin is not a marketing phrase here — it is a concrete set of live, queryable layers rendered over a 3D basemap:

| Twin Layer | Data Source | Refresh | Purpose |
|:---|:---|:---|:---|
| **Terrain & buildings** | MapLibre GL vector tiles (CARTO Voyager) with 55° pitch, −12.5° bearing | Static | Spatial context, 3D depth perception |
| **Satellite imagery** | Esri World Imagery | Static tiles | Ground truth visual reference |
| **Live incidents** | `/api/live_hazard_incidents` — up to 500 most recent active reports | On demand | Where things are going wrong right now |
| **Government hazards** | `/api/live_govt_hazards` — IMD, NDMA, USGS, GSI, Tsunami Early Warning | On demand | Official warning overlay |
| **Precipitation radar** | RainViewer tile API | ~10 min | Live rainfall movement |
| **TGDPS state rainfall** | Telangana Govt AWS station network (proxied) | Auto-refresh | Ground-station rainfall truth |
| **TGDPS district rainfall** | 33 selectable districts (proxied) | On selection | Ward-level granularity |
| **Climate telemetry** | Open-Meteo forecast + air quality | On geolocation lock | Temperature, humidity, wind, AQI |
| **Resilience zones** | `ResilienceZone` / `ResilienceScore` models | Periodic recalc | 0–100 URI score per grid zone |
| **Simulated futures** | Sentinel Resilience Engine | On simulate | Projected impact under scenario parameters |

### Why Sentinel AI vs. Existing Platforms

| Feature Area | Traditional Platforms | 🛡️ Sentinel AI |
|:---|:---|:---|
| **Response Speed** | Manual verification (takes hours) | **Sub-second AI Validation** (4-parameter checking algorithm) |
| **Reporting Channels** | Single-channel (app or phone) | **Omni-channel**: PWA reports, offline AI calling agent, one-tap Voice SOS with lat/long, full WhatsApp bot |
| **Accessibility** | Requires app downloads, English-first | **No-install PWA + WhatsApp + Voice SOS.** Auto-translates to 6 regional languages via GPS |
| **Volunteer Logistics** | Manual phone trees, chaotic groups | **"Uber-style" Auto-Dispatch.** Radius-bounded, skill-matched, WhatsApp-native |
| **Alerting Precision** | Mass SMS blasts (causes panic) | **Smart Geo-Fencing.** Per-hazard radius with disaster images + safe rescue locations |
| **Resource Supply Chain** | Top-down handouts only | **LifeLine P2P Marketplace** + agency supply-chain ledger for physical disaster items |
| **Predictive Power** | Reactive (post-disaster) | **Sentinel Resilience Engine + Live TGDPS Satellite Rainfall Maps** (state & district level) |
| **Dept. Coordination** | Phone calls between offices | **Unified Coordination Dashboard** — agencies, resources, SITREPs, volunteers |
| **Offline Behaviour** | Fails completely | **IndexedDB offline queue** — reports captured offline, auto-synced on reconnect |
| **Community Engagement** | None | **Volunteering Hub** — beach cleanups, tree planting, NGO onboarding |
| **Gamification** | None | **Points + Govt Certification + Leaderboards** with top-performer recognition |
| **Proof of Resolution** | Verbal confirmation | **GPS-verified photo proof** within 10 km of the incident |
| **Audit Trail** | Paper files | **CSV sync on every write** + immutable timestamps + rejection reasons |

---

## 🔄 Complete Application Flow

The following is the end-to-end operational flow of Sentinel AI, from incident detection to community resilience building:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: INCIDENT DETECTION                          │
│                                                                             │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────────────┐ │
│  │ 📱 Online   │  │ 📞 Offline via   │  │ 🆘 SOS Button                  │ │
│  │   Report    │  │   AI Calling     │  │   (One-tap with lat/long,      │ │
│  │   (PWA)     │  │   Agent          │  │    auto-records audio,         │ │
│  │             │  │                  │  │    NLP extracts keywords)      │ │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────┬─────────────────┘ │
│         │                  │                           │                    │
│         │      ┌───────────▼────────────┐              │                    │
│         │      │ 💬 WhatsApp Bot        │              │                    │
│         │      │   (linked account)     │              │                    │
│         │      └───────────┬────────────┘              │                    │
│         └──────────────────┴───────────────────────────┘                    │
│                            │                                                │
│                   ┌────────▼────────────────────────────────┐               │
│                   │  🤖 AI Verification Engine              │               │
│                   │  4-Parameter Accuracy System™           │               │
│                   │                                         │               │
│                   │  P1: Heatmap Match (25%)                │               │
│                   │      → Similar reports in 5.5km / 24hr  │               │
│                   │  P2: Climate Alignment (25%)            │               │
│                   │      → Open-Meteo live weather check    │               │
│                   │  P3: User Quality Score (25%)           │               │
│                   │      → Historical credibility of author │               │
│                   │  P4: Image Processing (25%)             │               │
│                   │      → NVIDIA NIM vision hazard match   │               │
│                   │                                         │               │
│                   │  Score ≥ 85% → AUTO-APPROVED            │               │
│                   │  Score < 85% → Queued for Official      │               │
│                   └────────┬────────────────────────────────┘               │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                   PHASE 2: ANALYST DASHBOARD & DIGITAL TWIN                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  🛰️ Live Satellite Climate Sources                                    │  │
│  │  • RainViewer real-time radar overlay                                 │  │
│  │  • Open-Meteo weather data (temp, humidity, wind, weather codes)      │  │
│  │  • TGDPS Live Rainfall Map — State Level (auto-refresh)               │  │
│  │  • TGDPS Live Rainfall Map — District Level (33 districts selectable) │  │
│  │  • Esri World Imagery satellite basemap                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  📊 Analytics & Risk Simulation                                       │  │
│  │  • Hazard distribution charts (server-rendered PNG)                   │  │
│  │  • Reports timeline & 7-day trend analysis                            │  │
│  │  • User engagement metrics                                            │  │
│  │  • Sentinel Resilience Engine: rainfall + sea-level → sectoral damage │  │
│  │  • Urban Resilience Index (URI) per geographic zone                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                   PHASE 3: OFFICIAL APPROVAL & ALERTING                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  🏛️ Official Review Panel                                       │        │
│  │  • View AI accuracy breakdown (all 4 parameters)                 │        │
│  │  • Approve / Reject with recorded reasons                        │        │
│  │  • Escalate priority (Low → Medium → High → Critical)            │        │
│  │  • Rejected reports enter a scheduled-deletion grace window      │        │
│  └────────────────────────────┬────────────────────────────────────┘        │
│                               │ approved                                    │
│  ┌────────────────────────────▼────────────────────────────────────┐        │
│  │  📡 Geo-Fenced Alert Dispatch                                    │        │
│  │  • Per-hazard radius (tsunami 10km, storm surge 15km, …)         │        │
│  │  • Only users inside the fence are notified — no mass panic      │        │
│  │  • Payload includes hazard photo + safe rescue coordinates       │        │
│  │  • Channels: in-app bell + WhatsApp + push token                 │        │
│  │  • Respects each user's per-hazard alert preferences             │        │
│  └────────────────────────────┬────────────────────────────────────┘        │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                   PHASE 4: RESPONSE & COORDINATION                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  🚁 Uber-Style Volunteer Dispatch                                │        │
│  │  1. Query available volunteers within radius                     │        │
│  │  2. Rank by distance; filter by skills & experience level        │        │
│  │  3. Fire WhatsApp mission card (photo + coords + severity)       │        │
│  │  4. Volunteer replies "1" Accept / "2" Decline                   │        │
│  │  5. Lifecycle: Pending → Accepted → Deployed → Completed         │        │
│  │  6. Completion requires GPS within 10km + photo proof            │        │
│  │  7. Points awarded by experience tier + speed bonus              │        │
│  └────────────────────────────┬────────────────────────────────────┘        │
│                               │                                             │
│  ┌────────────────────────────▼────────────────────────────────────┐        │
│  │  🤝 Inter-Department Coordination                                │        │
│  │  • Agency registry (govt, NGO, medical, emergency)               │        │
│  │  • Emergency events with severity + radius                       │        │
│  │  • Resource allocation ledger (allocated→deployed→used→returned) │        │
│  │  • Situation Reports (SITREPs) by type and priority              │        │
│  └────────────────────────────┬────────────────────────────────────┘        │
│                               │                                             │
│  ┌────────────────────────────▼────────────────────────────────────┐        │
│  │  🛰️ LifeLine P2P Resource Marketplace                            │        │
│  │  • Citizens list what they HAVE or NEED                          │        │
│  │  • SafeLink™ engine auto-matches within 10km, same category      │        │
│  │  • Both parties notified in-app + WhatsApp                       │        │
│  │  • Glowing connection lines on the LifeLine map                  │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                   PHASE 5: COMMUNITY RESILIENCE & REWARDS                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  🌿 Community Action Hub                                         │        │
│  │  • Disaster-prep drills, environment drives, social events       │        │
│  │  • Join / leave events, track participation                      │        │
│  │  • Eco-Tracker: plastic reduction + carbon savings logging       │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  🏆 Gamification Layer                                           │        │
│  │  • Points: reporting, verification, rescues, eco-activities      │        │
│  │  • Levels: points ÷ 50 + 1                                       │        │
│  │  • Badges: First Reporter, Storm Watcher, AI Verified, Eco …     │        │
│  │  • Leaderboards: Individual, Community, Eco-specific             │        │
│  │  • 500+ points → Government Certificate (view + download)        │        │
│  │  • Social: follow users, comment, like, share reports as reels   │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Cutting Capabilities

| Capability | Description |
|:---|:---|
| **🌐 Multi-Lingual** | Auto-detects language from GPS coordinates. Supports English, Telugu, Tamil, Malayalam, Kannada, Hindi. Manual toggle always available via `/set_language/<lang>`. |
| **📱 Progressive Web App** | Installable on mobile — no app store needed. Works offline via Service Worker caching with app-shell precache and an offline fallback page. |
| **📴 Offline-First Reporting** | Reports composed without connectivity are stored in IndexedDB and auto-flushed to the server the moment the device reconnects. |
| **💬 WhatsApp Integration** | Full bot flow — account linking with password verification, volunteer dispatch, mission navigation links, accept/decline/cancel, status queries. |
| **🎖️ Govt Certification** | Top performers receive official government-recognised certificates with unique certificate IDs, viewable and printable. |
| **🔔 Real-time Notifications** | In-app notification bell with 5-second polling, unread-count API, mark-read, clear-all, and auto-expiring alerts. |
| **🗺️ God Mode 3D Maps** | MapLibre GL renderer with 55° pitch, vignette depth shading, pulsing live-incident dots, and dynamic source/layer management. |
| **📊 Server-Rendered Charts** | Matplotlib generates PNG charts server-side, so analytics work even on low-end devices with no JS charting. |
| **🧾 CSV Audit Sync** | Every report write triggers a sync to `all_reports.csv` and `all_reports_export.csv` for offline audit and government hand-off. |

---

## ✨ Feature Deep-Dive

Sentinel AI ships **28 distinct feature clusters**. Each one is described below with its behaviour, thresholds, and the route or module that implements it.

---

### 🚨 1. Omni-Channel Incident Reporting

A citizen must never be blocked from raising an alarm. Sentinel AI accepts incidents through four fully independent channels.

| Channel | How It Works | Route |
|:---|:---|:---|
| **Online Report (PWA)** | Form-based reporting with photo/video upload, GPS auto-fill, hazard type selection, and instant AI scoring on submit | `POST /report` |
| **Voice SOS Button** | One-tap emergency — captures GPS coordinates, records audio, transcribes it, NLP extracts keywords ("stuck", "water rising", "fire"), auto-categorises hazard, elevates to **Critical** priority | `POST /api/submit_sos` |
| **WhatsApp Bot** | Linked users interact entirely inside WhatsApp — receive alerts, accept missions, get navigation links | `POST /webhook/whatsapp` |
| **Offline AI Calling Agent** | Citizens without internet call the AI agent, which transcribes speech, extracts hazard type and location, and auto-creates a report on their behalf | Integration endpoint |

**Report fields captured:** title, description, hazard type, location string, latitude, longitude, image file, video file, timestamp, author, status, priority.

**Supported hazard types:** `tsunami`, `storm_surge`, `high_waves`, `swell_surge`, `coastal_flooding`, `abnormal_tide`, `cyclone`, `fire`, `medical`, `accident`, `other`.

**Upload constraints:** 16 MB maximum per file; allowed extensions `png`, `jpg`, `jpeg`, `gif`, `mp4`, `mov`, `avi`; filenames sanitised through `secure_filename`.

---

### 🎤 2. Voice SOS with NLP Hazard Extraction

The SOS pipeline is the fastest path from "something is wrong" to a scored incident in the database.

```
User taps SOS
   │
   ▼
Browser MediaRecorder captures audio → speech-to-text transcript
   │
   ▼
POST /api/submit_sos  { transcript, latitude, longitude, timestamp }
   │
   ▼
Keyword map scans transcript:
   tsunami           ← tsunami, wave, sea, ocean, tide, harbor
   storm_surge       ← surge, water rise, flood, overflow, inundation
   high_waves        ← wave, swell, rough sea, high water
   coastal_flooding  ← flood, water, rain, drowning, stuck, entering
   cyclone           ← cyclone, storm, wind, hurricane, typhoon
   fire              ← fire, smoke, burn, flame
   medical           ← injured, blood, ambulance, hurt, pain, doctor, unconscious
   accident          ← crash, accident, collision, hit
   abnormal_tide     ← tide, low water, high water
   │
   ▼
Report created:  priority = "critical",  description = "[VOICE REPORT] …"
   │
   ▼
4-Parameter AI scoring runs immediately → confidence_score + ai_analysis
   │
   ▼
CSV audit sync → report_id returned to the caller
```

**Location fallback chain:** request payload coordinates → the user's saved home location → hard error if neither exists (the database requires coordinates, and an SOS without a location is not actionable).

**Timestamp handling:** ISO-8601 strings are parsed with `Z`-suffix tolerance; malformed timestamps silently fall back to server UTC time so an SOS is never dropped over a formatting issue.

---

### 🤖 3. AI Verification Engine — 4-Parameter Accuracy System™

Every report is scored the instant it lands, with no human in the loop.

| Parameter | Weight | How It Works |
|:---|:---|:---|
| **Heatmap Match** | 25% | Cross-references spatial density of similar reports within ~5.5 km (0.05° box) over a ±24-hour window, counting only `approved` or `pending` reports of the same hazard type |
| **Climate Alignment** | 25% | Queries Open-Meteo — validates that live weather conditions (wind speed, humidity, WMO weather codes) actually support the claimed hazard |
| **User Quality Score** | 25% | Historical credibility — approval rate, total report count, user level, and role-based trust multiplier |
| **Image Processing** | 25% | Sends the reporter's photo to an NVIDIA NIM vision-language model (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` by default, served via OpenRouter, with an automatic fallback to `minimax/minimax-m3:free` if the primary model is saturated), which checks whether the image visually matches the claimed hazard type |

#### Parameter 1 — Heatmap Corroboration Scoring

| Similar Reports Nearby | Score | Interpretation |
|:---|:---|:---|
| ≥ 5 | **0.95** | Strong hazard hotspot confirmed |
| 3–4 | **0.85** | Moderate hotspot |
| 1–2 | **0.70** | Partial corroboration |
| 0 | **0.50** | No corroboration, but plausible — not penalised |
| No coordinates | **0.50** | Heatmap unavailable, neutral score |

#### Parameter 3 — User Quality Scoring

```
quality_score = base_role_score × history_multiplier × level_factor   (capped at 1.0)
```

| Component | Values |
|:---|:---|
| **Base role score** | `official` 0.95 · `analyst` 0.90 · `agency` 0.88 · `citizen` 0.50 |
| **History multiplier** | ≥80% approval → 1.00 · ≥60% → 0.85 · ≥40% → 0.70 · <40% → 0.50 · brand-new user → 0.60 |
| **Level factor** | `min(1.0, (level / 10) × 0.3 + 0.7)` — scales 0.70 → 1.00 |

#### Parameter 4 — Image Processing (NVIDIA NIM)

The uploaded photo is base64-encoded and sent to NVIDIA's hosted NIM vision-language model with a prompt asking it to compare the image against the claimed `hazard_type` and return structured JSON (`matches_hazard`, `confidence`, `detected_hazard`, `reasoning`).

| Condition | Score | Interpretation |
|:---|:---|:---|
| Model confirms match | **model confidence (0–1)** | Photo visually supports the claimed hazard |
| Model detects a different hazard | **confidence × 0.3** | Photo doesn't match the claim — heavily discounted |
| No photo attached | **0.30** | Missing evidence, mildly penalised |
| No `NVIDIA_API_KEY` configured, file missing, timeout, or API error | **0.50** | Neutral fallback — never blocks report submission |

#### Final Classification

| Score | Classification | System Action |
|:---|:---|:---|
| **85–100%** | 🟢 Highly Reliable | **Auto-approved** → alerts dispatched immediately, reporter awarded bonus points |
| **60–84%** | 🟡 Good Confidence | Queued for official review |
| **40–59%** | 🟠 Questionable | Held for investigation |
| **0–39%** | 🔴 Low Confidence | Flagged as potential misinformation |

The full parameter-by-parameter breakdown is exposed to officials through `GET /api/report/<id>/accuracy_4param`, so no approval decision is a black box.

---

### 🛰️ 4. Analyst Dashboard & City Digital Twin

The crown jewel of the platform — a comprehensive analytical command center, gated to `official` and `analyst` roles.

**Live map layers**
- **Esri World Imagery** satellite basemap with 3D pitch
- **RainViewer** real-time precipitation radar overlay
- **Live incident markers** — up to 500 most recent active reports with hazard-typed icons
- **Government hazard overlay** — IMD, NDMA, USGS, GSI, and Tsunami Early Warning feeds with alert-level colour bands (Red / Orange / Yellow)

**TGDPS Government Integration**
- **State-Level Map** — the full Telangana AWS station network, auto-refreshing, served through a sanitising proxy
- **District-Level Map** — 33 selectable districts (Hyderabad, Adilabad, Warangal, and the rest) for ward-level granularity
- The proxy rewrites relative URLs to absolute, injects jQuery only if absent, and strips the government site's headers, footers, and menus so only the map canvas renders inside the dashboard

**Statistics rendered on load**
- Total / pending / approved / rejected report counts
- High-confidence report count (≥ 0.8)
- Hazard-type distribution
- 7-day timeline (grouped in Python for cross-database compatibility)
- Total users and active users (points > 0)

**Server-rendered charts** (matplotlib, `Agg` backend, streamed as PNG)
- `/chart/hazard_distribution` — hazard-type pie chart
- `/chart/reports_timeline` — reports-over-time line chart
- `/chart/user_engagement` — engagement bar chart

---

### 🧪 5. Sentinel Resilience Engine — Predictive Impact Simulation

The simulation dashboard (`/simulation`, `official`/`analyst` only) turns the digital twin into a *what-if* machine.

#### Input Parameters

| Control | Range | Meaning |
|:---|:---|:---|
| **Rainfall slider** | 0 – 300 mm/h | Projected precipitation intensity |
| **Sea-level slider** | 0 – 15 m (0.1 m steps) | Sea-level / storm-surge anomaly |
| **Time horizon** | `Current` · `2030` · `2050` | Climate escalation multiplier (1.0 / 1.25 / 1.6) |

#### Deterministic Impact Model

Every historical report becomes a *vulnerable node*. Each node is scored:

```
hazard_weight   = tsunami 0.8 · storm_surge 0.7 · coastal_flooding 0.6
                  high_waves 0.4 · other 0.3

rain_impact     = (rainfall / 100) × 0.4
sea_impact      = (sea_level / 5)  × 0.6

risk_score      = (hazard_weight × 0.3) + rain_impact + sea_impact ± 0.05 jitter
                  (seeded RNG → identical visuals on every run)

if risk_score > 0.4:
    radius = 200 + (rainfall × 5) + (sea_level × 100)   metres
    → node enters the impact zone set
```

#### Sectoral Damage Forecast

| Sector | Formula (capped at 100%) |
|:---|:---|
| **Power Grid** | `(rainfall × 0.3) + (sea_level × 10) × horizon_multiplier` |
| **Water Supply** | `(rainfall × 0.4) + (sea_level × 5) × horizon_multiplier` |
| **Telecom** | `(rainfall × 0.1) + (sea_level × 15) × horizon_multiplier` |
| **Housing** | `(rainfall × 0.2) + (sea_level × 20) × horizon_multiplier` |

#### Aggregate Metrics

- **People affected** — `(zones × 150 + rainfall × 20) × horizon_multiplier`
- **Critical infrastructure count** — `(zones × 0.4 + sea_level × 5) × horizon_multiplier`
- **Financial risk** — derived exposure figure in millions
- **Evacuation priority** — Critical (>0.8) / High (>0.6) / Moderate
- **Urban Resilience Index estimate** — `100 − mean(power_damage, housing_damage)`

#### LLM-Backed Government Resilience Report

After the deterministic pass, the frontend calls `POST /api/simulate_analysis`, which prompts the **Sentinel Resilience Strategy Engine** — an LLM configured as an Indian urban disaster-risk analyst. It returns a seven-section markdown briefing:

1. **Threat Assessment** — 0–100 severity per sector plus cascade-failure analysis
2. **Evacuation Priority** — level, affected population, corridors, time window
3. **Infrastructure Damage Forecast** — % damage per sector, named at-risk assets
4. **Immediate Action Plan (0–6 hrs)** — four numbered actions with owning departments
5. **Medium-Term Strategy (6–72 hrs)** — coordination and resource steps
6. **Long-Term Resilience** — infrastructure hardening recommendations with cost estimates
7. **Resource Requirements** — personnel, supplies, vehicles, communications assets

> **Cascade modelling is explicit.** The system prompt instructs the engine that Power, Water, Telecom, and Housing are interdependent — a power failure disables water pumping stations, which in turn compromises sanitation. This is what turns a damage estimate into a response plan.

**Graceful degradation:** if the LLM endpoint is unreachable or times out (45 s cap), the platform falls back to `_build_fallback_report()` — a fully deterministic, Telangana-specific resilience briefing that derives its severity bucket, evacuation level, corridors, shelters, at-risk substations, and resource tables from the same simulation parameters. **The simulation never fails silently and never shows an empty report.**

---

### 📢 6. Smart Geo-Fenced Alerts

Alert fatigue kills trust. Sentinel AI targets alerts by hazard physics, not by blanket radius.

| Hazard Type | Alert Radius | Reasoning |
|:---|:---|:---|
| **Storm surge** | 15.0 km | Can push water 30+ km inland across flat terrain |
| **Tsunami** | 10.0 km | Evacuation zone for coastal/low-elevation populations |
| **Coastal flooding** | 5.0 km | Typical inland reach of coastal inundation |
| **Other / unclassified** | 5.0 km | Conservative default |
| **High waves** | 2.0 km | Danger confined to the immediate coast and beaches |
| **Swell surge** | 2.0 km | Hazard limited to the surf zone |
| **Abnormal tide** | 2.0 km | Localised water-level anomaly |

**Alert gating logic** (`should_receive_alert`):
1. Does the user have a home location set? If not → skip.
2. Has the user disabled alerts for this hazard type in their preferences? If so → skip.
3. Is the Haversine distance from user to incident within the hazard's radius? If not → skip.
4. Otherwise → build a hazard-specific message including the formatted distance and dispatch.

**Message payload includes:** hazard emoji and title, the incident location string, safety instructions specific to the hazard type, the distance from the recipient ("3.2 km away"), the incident photo where one exists, and a navigation link.

**Distance formatting** is human-readable: under 1 km renders as metres, under 10 km as one decimal place, above that as whole kilometres.

**Location fallback:** if a user has no home location but is a registered volunteer, their volunteer location is used instead — so responders are never missed.

---

### 📣 7. Global Alert Broadcast Console

For situations where geo-fencing is not the right tool — a state-wide cyclone warning, a mass evacuation order — officials get a dedicated broadcast console from the simulation dashboard.

- Lists every distinct location currently present in the incident database
- Shows total-locations and selected-locations counters live
- Select-all toggle plus per-location checkboxes
- Send button stays disabled until at least one location is selected, preventing accidental empty broadcasts
- Delivered through `POST /send_global_alert` to every user tied to the chosen locations across in-app, WhatsApp, and push channels
- A separate `POST /send_test_warning` route lets operators validate the alerting pipeline end to end without alarming the public

---

### 🚁 8. Uber-Style Volunteer Dispatch

Once a hazard is verified, the Dispatch Agent runs a ride-hailing-style matching cycle.

1. **Query** — find registered, `available` volunteers within the dispatch radius (10 km default)
2. **Match** — filter by declared skills (medical, rescue, logistics, general) and experience level
3. **Rank** — sort by Haversine distance from the incident
4. **Dispatch** — fire a WhatsApp mission card containing the hazard photo, coordinates, severity, and distance
5. **Respond** — the volunteer replies `1` to Accept or `2` to Decline, directly in WhatsApp; the web app offers the same actions
6. **Track** — lifecycle states: `pending → accepted → deployed → completed`, with `declined` and `cancelled` as terminal branches
7. **Verify** — completion requires a photo *and* GPS proof of presence
8. **Reward** — points awarded by experience tier plus a speed bonus

#### Completion Verification Rules

| Check | Rule |
|:---|:---|
| **Identity** | Only the assigned volunteer may complete their own assignment |
| **State** | Only `accepted` assignments can be completed |
| **Photo proof** | Mandatory — request is rejected without a photo URL |
| **GPS proof** | Mandatory — latitude and longitude required |
| **Proximity** | Volunteer must be within **10 km** of the hazard; the API returns the measured distance in the error so the volunteer knows how far off they are |

#### Points Award Formula

```
base_points = 100

experience tier:
    beginner      → 100 points
    intermediate  → 150 points  (1.5×)
    expert        → 200 points  (2.0×)

speed bonus (if completed under 24 h from acceptance):
    bonus = (24 − hours_taken) / 4        → up to +30 points

total = tier_points + speed_bonus
```

The volunteer's `total_rescues` counter and personal points balance both increment, feeding the leaderboards and certificate eligibility.

#### Supporting Dispatch APIs

| Endpoint | Purpose |
|:---|:---|
| `GET /api/coordination/volunteers/match` | Skill-and-distance matching engine |
| `GET /api/coordination/volunteers/nearby` | Radius query for available responders |
| `POST /api/coordination/assign-volunteer` | Create an assignment and fire notifications |
| `GET /api/coordination/assignment/<id>` | Full assignment detail with hazard context |
| `POST /api/coordination/assignment/respond` | Unified accept/decline handler |
| `POST /api/coordination/assignment/<id>/accept` | Explicit accept |
| `POST /api/coordination/assignment/<id>/decline` | Explicit decline |
| `POST /api/coordination/assignment/<id>/complete` | Complete with GPS + photo proof |
| `POST /api/coordination/assignment/<id>/cancel` | Cancel and release the volunteer |
| `GET /api/coordination/assignments/active` | The current user's live mission |
| `GET /api/coordination/emergency/<id>/volunteers-count` | Responder count per emergency |
| `GET /api/coordination/hazard/<type>/<id>/volunteers-count` | Responder count per hazard |

---

### 🤝 9. Inter-Department Coordination Dashboard

This is the direct answer to *"fragmented across departments"*. One dashboard, four linked registries.

#### Agency Registry (`/coordination/agencies`)

| Field | Purpose |
|:---|:---|
| `name`, `type` | Government, NGO, emergency, medical, and other classifications |
| `contact_email`, `contact_phone` | Direct escalation path |
| `resources` (JSON) | What the agency physically holds |
| `capabilities` (JSON) | What the agency can actually do |
| `is_active` | Soft-disable without deleting history |

#### Emergency Events (`/coordination/emergencies`)

Formal, officially declared events — distinct from citizen reports. Carry `hazard_type`, `severity` (low/medium/high/critical), coordinates, an impact `radius_km`, and status (`active` / `resolved` / `cancelled`). Volunteers and resources are assigned against these events.

#### Resource Allocation Ledger (`/coordination/resources`)

Tracks the physical supply chain through four states:

```
allocated  →  deployed  →  used  →  returned
```

Each allocation records the emergency event, the owning agency, resource type (medical / food / shelter / equipment), quantity, units, and the official who authorised it. `GET /api/coordination/resources/status` exposes live inventory posture.

#### Situation Reports — SITREPs (`/coordination/situation-reports`)

Formal field reporting mapped against ongoing emergency events, typed as `damage_assessment`, `resource_status`, `weather`, or `evacuation`, each with a priority level and an authoring official. This is the artefact that makes a response *auditable* after the fact.

#### Emergency Map (`GET /api/coordination/emergency-map`)

A consolidated GeoJSON-style feed of every active emergency, its radius, and the resources and volunteers currently committed to it — the coordination layer of the digital twin.

---

### 🛰️ 10. LifeLine — P2P Emergency Resource Marketplace

When institutional supply chains break down, communities survive by trading with each other. LifeLine formalises that.

**How it works**
1. A user creates a listing marked `have` (donor) or `need` (requester) in a category: medical, food, water, shelter, gear, or transport.
2. The **SafeLink™ matching engine** immediately scans for open listings of the *opposite* type in the *same* category.
3. Any candidate within **10 km** (Haversine) becomes a `ResourceMatch` record.
4. **Both** parties are notified in-app and — if their number is linked — over WhatsApp, with the counterparty's username, item, and location.
5. The **LifeLine Map** (`/lifeline/map`) draws glowing connection lines between matched pairs, turning the mutual-aid network into something you can see.
6. Either party marks the match complete via `/lifeline/complete_match/<id>`, closing both listings.

**Listing states:** `open → matched → completed` (with `cancelled` available). Listings can be flagged **urgent** to sort to the top.

---

### 🌿 11. Community Action Hub

Resilience is built before the disaster, not during it.

- **Event types:** `disaster_prep` (drills, first-aid training), `environment` (beach cleanups, tree planting), `social` (community meetings)
- **Create events** with title, description, type, location, coordinates, date/time, and an optional cover image
- **Join / leave** flows with participant tracking (`registered` → `attended`)
- **Auto-categorisation** on the hub page — upcoming events grouped by type
- **Organiser attribution** — every event is tied to a user, building visible civic reputation
- **Statuses:** `upcoming` → `completed` / `cancelled`

Anyone can register as a volunteer — government employee, NGO member, or unaffiliated citizen. During disasters they assist with evacuation, feeding, and medical aid; between disasters they run environmental initiatives.

---

### ♻️ 12. Eco-Tracker — Plastic Reduction & Carbon Savings

A sustained engagement loop that keeps the citizen network active in peacetime.

#### Plastic Reduction Logging (`/plastic_reduction`)

Users log avoided plastic with an optional photo proof, which is run through an image-analysis pass that produces a verification score.

| Plastic Type | CO₂ per Piece | Assumed Weight |
|:---|:---|:---|
| Plastic bottle | 0.082 kg | 20 g |
| Food container | 0.045 kg | 15 g |
| Cutlery | 0.008 kg | 3 g |
| Plastic bag | 0.006 kg | 5 g |
| Straw | 0.001 kg | 0.5 g |
| Packaging | 0.002 kg/g | weight-based |
| Other | 0.001 kg/g | weight-based |

Quantities can be logged in `pieces`, `grams`, or `kg` — the calculator normalises automatically, using piece-based factors for countable items and weight-based factors for bulk material.

#### Carbon Savings Logging (`/carbon_savings`)

| Activity | Bonus Points |
|:---|:---|
| Tree planting | +15 |
| Cycling | +8 |
| Waste recycling | +6 |
| Plastic reduction | +5 |
| Energy saving | +4 |
| Public transport | +3 |
| Water saving | +3 |
| Other | +2 |

```
points = max(5, int(carbon_saved_kg × 10) + activity_bonus)
unverified activities earn half the base points
```

#### Eco Achievement Levels

Progression is driven by cumulative verified CO₂ saved: **Eco Beginner → Eco Enthusiast → Green Champion → Climate Hero**.

#### Eco Endpoints

| Route | Purpose |
|:---|:---|
| `GET /eco_tracker` | Personal dashboard — totals, streaks, impact equivalents |
| `GET/POST /plastic_reduction` | Log plastic avoided, upload proof |
| `GET/POST /carbon_savings` | Log an eco-friendly activity |
| `GET /api/eco_stats` | JSON statistics feed |
| `GET /eco_leaderboard` | Eco-specific rankings |

---

### 🏆 13. Gamification, Badges & Levels

| Element | Details |
|:---|:---|
| **Points** | Earned for reporting, verification, rescues, and eco-activities |
| **Levels** | `level = points ÷ 50 + 1` — recalculated on every points change |
| **Badges** | Awarded automatically when their criteria are met |
| **Leaderboards** | Individual (top 20), community, and eco-specific rankings |
| **Social proof** | Badges and level are displayed on public profiles |

#### Badge Catalogue

| Badge | Icon | Criterion |
|:---|:---|:---|
| **First Reporter** | 🚀 | Submitted your first report |
| **Storm Watcher** | ⛈️ | Reported 3 storm surges |
| **Verified Observer** | ✅ | Had 5 reports verified |
| **AI Verified** | 🤖 | Submitted a high-confidence AI-verified report |
| **Community Guardian** | 🛡️ | Reached 100 points |
| **Plastic Warrior** | ♻️ | Reduced 1 kg of plastic (verified) |
| **Carbon Neutral** | 🌱 | Saved 100 kg of CO₂ (verified) |
| **Green Commuter** | 🚲 | Used eco transport 10 times (verified) |
| **Eco Champion** | 🏆 | Earned 500 eco points |

Badge checks run automatically after any points-changing action, so a user is never left waiting for a nightly job to recognise their contribution.

---

### 🎖️ 14. Government Certification

Top contributors receive an official, printable certificate of recognition.

| Aspect | Detail |
|:---|:---|
| **Eligibility** | 500 points minimum |
| **Certificate ID** | `SH-CRT-<user_id>-<YYYYMMDD>` (view) / `MAXALERT-<user_id>-<YYYYMMDD>` (download) |
| **Displayed data** | Username, completed rescue count, issue date, unique certificate ID |
| **Access control** | Users may download only their own certificate; admins may download any |
| **Ineligible users** | Redirected to their profile with a progress-encouraging message rather than a hard error |
| **Routes** | `GET /certificate/<user_id>` (view) · `GET /certificate/download/<user_id>` (print-optimised) |

---

### 📊 15. Leaderboards

| Leaderboard | Route | Ranking Basis |
|:---|:---|:---|
| **Individual** | `/leaderboard` · `GET /api/leaderboard` | Top 20 users by total points |
| **Community** | `/community_leaderboard` · `GET /api/community_leaderboard` | All users ranked by combined contribution |
| **Eco** | `/eco_leaderboard` | Verified carbon savings and plastic reduction |
| **Combined hub** | `/leaderboards` | All boards in one view |
| **Personal rank** | `GET /api/leaderboard/user/<user_id>` | An individual's position and percentile |

---

### 👥 16. Social Layer

Disaster response is a social act. The platform treats it as one.

| Feature | Route | Behaviour |
|:---|:---|:---|
| **Follow / Unfollow** | `/follow/<username>` · `/unfollow/<username>` | Build a personal network of trusted reporters |
| **Followers / Following** | `/user_followers/<username>` · `/user_following/<username>` | Browse network graphs |
| **Public profiles** | `/profile/<username>` | Points, level, badges, report history |
| **Profile editing** | `/edit_profile` | Bio, profile image, preferences |
| **Comments** | `POST /api/report/<id>/comment` · `GET /api/report/<id>/comments` | Threaded discussion on incidents |
| **Local Approval** | `POST /api/report/<id>/local_approve` | Neighbourhood-level "I can confirm this" endorsement — crowd verification distinct from official approval |
| **View tracking** | `POST /api/report/<id>/view` | Deduplicated view counting |
| **Sharing** | `POST /api/report/<id>/share` · `/share` | Share counters and shareable app links |
| **Reels** | `/reels` | Vertical, scrollable feed of report media — awareness through a familiar format |
| **User report feed** | `/user/<username>/reports` | Everything a given user has reported |

Every report carries live `likes_count`, `comments_count`, `shares_count`, `views_count`, and an `is_local_verified` flag.

---

### 🔔 17. Notification System

| Capability | Detail |
|:---|:---|
| **In-app bell** | Polls every 5 seconds for unread count |
| **Alert flag** | `is_alert` distinguishes hazard alerts from routine notifications |
| **Assignment linkage** | Notifications can carry a `report_id` or `assignment_id` for one-tap navigation |
| **Expiry** | `expires_at` lets time-sensitive alerts self-retire |
| **Push tokens** | `POST /api/register_push_token` registers Firebase Cloud Messaging tokens |
| **Per-hazard preferences** | `/alert_preferences` lets users mute hazard types they don't care about |
| **Bulk clear** | `POST /clear_all_notifications` |

**Notification routes:** `GET /api/notifications` · `GET /notifications` · `POST /api/notification/<id>/read` · `POST /notification/<id>/read` · `GET /api/notifications/unread-count` · `POST /clear_all_notifications`

---

### 🌐 18. Multi-Lingual Support

| Language | Code | Detection Method |
|:---|:---|:---|
| English | `en` | Default |
| Hindi | `hi` | GPS-detected (Hindi belt coordinates) |
| Telugu | `te` | GPS-detected (Telangana / Andhra Pradesh) |
| Tamil | `ta` | GPS-detected (Tamil Nadu) |
| Malayalam | `ml` | GPS-detected (Kerala) |
| Kannada | `kn` | GPS-detected (Karnataka) |

- `detect_preferred_language(latitude, longitude)` maps coordinates to the regional language on first load
- The chosen locale is stored on the `User` record and in the session, then injected into every template through a Flask context processor
- `/set_language/<lang>` allows manual override at any time
- **All 25 WTForms classes extend `MultilingualForm`**, so form labels, placeholders, and validation errors are translated too — not just page copy
- Translation tables live in `translations.py` with a `get_translation(lang, key, default)` lookup that falls back gracefully rather than showing a raw key

---

### 📱 19. Progressive Web App & Offline-First Reporting

#### PWA Shell

- **Installable** — full Web App Manifest with 8 icon sizes (72 px → 512 px), all `any maskable`
- **Standalone display**, portrait-primary orientation, `#0f172a` background, `#1a365d` theme colour
- **App shortcuts** — long-press the installed icon for direct "Report Emergency" and "View Dashboard" jumps
- **Categories** declared as emergency, safety, utilities
- **Service Worker** (`/sw.js`) precaches the app shell, cleans stale caches on activate, and calls `skipWaiting()` for immediate updates
- **Offline fallback page** at `/offline.html`

#### Offline Sync Manager

`static/js/offline-sync.js` implements a genuine offline-first pipeline:

```
Device goes offline
   │
   ▼
User submits a report as normal
   │
   ▼
Report serialised → IndexedDB store "pending_reports" (db: sentinel_offline_db)
   │
   ▼
Persistent UI indicator shows pending count + offline banner
   │
   ▼
Connectivity returns (online event)
   │
   ▼
Queue drains automatically → each report POSTed to the server
   │
   ▼
Successful items removed from IndexedDB, pending count updates
```

This is the difference between a disaster app that works and one that goes blank exactly when it matters.

---

### 💬 20. WhatsApp Bot Integration

A complete conversational interface — for many users, the *only* interface they will ever use. See the [full flows](#-whatsapp-bot) below.

| Capability | Detail |
|:---|:---|
| **Account linking** | Two-step username → password verification against the hashed credential store |
| **Session state** | Multi-step conversation state persisted in `User.whatsapp_session` as JSON |
| **Number normalisation** | Handles `+91…` and `91…` variants so linking never fails on formatting |
| **Mission cards** | Hazard title, description snippet, location, raw coordinates, Google Maps navigation link, and the incident photo as media |
| **Accept / Decline** | Reply `1` / `accept` / `yes` or `2` / `reject` / `decline` / `no` |
| **Cancel** | Reply `cancel` or `abort` — releases the volunteer and notifies the coordinator both in-app and over WhatsApp |
| **Status** | Reply `status` or `hi` for a live account and monitoring summary with a dashboard deep link |
| **Media delivery** | Incident photos attached to the same message as the mission brief |
| **Setup guide** | Built-in walkthrough at `/whatsapp-setup`, plus the `setup_whatsapp.sh` helper script |

---

### 🗺️ 21. God Mode 3D Maps

`static/js/god-mode-maps.js` wraps MapLibre GL in a reusable `GodModeMap` class used across the hero map, analyst dashboard, simulation, and LifeLine views.

| Feature | Implementation |
|:---|:---|
| **Cinematic default camera** | 55° pitch, −12.5° bearing, antialiasing on |
| **Depth vignette** | Inset box-shadow overlay for 3D depth without harsh glow filters |
| **Pulsing live dots** | Custom animated GL marker image for live incidents |
| **Deferred operations queue** | Layer/source calls issued before map load are queued and replayed on `load` — no race conditions |
| **Dynamic layer management** | Tracked `addedSources` / `addedLayers` / `popups` arrays enable clean teardown between simulation runs |
| **Live UI badge** | Optional "LIVE" indicator overlay |
| **Basemap** | CARTO Voyager GL style, centred on India (78.9°E, 20.5°N) at zoom 4 by default |

---

### 🌡️ 22. Live Climate Panel on the Hero Map

A real-time climate widget overlaid directly on the homepage's full-screen map.

| Metric | Source | Update Behaviour |
|:---|:---|:---|
| **Temperature (°C)** | Open-Meteo `/v1/forecast` | On geolocation lock |
| **Weather condition** | WMO weather codes → emoji + label (Clear, Rain, Thunderstorm, …) | On geolocation lock |
| **Humidity (%)** | Open-Meteo `hourly.relativehumidity_2m` | On geolocation lock |
| **Wind (km/h)** | Open-Meteo `current_weather.windspeed` | On geolocation lock |
| **US AQI** | Open-Meteo Air Quality `/v1/air-quality` | On geolocation lock |
| **AQI category & colour band** | Computed locally — Good 🟢 / Moderate 🟡 / Unhealthy 🟠🔴 / Very Unhealthy 🟣 / Hazardous ⚫ | On AQI fetch |

- **Smart fallback** — if geolocation is denied, defaults to Hyderabad (17.385°N, 78.487°E)
- **Glassmorphism design** — blurred dark glass card pinned to the top-right of the map
- **Animated AQI meter** — fills horizontally in the category colour
- **Zero-cost APIs** — both Open-Meteo endpoints are free and key-less
- **No extra permission prompt** — piggybacks on the map's existing geolocation request

---

### 💬 23. On-Map Flash Notification Popups

Flask flash messages ("Language changed to EN", "Report submitted successfully") are intercepted and rendered as **floating glass popups** over the map instead of being pushed below the fold.

- Slides down from the top-centre of the map with a fade animation
- Auto-dismisses after 5 seconds
- Glass-backed styling consistent with the rest of the hero UI
- Only Flask-flashed alerts (`.alert-dismissible`) are intercepted — the persistent **Sentinel AI ACTIVE** status pill stays put

---

### 🖥️ 24. Full-Screen Responsive Layout

The entire application uses the **full screen width** on every page — no narrow centred columns.

- Removed the legacy `col-xl-8` 66%-width cap from `base.html`
- All dashboards (Analyst, Coordination, Simulation, user Dashboard, Hazard Reports) stretch edge-to-edge
- The hero map is a true `100vh × 100vw` canvas with the navbar floating over it — no gap between navbar and map
- Comfortable `1.5rem` side gutters preserved on data-heavy pages
- Breakpoints at 400 px, 576 px, 768 px, 992 px, and 1200 px maintain readability from phone to command-room display wall

---

### 📋 25. Report Lifecycle & Moderation

A report's full life is modelled explicitly, and every state transition is recorded.

```
   SUBMITTED
      │  AI scores confidence
      ├── ≥ 85% ──► AUTO-APPROVED ──► alerts dispatched ──► +30 points to reporter
      │
      └── < 85% ──► PENDING
                       │
              ┌────────┴────────┐
              ▼                 ▼
          APPROVED           REJECTED
        (+20 points,      (reason recorded,
         alerts fire)      scheduled_deletion set)
              │                 │
              ▼                 ▼
          RESOLVED       grace window ──► purge
                                 │
                                 └─ /cancel_deletion/<id> restores it
```

| Moderation Capability | Route |
|:---|:---|
| Approve / reject with AI breakdown visible | `POST /verify_report/<id>` |
| Reject with a recorded, structured reason | `GET/POST /reject_report/<id>` |
| Delete a report | `POST /delete_report/<id>` |
| Cancel a scheduled deletion | `POST /cancel_deletion/<id>` |
| Automatic purge of expired rejected reports | `delete_scheduled_reports()` background job |
| Full report detail with media and comments | `GET /view_report/<id>` |

`verified`, `verified_by`, and `verified_at` are stamped on every approval, so accountability for each decision is permanent.

---

### 🧾 26. Audit Trail & CSV Data Export

Every write to the report table triggers `sync_reports_to_csv()`, mirroring the full dataset into `all_reports.csv` and `all_reports_export.csv`.

- Survives database corruption or migration failure — the CSV is a parallel record
- Hands off cleanly to government systems that expect spreadsheets, not APIs
- Enables offline analysis by officials with no database access
- Written synchronously on report creation and status change, so it never lags the live system

---

### ⏱️ 27. Background Job Scheduler

APScheduler runs the platform's autonomous housekeeping, registered at startup and shut down cleanly through `atexit`.

| Job | Purpose |
|:---|:---|
| **Scheduled report deletion** | Purges rejected reports once their grace window expires |
| **Weather pre-fetching** | Warms weather data so dashboards render instantly |
| **Alert expiry processing** | Retires notifications past their `expires_at` |
| **Badge & level reconciliation** | Ensures gamification state stays consistent |

---

### 🧰 28. Administrative & Operational Utilities

Purpose-built endpoints that make demos, deployments, and field debugging survivable.

| Route | Purpose |
|:---|:---|
| `GET /repair-database-2026` | Runs schema repair for missing columns after a migration gap |
| `GET /create-official-account` | Bootstraps the first official account on a fresh deployment |
| `GET /check-users` | Lists registered users and roles for verification |
| `GET /elevate-user/<email>/<role>` | Promotes a user to `official`, `analyst`, or `agency` |
| `GET /force-logout` | Clears a stuck session |
| `GET /debug_users` | Diagnostic user dump |
| `GET /uploads/<filename>` | Serves user-uploaded media |
| `POST /api/upload` | Generic authenticated file upload for completion proofs |
| `GET /get_location` | Location helper for the client |
| `GET/POST /set_location` | Set the home location that drives geo-fenced alerting |
| `GET /search` · `GET /api/search` | Full-text search across reports with trending-hazard suggestions |
| `GET /rescue-complete` | Rescue completion confirmation view |
| `GET /about` | Platform information page |

> ⚠️ **Production note:** the bootstrap and elevation utilities above are unauthenticated conveniences for hackathon and demo environments. Gate them behind an admin token or remove them before any public deployment. See [Security](#-security).

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER / PWA CLIENT                             │
│                                                                          │
│  Bootstrap 5 · Glassmorphism CSS · Leaflet.js · MapLibre GL · Chart.js   │
│  Service Worker (offline shell) · Web App Manifest (add-to-homescreen)   │
│  IndexedDB offline report queue · Online/offline event listeners         │
│  Language: auto-detected by GPS · Notification polling every 5s          │
│  Voice SOS: MediaRecorder API + NLP keyword extraction                   │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTPS
                             │
┌────────────────────────────▼─────────────────────────────────────────────┐
│                        FLASK APPLICATION                                  │
│                     (Port 5001 · 119 Routes · ~5,950 Lines)              │
│                                                                           │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────┐ ┌─────────────┐   │
│  │ 🔍 Detection  │ │ 📋 Prioritize  │ │ 🚁 Dispatch  │ │ 📡 Alert    │   │
│  │    Agent      │ │    Agent       │ │    Agent     │ │    Agent    │   │
│  │ 3-Param AI    │ │ Auto-approval  │ │ 10km Geo-Q   │ │ Geo-fencing │   │
│  │ NLP + SOS     │ │ Severity rank  │ │ WhatsApp bot │ │ Multi-lang  │   │
│  └───────┬───────┘ └───────┬────────┘ └──────┬───────┘ └──────┬──────┘   │
│          │                 │                 │                │           │
│  ┌───────┴─────────────────┴─────────────────┴────────────────┴───────┐   │
│  │ 📊 Analytics Agent            🤝 Coordination Agent                │   │
│  │ Charts · URI · TGDPS proxy    Agencies · Resources · SITREPs       │   │
│  └───────────────────────────────┬────────────────────────────────────┘   │
│                                  │                                        │
│  ┌───────────────────────────────▼────────────────────────────────────┐   │
│  │                     SQLAlchemy ORM (23 Models)                     │   │
│  │                                                                    │   │
│  │  sqlite:///site.db  (development)                                  │   │
│  │  postgresql://...   (production — Render / Heroku / AWS)           │   │
│  │  Flask-Migrate (Alembic) manages every schema change               │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    APScheduler Background Jobs                        │ │
│  │  • Scheduled report purge     • Weather data pre-fetching             │ │
│  │  • Alert expiry processing    • Badge / level reconciliation          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │              Utility Layer (utils.py · translations.py)               │ │
│  │  3-Param validator · Haversine · Twilio sender · Geo-fence rules      │ │
│  │  Carbon calculator · CSV audit sync · 6-language translation tables   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────┬──────────────┬──────────────┬──────────────┬────────────────┘
             │              │              │              │
   ┌─────────▼──────┐ ┌────▼─────────┐ ┌──▼───────────┐ ┌▼───────────────┐
   │  Twilio API    │ │ Open-Meteo   │ │ TGDPS Gov    │ │ RainViewer     │
   │  WhatsApp msgs │ │ Weather +    │ │ Live Rainfall│ │ Satellite Radar│
   │  Inbound hooks │ │ Air Quality  │ │ Map Proxy    │ │ Precipitation  │
   │  Media attach. │ │ (free, keyless)│ (State+Dist) │ │ Overlay API    │
   └────────────────┘ └──────────────┘ └──────────────┘ └────────────────┘
             │              │              │              │
   ┌─────────▼──────────────▼──────────────▼──────────────▼──────────────┐
   │  Sentinel LLM — Resilience Strategy Engine (simulation briefings)   │
   │  Nominatim (OpenStreetMap) — reverse geocoding for hero location    │
   │  Esri World Imagery — satellite tiles for the hero map              │
   │  Firebase Cloud Messaging (optional) — push notifications           │
   │  Chatbase — embedded AI support assistant iframe                    │
   │  IMD · NDMA · USGS · GSI · Tsunami Early Warning — hazard feeds      │
   └─────────────────────────────────────────────────────────────────────┘
```

### Architectural Principles

| Principle | How It Shows Up |
|:---|:---|
| **Never lose a report** | Four ingestion channels, IndexedDB offline queue, CSV mirror on every write, timestamp fallbacks |
| **Never block on an external service** | LLM has a deterministic fallback report; weather failures score neutral (0.50) rather than failing validation; TGDPS proxy errors return a readable message |
| **Degrade, don't crash** | Missing coordinates, missing images, missing weather, and missing history all have defined neutral behaviours |
| **Cross-database compatibility** | Timeline grouping is done in Python, not SQL, so SQLite and PostgreSQL behave identically |
| **Explainable AI** | Every confidence score exposes its three sub-scores and a human-readable analysis string |
| **Role-gated by default** | Analyst, simulation, coordination, and moderation surfaces all check `current_user.role` before rendering |

---

## 🔀 Data Flow Sequences

### Sequence A — Citizen Report to Dispatched Volunteer

```
 1. Citizen           POST /report  (title, description, hazard, photo, GPS)
 2. Flask             save_file() → sanitised filename in static/uploads/
 3. Detection Agent   analyze_report_with_ai(report)
 4.   ├─ _validate_heatmap_match()        → 0.00–0.95  (33%)
 5.   ├─ _validate_climate_alignment()    → Open-Meteo (33%)
 6.   └─ _calculate_user_quality_score()  → role × history × level (34%)
 7. Prioritization    weighted score ≥ 0.85 ?
 8.   ├─ YES → verification_status = "approved", +30 pts, alerts fire now
 9.   └─ NO  → verification_status = "pending", queued for official
10. Alert Agent       send_hazard_alerts(report)
11.   └─ for each user: home coords → Haversine → within hazard radius?
12.        → in-app Notification + WhatsApp message + photo media
13. Dispatch Agent    query available volunteers in radius, rank by distance
14.   └─ create VolunteerAssignment(status="pending")
15.        → WhatsApp mission card with coords + Google Maps link
16. Volunteer         replies "1" → status="accepted", accepted_at stamped
17. Volunteer         arrives, POSTs completion with photo + GPS
18.   └─ distance check ≤ 10 km, else 400 with measured distance
19.        → status="completed", points awarded, total_rescues++
20. Audit             sync_reports_to_csv() mirrors state to CSV
```

### Sequence B — Simulation to Government Briefing

```
 1. Analyst      moves rainfall + sea-level sliders, picks time horizon
 2. Frontend     POST /api/simulate_impact  { rainfall, sea_level, time_horizon }
 3. Backend      seeded RNG → deterministic per-node risk scores
 4.              nodes with risk > 0.4 become impact zones with computed radii
 5.              sectoral damage computed for Power / Water / Telecom / Housing
 6.              aggregate stats: people affected, infra count, financial risk
 7. Response     { zones[], stats{}, llm_params{} }
 8. Frontend     renders impact circles + sector damage bars on the 3D map
 9. Frontend     POST /api/simulate_analysis  { …llm_params }
10. Backend      build_resilience_prompt() → Sentinel LLM (45 s timeout)
11.   ├─ SUCCESS → 7-section markdown government briefing
12.   └─ FAILURE → _build_fallback_report() deterministic briefing
13. Frontend     renders the briefing beneath the map — never blank
```

### Sequence C — Offline Report Recovery

```
 1. Device loses connectivity mid-disaster
 2. offline-sync.js  detects the "offline" event → banner + pending badge
 3. Citizen          fills the report form as normal and submits
 4. Handler          serialises payload → IndexedDB "pending_reports"
 5. UI               pending count increments; user gets clear confirmation
 6. Connectivity returns → "online" event fires
 7. Queue drains     each stored report POSTed in order
 8. On 2xx           record deleted from IndexedDB, count decrements
 9. Server           each recovered report runs the full AI pipeline as usual
```

### Sequence D — WhatsApp Account Linking

```
 1. User      sends "hi" from an unlinked number
 2. Bot       "Please enter your username"
 3. User      "john_doe"
 4. Backend   case-insensitive, whitespace-trimmed username lookup
 5. Backend   User.whatsapp_session = {"phone": …, "step": "awaiting_password"}
 6. Bot       "Please enter your password to confirm"
 7. User      "••••••••"
 8. Backend   check_password_hash() against the stored hash
 9.   ├─ MATCH    → whatsapp_number linked, session cleared, success message
10.   └─ MISMATCH → "Incorrect password", session retained for a retry
```

---

## 📁 Project Structure

```
sentinel-ai/
│
├── app.py                  # Main Flask application — 119 routes, ~5,950 lines
│                           # All business logic, AI engines, WhatsApp handler,
│                           # background jobs, TGDPS proxy, multilingual tables,
│                           # simulation engine, LLM integration
│
├── models.py               # SQLAlchemy ORM — 23 database models (~880 lines)
│
├── forms.py                # WTForms — 25 validated, multilingual form classes
│
├── utils.py                # Core utility library (~815 lines):
│                           #  - 4-Parameter AI validation engine
│                           #  - Haversine distance calculator
│                           #  - WhatsApp / Twilio message sender
│                           #  - SMS alert sender
│                           #  - Per-hazard geo-fence radius rules
│                           #  - Carbon savings + eco points calculators
│                           #  - Plastic image analysis
│                           #  - CSV audit sync
│
├── translations.py         # Multilingual string tables (6 languages)
├── config.py               # Environment-aware Flask configuration
├── list_admins.py          # Helper: list admin/official accounts
├── requirements.txt        # Python dependencies (19 packages)
├── Procfile                # Heroku/Render entry point — `gunicorn app:app`
├── start_system.sh         # Helper: start app + ngrok tunnel guidance
├── setup_whatsapp.sh       # Twilio WhatsApp sandbox setup script
├── FRONTEND.md             # Frontend design + component documentation
├── all_reports.csv         # Live CSV mirror of the report table (audit)
├── all_reports_export.csv  # Export-formatted CSV mirror
│
├── static/
│   ├── css/
│   │   ├── style.css           # Global stylesheet (glassmorphism, animations)
│   │   └── image-fix.css       # Media rendering corrections
│   ├── js/
│   │   ├── script.js           # Core frontend bootstrap
│   │   ├── god-mode-maps.js    # MapLibre GL 3D map engine (GodModeMap class)
│   │   ├── analyst_dashboard.js# TGDPS live map refresh + district selector
│   │   ├── offline-sync.js     # IndexedDB offline report queue + sync
│   │   └── pwa.js              # Service Worker registration + install prompt
│   ├── sw.js                   # Service Worker (offline app-shell caching)
│   ├── manifest.json           # PWA manifest (8 icon sizes, shortcuts)
│   ├── icons/                  # PWA app icons (72 → 512 px)
│   └── uploads/                # User-uploaded photos and videos
│
├── templates/                  # 50 Jinja2 HTML templates
│   ├── base.html                   # Global layout, navbar, notification bell
│   ├── index.html                  # Landing page + full-screen hero map
│   ├── about.html                  # Platform information
│   ├── register.html · login.html  # Authentication
│   ├── profile.html · edit_profile.html
│   ├── user_followers.html · user_following.html
│   ├── report.html                 # Hazard submission form
│   ├── view_report.html            # Report detail + comments + AI breakdown
│   ├── reject_report.html          # Structured rejection flow
│   ├── dashboard.html              # Main user dashboard
│   ├── analyst_dashboard.html      # Analyst command centre + TGDPS maps
│   ├── simulation.html             # Sentinel Resilience Engine UI
│   ├── coordination_dashboard.html # Inter-department coordination
│   ├── agency_management.html · new_agency.html
│   ├── emergency_management.html · new_emergency.html
│   ├── resource_management.html
│   ├── volunteer_management.html · register_volunteer.html
│   ├── situation_reports.html · new_situation_report.html
│   ├── rescue_completion.html      # GPS + photo proof capture
│   ├── lifeline.html · lifeline_map.html · create_listing.html
│   ├── community_hub.html · create_community_event.html
│   ├── community_event_card.html
│   ├── eco_tracker.html · plastic_reduction.html · carbon_savings.html
│   ├── eco_leaderboard.html
│   ├── leaderboard.html · leaderboards.html · community_leaderboard.html
│   ├── certificate_view.html · certificate_download.html
│   ├── notifications.html · alert_preferences.html
│   ├── set_location.html · search.html · reels.html
│   ├── whatsapp_setup.html · offline.html · debug_users.html
│   └── partials/language_selector.html
│
├── migrations/                 # Flask-Migrate (Alembic) migrations
│   └── versions/
│       ├── 0391715ef3c0_initial_migration.py
│       ├── 8b8777ac801a_add_status_and_priority_to_report.py
│       ├── 5f66bb321e7d_add_alert_system_fields.py
│       ├── 26b3b232e047_add_user_location_and_notification_.py
│       ├── ec15d6b69125_add_urban_resilience_index_tables.py
│       ├── add_notification_assignment.py
│       ├── add_rescue_completion_fields.py
│       ├── add_volunteer_assignment_columns.py
│       └── volunteer_assignment_updates.py
│
└── instance/                   # SQLite database files (gitignored)
```

---

## 🗄️ Database Schema

The application uses **23 SQLAlchemy models** managed through Flask-Migrate.

### Core Models

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE MODELS                                    │
├──────────────────┬──────────────────────────────────────────────────────┤
│ User             │ id · username · email · password (hashed) · role      │
│                  │ profile_image · bio · points · level · created_at     │
│                  │ language · home_latitude · home_longitude             │
│                  │ whatsapp_number (unique) · whatsapp_session (JSON)    │
│                  │ alert_preferences (JSON) · push_token                 │
│                  │ Methods: follow() · unfollow() · is_following()       │
│                  │          get/set_alert_preferences() · to_dict()      │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Report           │ id · title · description · hazard_type · location     │
│                  │ latitude · longitude · image_file · video_file        │
│                  │ timestamp · user_id · status · priority               │
│                  │ alert_radius · alert_sent · alert_sent_at             │
│                  │ verified · confidence_score · ai_analysis             │
│                  │ verification_status · rejection_reason                │
│                  │ scheduled_deletion · verified_by · verified_at        │
│                  │ likes/comments/shares/views_count · is_local_verified │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Badge            │ id · name · description · icon · points_required      │
├──────────────────┼──────────────────────────────────────────────────────┤
│ UserBadge        │ id · user_id · badge_id · earned_at                   │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Notification     │ id · user_id · message · report_id · assignment_id    │
│                  │ is_read · is_alert · created_at · expires_at          │
├──────────────────┼──────────────────────────────────────────────────────┤
│ followers        │ association table — follower_id ↔ followed_id         │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Social Engagement Models

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ Like             │ id · user_id · report_id · timestamp                  │
│ Comment          │ id · user_id · report_id · text · timestamp           │
│ ReportView       │ id · user_id · report_id · timestamp                  │
│ LocalApproval    │ id · user_id · report_id · timestamp                  │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Coordination Models

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ Agency           │ id · name · type · contact_email · contact_phone      │
│                  │ resources (JSON) · capabilities (JSON) · is_active    │
├──────────────────┼──────────────────────────────────────────────────────┤
│ EmergencyEvent   │ id · title · description · hazard_type · severity     │
│                  │ location · latitude · longitude · radius_km           │
│                  │ status · created_by · created_at · updated_at         │
├──────────────────┼──────────────────────────────────────────────────────┤
│ ResourceAllocation │ id · emergency_event_id · agency_id                 │
│                  │ resource_type · quantity · units · status             │
│                  │ allocated_by · created_at · updated_at                │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Volunteer        │ id · user_id (unique) · skills (JSON) · availability  │
│                  │ experience_level · certifications (JSON) · location   │
│                  │ latitude · longitude · is_verified                    │
│                  │ points · total_rescues · created_at                   │
├──────────────────┼──────────────────────────────────────────────────────┤
│ VolunteerAssignment │ id · volunteer_id · emergency_event_id             │
│                  │ hazard_type ("emergency" | "report") · role · status  │
│                  │ assigned_by · assigned_at · accepted_at · completed_at│
│                  │ distance_km · completion_photo · completion_notes     │
│                  │ points_earned                                         │
├──────────────────┼──────────────────────────────────────────────────────┤
│ SituationReport  │ id · emergency_event_id · title · content             │
│                  │ priority · report_type · created_by · created_at      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Sustainability Models

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ PlasticUsage     │ id · user_id · date · plastic_type · quantity · unit  │
│                  │ image_proof · description · verified                  │
│                  │ verification_score · points_earned                    │
├──────────────────┼──────────────────────────────────────────────────────┤
│ CarbonSavings    │ id · user_id · date · activity_type · carbon_saved    │
│                  │ description · proof_type · proof_file                 │
│                  │ verified · points_earned                              │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Community & Mutual-Aid Models

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ CommunityEvent   │ id · title · description · event_type · location      │
│                  │ latitude · longitude · date_time · organizer_id       │
│                  │ status · image_file · created_at                      │
├──────────────────┼──────────────────────────────────────────────────────┤
│ EventParticipant │ id · user_id · event_id · joined_at · status          │
├──────────────────┼──────────────────────────────────────────────────────┤
│ ResourceListing  │ id · user_id · listing_type ("have"|"need")           │
│                  │ category · title · description · quantity             │
│                  │ location · latitude · longitude · status · urgent     │
├──────────────────┼──────────────────────────────────────────────────────┤
│ ResourceMatch    │ id · need_id · have_id · status · created_at          │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Urban Resilience Index Models

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ ResilienceZone   │ id · zone_identifier (unique, e.g. "grid_17.5_78.5")  │
│                  │ zone_type (grid | ward | city | coastal_segment)      │
│                  │ center_latitude · center_longitude                    │
│                  │ bounds_geojson · display_name · created_at            │
├──────────────────┼──────────────────────────────────────────────────────┤
│ ResilienceScore  │ id · zone_id · score (0–100) · trend                  │
│                  │ calculation_period (30d | 90d) · calculated_at        │
│                  │ metrics_json (breakdown of contributing factors)      │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Entity Relationships

```
User ──1:N──► Report ──1:N──► Comment / Like / ReportView / LocalApproval
 │                │
 │                └──1:N──► Notification
 │
 ├──1:1──► Volunteer ──1:N──► VolunteerAssignment ──N:1──► EmergencyEvent
 │
 ├──1:N──► PlasticUsage · CarbonSavings
 ├──1:N──► CommunityEvent (as organiser) ──1:N──► EventParticipant
 ├──1:N──► ResourceListing ──N:N──► ResourceMatch (need ↔ have)
 ├──N:N──► User (followers association table)
 └──1:N──► UserBadge ──N:1──► Badge

Agency ──1:N──► ResourceAllocation ──N:1──► EmergencyEvent ──1:N──► SituationReport

ResilienceZone ──1:N──► ResilienceScore  (time series per zone)
```

---

## 🎮 User Roles & Permissions

| Role | Who | Key Permissions |
|:---|:---|:---|
| `citizen` | General public | Submit reports, raise SOS, join LifeLine, log eco-activities, earn points, join community events, follow users, comment |
| `volunteer` | Registered responders | Everything a citizen can do, plus: accept rescue missions, complete assignments with proof, earn rescue points, appear in dispatch queries |
| `official` | Government officers | Approve/reject reports, create emergency events, assign volunteers, allocate resources, file SITREPs, send global alerts, access analyst + simulation dashboards |
| `analyst` | Data scientists / planners | Full access to analyst dashboard, Sentinel Resilience Engine, TGDPS maps, URI data, all analytics and charts |
| `agency` | NGO / emergency organisation | Manage agency resources, create SITREPs, coordinate cross-department responses |

### Permission Matrix

| Capability | citizen | volunteer | official | analyst | agency |
|:---|:---:|:---:|:---:|:---:|:---:|
| Submit report / SOS | ✅ | ✅ | ✅ | ✅ | ✅ |
| Receive geo-fenced alerts | ✅ | ✅ | ✅ | ✅ | ✅ |
| Comment, like, follow, local-approve | ✅ | ✅ | ✅ | ✅ | ✅ |
| LifeLine listings & matches | ✅ | ✅ | ✅ | ✅ | ✅ |
| Eco-tracker & leaderboards | ✅ | ✅ | ✅ | ✅ | ✅ |
| Accept & complete missions | ❌ | ✅ | ✅ | ❌ | ✅ |
| Approve / reject reports | ❌ | ❌ | ✅ | ❌ | ❌ |
| Create emergency events | ❌ | ❌ | ✅ | ❌ | ✅ |
| Assign volunteers | ❌ | ❌ | ✅ | ❌ | ✅ |
| Allocate resources / file SITREPs | ❌ | ❌ | ✅ | ❌ | ✅ |
| Analyst dashboard & TGDPS maps | ❌ | ❌ | ✅ | ✅ | ❌ |
| Sentinel Resilience Engine | ❌ | ❌ | ✅ | ✅ | ❌ |
| Send global alerts | ❌ | ❌ | ✅ | ✅ | ❌ |
| Weather warnings API | ❌ | ❌ | ✅ | ✅ | ❌ |

---

## 🎯 Points & Rewards Economy

Every point in the system is earned through a defined, auditable action.

| Action | Points | Notes |
|:---|:---|:---|
| Submit a report | **+10** | Base award on submission |
| Report auto-approved by AI (≥85%) | **+30 total** | 10 base + 20 verification bonus, awarded instantly |
| Report approved by an official | **+20** | Awarded to the report author on approval |
| Complete a rescue — beginner | **+100** | Base tier |
| Complete a rescue — intermediate | **+150** | 1.5× multiplier |
| Complete a rescue — expert | **+200** | 2.0× multiplier |
| Rescue speed bonus | **up to +30** | `(24 − hours_taken) / 4` when completed under 24 h |
| Eco activity | **max(5, kg CO₂ × 10 + bonus)** | Bonus varies by activity; unverified earns half base |
| Tree planting bonus | **+15** | Highest eco bonus |
| Cycling bonus | **+8** | |
| Waste recycling bonus | **+6** | |
| Plastic reduction bonus | **+5** | |

### Progression Thresholds

| Milestone | Threshold | Unlock |
|:---|:---|:---|
| **Level up** | Every 50 points | `level = points ÷ 50 + 1` |
| **Community Guardian badge** | 100 points | 🛡️ Badge |
| **Eco Champion badge** | 500 eco points | 🏆 Badge |
| **Government Certificate** | 500 points | Viewable + printable official certificate |
| **Leaderboard top 20** | Relative | Public recognition on `/leaderboard` |

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Notes |
|:---|:---|
| **Python 3.9+** | Tested on 3.11 and 3.13 |
| **pip + venv** | Standard library tooling is sufficient |
| **Twilio Account** | Free trial works; WhatsApp Sandbox must be enabled |
| **Ngrok / tunnel** | Required only for local WhatsApp webhook testing |
| **PostgreSQL 14+** | Production only — SQLite is used automatically in development |

### 1. Clone & Set Up the Environment

```bash
git clone https://github.com/varunmax7/sentinelai.git
cd sentinelai

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# --- Core ---
SECRET_KEY=replace-with-a-long-random-string
DATABASE_URL=sqlite:///site.db       # Production: postgresql://user:pass@host/db

# --- Twilio WhatsApp ---
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886   # Twilio Sandbox number

# --- Twilio SMS (optional) ---
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# --- NVIDIA NIM (image processing, Parameter 4) ---
NVIDIA_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # OpenRouter key
NVIDIA_VISION_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free   # optional, this is the default

# --- Optional ---
BASE_URL=https://your-ngrok-subdomain.ngrok-free.app
FIREBASE_SERVER_KEY=your_firebase_key    # For push notifications
```

### 3. Initialise the Database

```bash
flask db upgrade
```

If you are starting from a blank database, `db.create_all()` runs automatically at import time, and `init_badges()` seeds the badge catalogue on first launch.

### 4. Run the Application

```bash
python app.py
# Server starts on http://0.0.0.0:5001
# Access locally: http://localhost:5001
```

Or use the helper script, which frees port 5001 if it is occupied and prints the ngrok next-steps:

```bash
./start_system.sh
```

### 5. Expose to the Internet (For WhatsApp Testing)

```bash
ngrok http 5001

# Then in the Twilio Console, set the WhatsApp Sandbox webhook to:
#   https://YOUR-TUNNEL-URL/webhook/whatsapp
```

The `setup_whatsapp.sh` script automates the Twilio sandbox configuration steps, and `/whatsapp-setup` renders an in-app walkthrough.

### 6. Bootstrap an Official Account

```bash
# Visit once in the browser to create the first official account:
#   http://localhost:5001/create-official-account
#
# Or promote an existing user:
#   http://localhost:5001/elevate-user/you@example.com/official
```

Remove or gate these routes before any public deployment.

---

## ⚙️ Configuration Reference

Every setting lives in `config.py` and reads from the environment.

| Variable | Default | Purpose |
|:---|:---|:---|
| `SECRET_KEY` | `dev-key-for-demo-only` | Flask session signing — **must** be replaced in production |
| `DATABASE_URL` | `sqlite:///site.db` | Database connection string; `postgres://` is auto-rewritten to `postgresql://` for SQLAlchemy 2.x compatibility |
| `MAX_CONTENT_LENGTH` | 16 MB | Maximum upload size; exceeding it returns a friendly 413 handler |
| `UPLOAD_FOLDER` | `static/uploads` | Where report media is stored |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, mp4, mov, avi | Upload allowlist |
| `LANGUAGES` | en, ta, hi, te, ml, kn | Supported locales |
| `BABEL_DEFAULT_LOCALE` | `en` | Fallback language |
| `TWILIO_ACCOUNT_SID` | — | Twilio credential |
| `TWILIO_AUTH_TOKEN` | — | Twilio credential |
| `TWILIO_WHATSAPP_NUMBER` | — | Sandbox or approved WhatsApp sender |
| `TWILIO_PHONE_NUMBER` | — | SMS sender for the SMS alert path |
| `FIREBASE_SERVER_KEY` | — | Enables push notifications when set |

---

## 📡 API Reference

All JSON endpoints require authentication via session cookie unless marked otherwise. 🔐 indicates an additional role check.

### Authentication & Profile

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET/POST` | `/register` | Public | Create an account |
| `GET/POST` | `/login` | Public | Sign in |
| `GET` | `/logout` | ✅ | Sign out |
| `GET` | `/profile/<username>` | ✅ | Public profile with points, badges, reports |
| `GET/POST` | `/edit_profile` | ✅ | Update bio, image, preferences |
| `GET` | `/follow/<username>` | ✅ | Follow a user |
| `GET` | `/unfollow/<username>` | ✅ | Unfollow a user |
| `GET` | `/user_followers/<username>` | ✅ | List followers |
| `GET` | `/user_following/<username>` | ✅ | List following |
| `GET` | `/user/<username>/reports` | Public | A user's report history |
| `GET` | `/set_language/<lang>` | Public | Switch locale |
| `GET/POST` | `/set_location` | ✅ | Set the home location that drives alerting |
| `GET/POST` | `/alert_preferences` | ✅ | Per-hazard alert opt-in/out |

### Reports & Detection

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET/POST` | `/report` | ✅ | Submit a new hazard report |
| `GET` | `/api/reports` | Public | List of reports for map rendering |
| `GET` | `/view_report/<id>` | ✅ | Full report detail |
| `GET` | `/api/hazards/active` | ✅ | Active hazards for map overlay |
| `GET` | `/api/report/<id>/accuracy_4param` | ✅ | Full 4-parameter AI accuracy breakdown |
| `POST` | `/api/submit_sos` | ✅ | Voice SOS with transcript + GPS |
| `POST` | `/verify_report/<id>` | 🔐 Official | Approve a pending report |
| `GET/POST` | `/reject_report/<id>` | 🔐 Official | Reject with a recorded reason |
| `POST` | `/delete_report/<id>` | 🔐 Official | Delete a report |
| `POST` | `/cancel_deletion/<id>` | 🔐 Official | Cancel a scheduled deletion |
| `POST` | `/api/report/<id>/local_approve` | ✅ | Neighbourhood crowd-verification |
| `POST` | `/api/report/<id>/view` | ✅ | Register a view |
| `POST` | `/api/report/<id>/comment` | ✅ | Add a comment |
| `GET` | `/api/report/<id>/comments` | ✅ | List comments |
| `POST` | `/api/report/<id>/share` | ✅ | Increment share counter |
| `GET` | `/uploads/<filename>` | Public | Serve uploaded media |
| `POST` | `/api/upload` | ✅ | Generic authenticated upload (completion proofs) |
| `GET` | `/search` · `/api/search` | ✅ | Search reports, trending hazards |
| `GET` | `/reels` | Public | Vertical media feed |

### Coordination & Dispatch

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/coordination` | 🔐 Official | Coordination command dashboard |
| `GET` | `/coordination/agencies` | 🔐 Official | Agency registry |
| `GET/POST` | `/coordination/agencies/new` | 🔐 Official | Register an agency |
| `GET` | `/coordination/emergencies` | 🔐 Official | Emergency event list |
| `GET/POST` | `/coordination/emergencies/new` | 🔐 Official | Declare an emergency |
| `GET` | `/coordination/resources` | 🔐 Official | Resource ledger |
| `GET/POST` | `/coordination/resources/allocate` | 🔐 Official | Allocate resources |
| `GET` | `/coordination/volunteers` | 🔐 Official | Volunteer roster |
| `GET/POST` | `/coordination/volunteers/register` | ✅ | Register as a volunteer |
| `GET/POST` | `/coordination/volunteers/assign` | 🔐 Official | Manual assignment form |
| `GET` | `/coordination/situation-reports` | 🔐 Official | SITREP list |
| `GET/POST` | `/coordination/situation-reports/new` | 🔐 Official | File a SITREP |
| `GET` | `/api/coordination/volunteers/match` | 🔐 Official | Skill + distance matching engine |
| `GET` | `/api/coordination/volunteers/nearby` | 🔐 Official | Radius query for responders |
| `POST` | `/api/coordination/assign-volunteer` | 🔐 Official | Create assignment + notify |
| `GET` | `/api/coordination/assignment/<id>` | ✅ | Assignment detail |
| `POST` | `/api/coordination/assignment/respond` | ✅ Volunteer | Accept or decline |
| `POST` | `/api/coordination/assignment/<id>/accept` | ✅ Volunteer | Accept |
| `POST` | `/api/coordination/assignment/<id>/decline` | ✅ Volunteer | Decline |
| `POST` | `/api/coordination/assignment/<id>/complete` | ✅ Volunteer | Complete with GPS + photo |
| `POST` | `/api/coordination/assignment/<id>/cancel` | ✅ | Cancel and release |
| `GET` | `/api/coordination/assignments/active` | ✅ | Current live mission |
| `GET` | `/api/coordination/resources/status` | 🔐 Official | Live inventory posture |
| `GET` | `/api/coordination/emergency-map` | 🔐 Official | Emergency map feed |
| `GET` | `/api/coordination/emergency/<id>/volunteers-count` | ✅ | Responders per emergency |
| `GET` | `/api/coordination/hazard/<type>/<id>/volunteers-count` | ✅ | Responders per hazard |
| `GET` | `/rescue-complete` | ✅ | Completion confirmation view |

### Analytics, Weather & Simulation

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/analyst_dashboard` | 🔐 Official/Analyst | Full analyst command centre |
| `GET` | `/simulation` | 🔐 Official/Analyst | Sentinel Resilience Engine UI |
| `POST` | `/api/simulate_impact` | 🔐 Official/Analyst | Deterministic impact simulation |
| `POST` | `/api/simulate_analysis` | 🔐 Official/Analyst | LLM-backed government resilience briefing |
| `GET` | `/api/weather_data` | Public | Live weather from Open-Meteo |
| `GET` | `/api/weather_warnings` | 🔐 Official/Analyst | Severe weather warnings feed |
| `GET` | `/api/live_hazard_incidents` | Public | Up to 500 live incidents for maps |
| `GET` | `/api/live_govt_hazards` | Public | IMD / NDMA / USGS / GSI hazard feed |
| `GET` | `/api/proxy/tgdps_map?path=aws.jsp` | Public | Proxied TGDPS state rainfall map |
| `GET` | `/api/proxy/tgdps_map?path=livejsp/Hyderabad.jsp` | Public | District-level rainfall map |
| `POST` | `/send_test_warning` | 🔐 Official | Fire a test warning through the alert pipeline |
| `POST` | `/send_global_alert` | 🔐 Official | Broadcast to selected locations |
| `GET` | `/chart/hazard_distribution` | ✅ | Server-rendered hazard pie chart (PNG) |
| `GET` | `/chart/reports_timeline` | ✅ | Server-rendered timeline chart (PNG) |
| `GET` | `/chart/user_engagement` | ✅ | Server-rendered engagement chart (PNG) |

### Notifications

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/notifications` | ✅ | Notification centre page |
| `GET` | `/api/notifications` | ✅ | Notification list (JSON) |
| `GET` | `/api/notifications/unread-count` | ✅ | Unread count (polled every 5 s) |
| `POST` | `/api/notification/<id>/read` | ✅ | Mark read (API) |
| `POST` | `/notification/<id>/read` | ✅ | Mark read (web) |
| `POST` | `/clear_all_notifications` | ✅ | Clear all |
| `POST` | `/api/register_push_token` | ✅ | Register an FCM push token |

### Community, LifeLine & Sustainability

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/community_hub` | ✅ | Community events hub |
| `GET/POST` | `/community/create` | ✅ | Create a community event |
| `GET` | `/community/join/<id>` | ✅ | Join an event |
| `GET` | `/community/leave/<id>` | ✅ | Leave an event |
| `GET` | `/lifeline` | ✅ | P2P resource marketplace |
| `GET/POST` | `/lifeline/create` | ✅ | Create a have/need listing |
| `GET` | `/lifeline/map` | ✅ | Visual match map with connection lines |
| `GET` | `/lifeline/complete_match/<id>` | ✅ | Close a completed match |
| `GET` | `/eco_tracker` | ✅ | Personal sustainability dashboard |
| `GET/POST` | `/plastic_reduction` | ✅ | Log plastic avoided |
| `GET/POST` | `/carbon_savings` | ✅ | Log an eco activity |
| `GET` | `/api/eco_stats` | ✅ | Eco statistics feed |
| `GET` | `/eco_leaderboard` | ✅ | Eco rankings |

### Gamification

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/leaderboards` | ✅ | All leaderboards |
| `GET` | `/leaderboard` | ✅ | Top 20 individuals |
| `GET` | `/community_leaderboard` | ✅ | Community rankings |
| `GET` | `/api/leaderboard` | ✅ | Leaderboard JSON |
| `GET` | `/api/leaderboard/user/<id>` | ✅ | An individual's rank |
| `GET` | `/api/community_leaderboard` | ✅ | Community leaderboard JSON |
| `GET` | `/certificate/<user_id>` | ✅ | View government certificate |
| `GET` | `/certificate/download/<user_id>` | ✅ | Print-optimised certificate |

### PWA, WhatsApp & Utilities

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/sw.js` | Public | Service Worker |
| `GET` | `/manifest.json` | Public | PWA manifest |
| `GET` | `/offline.html` | Public | Offline fallback page |
| `POST` | `/webhook/whatsapp` | Twilio | Inbound WhatsApp handler |
| `GET` | `/whatsapp-setup` | Public | WhatsApp setup walkthrough |
| `GET` | `/share` | Public | Shareable app link page |
| `GET` | `/about` | Public | About the platform |
| `GET` | `/` · `/home` | Public | Landing page + hero map |
| `GET` | `/dashboard` | ✅ | Main user dashboard |
| `GET` | `/get_location` | ✅ | Location helper |

### Browser-Side External APIs (no proxy)

| Service | Endpoint | Purpose |
|:---|:---|:---|
| **Open-Meteo Forecast** | `api.open-meteo.com/v1/forecast` | Temperature, wind, humidity, weather codes |
| **Open-Meteo Air Quality** | `air-quality-api.open-meteo.com/v1/air-quality` | US AQI for the climate panel |
| **Nominatim** | `nominatim.openstreetmap.org/reverse` | Reverse geocode lat/lng → city name |
| **Esri World Imagery** | `server.arcgisonline.com/.../World_Imagery` | Satellite tiles for the hero map |
| **RainViewer** | `api.rainviewer.com` | Precipitation radar tiles |
| **CARTO Voyager GL** | `basemaps.cartocdn.com` | 3D vector basemap style |

---

## 📱 WhatsApp Bot

### Flow 1 — Account Linking

```
User  →  "Hi"
Bot   →  "🛡️ Welcome to Sentinel AI!
          Please enter your *username* to link your account:"
User  →  "john_doe"
Bot   →  "Hello john_doe! Please enter your *password* to confirm:"
User  →  "••••••••"
Bot   →  "✅ Success! Your WhatsApp is now linked to *john_doe*.
          You will receive real-time hazard alerts and assignment
          requests here."
```

Username lookup is case-insensitive and whitespace-tolerant. The password is verified against the same PBKDF2 hash used by the web login — the bot never stores or echoes a plaintext credential.

### Flow 2 — Status Check

```
User  →  "status"
Bot   →  "🛡️ *SENTINEL AI ASSISTANT*
          ━━━━━━━━━━━━━━
          👤 User: john_doe
          ✅ Status: Monitoring Active
          📍 Zone: Within 50km radius

          You will receive verified hazard alerts and assignments
          automatically.

          💡 Commands:
          • Reply *1* to Accept assignments
          • Reply *2* to Reject assignments

          🔗 Dashboard: https://…/dashboard"
```

### Flow 3 — Volunteer Dispatch

```
[Hazard verified by the system]

Bot   →  📸 [Hazard photo attached]
Bot   →  "🚨 *STORM SURGE ALERT*
          Location: Marina Beach, Chennai
          Distance: 3.2 km from you
          Severity: HIGH

          🤝 Your help is needed.
          Reply *1* to Accept
          Reply *2* to Decline"

User  →  "1"
Bot   →  "✅ *MISSION ASSIGNED*

          🚀 Title: Storm surge at Marina Beach
          📝 Info: Water rising rapidly near the pier…
          📍 Location: Marina Beach, Chennai
          🌐 Coords: 13.0566, 80.2783

          🏁 START NAVIGATION:
          https://www.google.com/maps/dir/?api=1&destination=13.0566,80.2783

          ⚠️ Stay Alert: Report status via dashboard."
Bot   →  📸 [Incident photo attached to the same message]

[Volunteer arrives and completes with GPS + photo proof]
Bot   →  "🏆 Mission completed! You earned 150 points."
```

### Flow 4 — Cancellation

```
User  →  "cancel"
Bot   →  "✅ Assignment cancelled successfully.
          You are now marked as available."

[Simultaneously]
Coordinator (in-app) →  "❌ Volunteer john_doe has cancelled their assignment."
Coordinator (WhatsApp) → "❌ *ASSIGNMENT CANCELLED*
                          Volunteer *john_doe* has cancelled their accepted task.
                          🔗 Dashboard: …
                          Please assign another volunteer."
```

### Supported Commands

| Command | Aliases | Response |
|:---|:---|:---|
| `hi` | hello, hey, ji, start, status | Account status summary + command help |
| `1` | accept, yes, 1️⃣ | Accept the latest assignment; returns full mission brief + navigation link + photo |
| `2` | reject, decline, no, 2️⃣ | Decline the pending assignment; coordinator notified |
| `cancel` | abort | Cancel an accepted assignment; volunteer released, coordinator alerted |
| *anything else* | — | Fallback help message with available commands |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Language** | Python 3.9+ | Backend runtime |
| **Web Framework** | Flask ≥ 2.3.3 | HTTP server, routing, templating |
| **Auth** | Flask-Login ≥ 0.6.3 | Session management |
| **Forms** | Flask-WTF + WTForms ≥ 3.1.2 | Server-side validation, CSRF |
| **ORM** | Flask-SQLAlchemy ≥ 3.1.1 | Database abstraction |
| **Migrations** | Flask-Migrate ≥ 4.0.7 (Alembic) | Schema version control |
| **Task Scheduler** | APScheduler ≥ 3.10.5 | Background jobs |
| **Messaging** | Twilio ≥ 9.0.0 | WhatsApp + SMS API |
| **HTTP client** | requests ≥ 2.31 | External API calls |
| **Weather API** | Open-Meteo Forecast | Free live weather (temp, wind, humidity, codes) |
| **Air Quality API** | Open-Meteo Air Quality | US AQI for the hero climate panel |
| **Geocoding** | Nominatim (OpenStreetMap) | Reverse-geocode GPS → city name |
| **Rainfall Data** | TGDPS (Telangana Govt) | Live state + district rainfall maps |
| **Maps** | Leaflet.js + MapLibre GL | Interactive 2D maps + 3D God Mode globe |
| **Map Tiles** | Esri World Imagery + CARTO Voyager | Satellite + vector base tiles |
| **Weather Radar** | RainViewer | Satellite precipitation overlay |
| **LLM** | Sentinel Resilience Strategy Engine | Government-grade simulation briefings |
| **AI Support** | Chatbase (embedded iframe) | In-app AI assistant chatbot |
| **Charts** | Matplotlib ≥ 3.8 + NumPy ≥ 1.26 | Server-rendered analytics PNGs |
| **NLP** | TextBlob ≥ 0.18 + NLTK ≥ 3.8 | Report text analysis + SOS parsing |
| **Imaging** | Pillow ≥ 10.2 | Image processing and proof analysis |
| **DB (dev)** | SQLite | Development database |
| **DB (prod)** | PostgreSQL ≥ 14 (psycopg2-binary) | Production database |
| **WSGI** | Gunicorn ≥ 21.2 | Production app server |
| **Config** | python-dotenv ≥ 1.0.1 | Environment loading |
| **Validation** | email-validator ≥ 2.1.1 | Email field validation |
| **Frontend** | Bootstrap 5 + Glassmorphism CSS | UI framework |
| **PWA** | Service Worker + Web App Manifest | Installable, offline-capable web app |
| **Client storage** | IndexedDB | Offline report queue |

---

## ☁️ Deployment

### Render (Recommended)

1. Push the repository to GitHub
2. Create a **Web Service** on [render.com](https://render.com)
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn app:app`
5. Add every environment variable from your `.env`
6. Attach a free **PostgreSQL** database add-on and set `DATABASE_URL`
7. Deploy — `db.create_all()` runs at import, so tables are created on first boot

### Heroku

```bash
heroku create sentinel-ai
heroku addons:create heroku-postgresql:essential-0
heroku config:set SECRET_KEY=... TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=...
git push heroku main
heroku run flask db upgrade
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]
```

```bash
docker build -t sentinel-ai .
docker run -p 5001:5001 --env-file .env sentinel-ai
```

### Production Checklist

- [ ] `SECRET_KEY` replaced with a long random value
- [ ] `DATABASE_URL` points to PostgreSQL, not SQLite
- [ ] Debug mode disabled (`app.run(debug=True)` is development only — Gunicorn does not use it)
- [ ] Bootstrap/elevation utility routes removed or admin-gated
- [ ] Twilio webhook signature validation enabled
- [ ] HTTPS enforced; secure session cookies configured
- [ ] `static/uploads/` backed by persistent storage or object storage
- [ ] `flask db upgrade` run against the production database
- [ ] Log aggregation configured for the print/`app.logger` output

---

## 🔐 Security

| Control | Implementation |
|:---|:---|
| **Password storage** | Werkzeug PBKDF2-HMAC-SHA256 hashing — plaintext is never stored or logged |
| **CSRF protection** | All forms protected by Flask-WTF CSRF tokens |
| **Session management** | Flask-Login with server-side session validation and a configurable login view |
| **Role-based access control** | Every sensitive route checks `current_user.role` before rendering or mutating |
| **Ownership checks** | Assignment completion, certificate download, and profile editing verify the acting user owns the resource |
| **File upload safety** | `secure_filename` sanitisation, extension allowlist, 16 MB cap with a friendly 413 handler |
| **Path traversal defence** | The TGDPS proxy rejects `..` sequences and absolute URLs, falling back to a safe default path |
| **WhatsApp credential flow** | Password verified against the hash; session state is scoped to the originating phone number |
| **SQL injection** | All database access goes through SQLAlchemy's parameterised ORM layer |
| **Rate-limiting** | Recommended at the reverse proxy / CDN layer for production |

### Known Hardening Work

These are explicit, tracked gaps rather than hidden ones:

- **Utility routes** (`/create-official-account`, `/elevate-user/...`, `/check-users`, `/repair-database-2026`, `/debug_users`) are unauthenticated demo conveniences and **must** be removed or admin-gated before public deployment.
- **Twilio webhook signature validation** should be enabled so only Twilio can post to `/webhook/whatsapp`.
- **Demo broadcast radius** — the alert dispatcher currently uses a very wide radius so every seeded user receives demo alerts. Restore the per-hazard radii from `get_hazard_alert_radius()` for real deployments.
- **LLM endpoint credentials** are inlined for the hackathon build and should move to environment variables.

---

## ⚡ Performance & Scalability

| Concern | Current Behaviour | Scaling Path |
|:---|:---|:---|
| **AI validation latency** | Sub-second — three lightweight checks, one cached weather call | Pre-compute heatmap density per grid cell |
| **Live incident feed** | Capped at 500 most recent reports | Add spatial indexing (PostGIS) and bounding-box queries |
| **Timeline aggregation** | Grouped in Python for cross-DB parity | Move to SQL `date_trunc` on PostgreSQL-only deployments |
| **Chart rendering** | Matplotlib `Agg` backend, streamed as PNG | Cache PNGs with a short TTL |
| **Notification polling** | 5-second client poll | Upgrade to Server-Sent Events or WebSockets |
| **Alert fan-out** | Iterates all users in Python | Batch by geohash bucket; move sends to a worker queue |
| **WhatsApp sends** | Synchronous Twilio calls | Offload to a Celery/RQ queue |
| **Media storage** | Local filesystem under `static/uploads/` | S3 / Cloud Storage with CDN |
| **LLM calls** | 45-second timeout with deterministic fallback | Cache briefings keyed by rounded parameters |
| **Background jobs** | APScheduler in-process | External scheduler for multi-worker deployments |

---

## 🧪 Testing & QA Checklist

A practical validation script for demo day or a staging sign-off.

### Detection
- [ ] Submit a report with photo + GPS → confidence score appears immediately
- [ ] Submit an SOS with the phrase "water is rising, I am stuck" → hazard classified as flooding, priority `critical`
- [ ] Submit a report with no coordinates → validated gracefully with a neutral heatmap score
- [ ] Submit three similar reports in the same area → third one scores materially higher on heatmap corroboration

### Prioritization
- [ ] An `official` account's report scores higher than a brand-new citizen's identical report
- [ ] A report scoring ≥ 85% is auto-approved and alerts fire without human action
- [ ] A report scoring below 85% appears in the official review queue

### Alerting
- [ ] A user inside the hazard radius receives the alert; a user outside does not
- [ ] A user who disabled that hazard type in preferences receives nothing
- [ ] The alert message includes distance, safety instruction, and the incident photo

### Dispatch
- [ ] Assign a volunteer → WhatsApp mission card arrives with photo and navigation link
- [ ] Reply `1` → status becomes `accepted`, `accepted_at` stamped
- [ ] Attempt completion from 20 km away → rejected with the measured distance
- [ ] Complete within 10 km with a photo → points awarded per experience tier + speed bonus
- [ ] Reply `cancel` → volunteer released and coordinator notified on both channels

### Simulation
- [ ] Move sliders → impact zones and sector damage bars update on the 3D map
- [ ] Change the time horizon → damage percentages scale by 1.0 / 1.25 / 1.6
- [ ] Disconnect the LLM endpoint → the deterministic fallback briefing still renders in full

### Offline
- [ ] Enable airplane mode → offline banner and pending badge appear
- [ ] Submit a report offline → queued in IndexedDB
- [ ] Restore connectivity → queue drains and the report appears server-side with a full AI score

### Multilingual
- [ ] Load from Telangana coordinates → interface renders in Telugu
- [ ] Switch manually to Tamil → form labels and validation messages translate too

### Gamification
- [ ] First report → 🚀 First Reporter badge awarded
- [ ] Cross 100 points → 🛡️ Community Guardian badge awarded
- [ ] Cross 500 points → certificate becomes viewable and downloadable
- [ ] Below 500 points → redirected with an encouraging message, not an error

---

## 🩺 Troubleshooting

| Symptom | Likely Cause | Fix |
|:---|:---|:---|
| **Port 5001 already in use** | A previous run is still alive | `./start_system.sh` kills it automatically, or `lsof -i :5001` then `kill -9 <pid>` |
| **WhatsApp messages not arriving** | Webhook URL not set, or ngrok URL rotated | Re-point the Twilio Sandbox webhook at the current tunnel + `/webhook/whatsapp` |
| **WhatsApp media not loading** | Twilio cannot reach a `localhost` media URL | Ensure a public tunnel URL is used for `BASE_URL` |
| **"Username not found" on linking** | Trailing whitespace in the stored username | Lookup already trims and lowercases — verify the account actually exists via `/check-users` |
| **Missing database column errors** | Migration gap after pulling new code | Run `flask db upgrade`, or hit `/repair-database-2026` in a demo environment |
| **Certificate refuses to download** | Under the 500-point threshold, or not your own certificate | Earn more points, or download from the owning account |
| **Completion rejected as "too far"** | Device GPS drift or genuinely off-site | Confirm location permission is granted; the error includes the measured distance |
| **Simulation report is blank** | Should be impossible — fallback always renders | Check `app.logger` for the Sentinel LLM error, then verify the fallback path |
| **TGDPS map fails to load** | Upstream government site is down or slow (5 s timeout) | The proxy returns a readable error; retry, or use the RainViewer overlay meanwhile |
| **Charts render as broken images** | Matplotlib backend issue | Confirm `matplotlib.use('Agg')` runs before any pyplot import |
| **Offline reports never sync** | IndexedDB blocked in private browsing | Use a normal browsing window; the pending badge shows the queue depth |
| **Alerts reaching everyone** | Demo broadcast radius still active | Restore per-hazard radii in `send_hazard_alerts()` |

---

## 📜 Compliance & Governance

| Requirement | How Sentinel AI Satisfies It |
|:---|:---|
| **Auditable decisions** | Every approval stamps `verified_by` and `verified_at`; every rejection records a structured reason |
| **Evidence-backed closure** | Missions cannot be closed without a photo and GPS coordinates within 10 km of the incident |
| **Immutable record** | Every report write mirrors to CSV, independent of the database |
| **Explainable AI** | Confidence scores decompose into three named sub-scores with human-readable analysis strings |
| **Data minimisation** | Only home coordinates (not continuous location tracking) are stored for alerting |
| **User control** | Per-hazard alert preferences, manual language override, self-service location updates |
| **Right to be forgotten** | Report deletion with a grace window and an explicit cancel path |
| **Inter-agency accountability** | Resource allocations record the authorising official and the owning agency |
| **NDMA/SDMA alignment** | SITREP typing (damage assessment, resource status, weather, evacuation) mirrors standard incident-reporting categories |
| **Language accessibility** | Six languages covering the primary linguistic regions of southern and northern India |

---

## 🗺️ Roadmap

| Phase | Item | Status |
|:---|:---|:---|
| **Now** | 4-channel ingestion, 4-parameter AI, dispatch, coordination, simulation | ✅ Shipped |
| **Now** | PWA, offline queue, WhatsApp bot, 6 languages, gamification | ✅ Shipped |
| **Next** | WebSockets replacing 5-second notification polling | 🔨 Planned |
| **Next** | PostGIS spatial indexing for sub-100 ms radius queries at city scale | 🔨 Planned |
| **Next** | Celery/RQ worker queue for WhatsApp and alert fan-out | 🔨 Planned |
| **Next** | Automated Urban Resilience Index recomputation on a schedule | 🔨 Planned |
| **Later** | Live IoT river-gauge and drainage-sensor ingestion | 🧭 Exploring |
| **Later** | Satellite SAR inundation mapping for post-event damage assessment | 🧭 Exploring |
| **Later** | Native mobile wrappers with background geofencing | 🧭 Exploring |
| **Later** | Federated deployment model for multi-city state rollouts | 🧭 Exploring |
| **Later** | Formal integration with NDMA/SDMA incident-exchange standards | 🧭 Exploring |

---

## 🆕 Recent Updates

| Date | Change |
|:---|:---|
| **2026-09-03** | 📚 README rewritten as a complete platform reference — all 28 feature clusters, 119 routes, 23 models, full SH-SVA-03 traceability matrix |
| **2026-05-24** | 🧪 **Sentinel Resilience Engine** — LLM-backed 7-section government resilience briefings with a deterministic fallback report |
| **2026-05-24** | 📣 **Global Alert Broadcast console** with per-location selection and select-all |
| **2026-05-24** | 🗺️ God Mode map engine refactor — deferred operation queue, dynamic layer teardown, pulsing live-incident dots |
| **2026-05-23** | 🌡️ **Live Climate Panel** on the hero map — temperature, weather, humidity, wind, US AQI (Open-Meteo) |
| **2026-05-23** | 💬 Flash messages now display as animated glass popups on the map (auto-dismiss 5 s) |
| **2026-05-23** | 🖥️ Full-screen responsive layout — removed the legacy `col-xl-8` constraint from `base.html` |
| **2026-05-23** | 🎯 Removed the gap between navbar and hero map — a true `100vh × 100vw` canvas |
| **2026-05-23** | 🧹 Cleaned up the "Sentinel AI ACTIVE" status banner into a minimal pulsing pill |
| **2026-05-23** | 🧾 CSV audit sync on every report write (`all_reports.csv`, `all_reports_export.csv`) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add feature'`
4. Push the branch: `git push origin feature/my-feature`
5. Open a Pull Request

### Contribution Guidelines

- Match the existing code style — this codebase favours explicit, readable Flask over clever abstraction
- Any new external dependency must degrade gracefully when unavailable, following the pattern used by the LLM fallback and the weather validator
- New routes that touch sensitive data must include an explicit role check
- Any schema change needs a Flask-Migrate migration in `migrations/versions/`
- New user-facing strings belong in `translations.py` across all six languages

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ for Smart India Hackathon — Problem Statement SH-SVA-03**

*"Every minute in a disaster matters. Sentinel AI turns hours into seconds — unifying departments, empowering communities, saving lives."*

**119 API Routes · 23 Database Models · 50 Templates · 25 Forms · 6 Languages · 6 AI Agents · 4 Reporting Channels · 28 Feature Clusters**

[⭐ Star this repo](https://github.com/varunmax7/sentinelai) if you find it useful!

</div>
