# 🛡️ Sentinel AI — Multi-Agent Urban Disaster & Infrastructure Intelligence Platform

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite%20%2F%20PostgreSQL-Ready-003B57?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Twilio](https://img.shields.io/badge/Twilio-WhatsApp_API-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)
[![Leaflet](https://img.shields.io/badge/Leaflet.js-Maps-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**An enterprise-grade, AI-powered multi-agent disaster response & urban infrastructure management platform.**  
*Addressing Problem Statement SH-SVA-03: Unifying fragmented urban departments through autonomous incident detection, coordinated multi-agent response, and real-time city-wide digital twin intelligence.*

[Problem Statement](#-problem-statement-sh-sva-03) • [Solution](#-sentinel-ai-the-solution) • [App Flow](#-complete-application-flow) • [Features](#-feature-deep-dive) • [Architecture](#-system-architecture) • [Getting Started](#-getting-started) • [API Reference](#-api-reference) • [WhatsApp Bot](#-whatsapp-bot) • [Database Schema](#-database-schema)

</div>

---

## 🎯 Problem Statement: SH-SVA-03

> **Urban infrastructure management is fragmented across departments, leading to delayed incident detection, inefficient response, and increased operational costs. A multi-agent AI system integrated with a city digital twin is needed to autonomously prioritize incidents, coordinate actions, and ensure timely, compliant resolution.**

### The Crisis in Numbers

India has **7,516 km of coastline** with over **170 million people** living in low-lying urban areas vulnerable to cyclones, floods, storm surges, and tsunamis. Urban infrastructure management across Indian cities suffers from systemic, cross-departmental failures:

| Problem Area | Impact |
|:---|:---|
| **🏛️ Departmental Silos** | Fire, police, municipal, health, and disaster agencies operate on separate communication channels. A single flood event requires 5+ departments to coordinate — manually. |
| **⏱️ Delayed Detection** | A field report of rising floodwater takes **hours** to be manually confirmed by authorities, delaying response. Citizens call helplines, officials check social media, volunteers wait for orders. |
| **📞 Inefficient Dispatch** | Coordinators manually phone or message volunteers one by one. Losing precious minutes while lives are at stake. |
| **🌐 Language Barriers** | Critical alerts in non-native languages are often ignored by local communities — fishermen, farmers, coastal workers. |
| **📊 Zero Predictive Power** | Agencies react to disasters rather than simulating impacts ahead of time. No city-wide digital twin exists. |
| **💰 Operational Cost Overrun** | Redundant efforts, uncoordinated resource deployment, and reactive approaches drain government budgets. |

**The result:** Response times measured in hours. Lives and resources lost that could have been saved with an intelligent, unified system.

---

## 🧠 Sentinel AI: The Solution

Sentinel AI is not just another disaster app — it is a **multi-agent AI command system** that acts as the autonomous nervous system for urban crisis management.

### Multi-Agent Architecture

The platform deploys specialized AI agents that work in concert:

| Agent | Role | Autonomy Level |
|:---|:---|:---|
| **🔍 Detection Agent** | Ingests citizen reports (online, offline via AI calling, SOS), satellite data, TGDPS rainfall feeds, and weather APIs. Cross-validates using 3-parameter AI scoring. | Fully autonomous |
| **📋 Prioritization Agent** | Ranks incidents by severity, proximity to critical infrastructure, population density, and weather alignment. Auto-approves high-confidence reports (≥85%). | Fully autonomous |
| **🚁 Dispatch Agent** | "Uber-style" volunteer matching — queries available responders within 10km, fires WhatsApp assignments, tracks acceptance/completion. | Semi-autonomous |
| **📡 Alert Agent** | Geo-fenced push notifications — alerts only users within the hazard impact radius (not mass blasts). 20km radius notifications with disaster images and safe rescue locations. | Fully autonomous |
| **📊 Analytics Agent** | Powers the Analyst Dashboard — live satellite overlays, TGDPS real-time rainfall maps (state + district level), climate source integration, risk simulators. | Continuous |
| **🤝 Coordination Agent** | Manages inter-departmental resource allocation, SITREP generation, agency registry, and supply chain tracking. | Semi-autonomous |

### Why Sentinel AI vs. Existing Platforms

| Feature Area | Traditional Platforms | 🛡️ Sentinel AI |
|:---|:---|:---|
| **Response Speed** | Manual verification (takes hours) | **Sub-second AI Validation** (3-parameter checking algorithm) |
| **Reporting Channels** | Single-channel (app or phone) | **Omni-channel**: Online reports, offline AI calling agent, one-tap Voice SOS with lat/long, WhatsApp bot |
| **Accessibility** | Requires app downloads, English-first | **No-install PWA + WhatsApp + Voice SOS.** Auto-translates to 6 regional languages via GPS |
| **Volunteer Logistics** | Manual phone trees, chaotic groups | **"Uber-style" Auto-Dispatch.** 10km radius, skill-matched, WhatsApp-native |
| **Alerting Precision** | Mass SMS blasts (causes panic) | **Smart Geo-Fencing.** 20km radius alerts with disaster images + safe rescue locations |
| **Resource Supply Chain** | Top-down handouts only | **LifeLine P2P Marketplace** + Supply chain tracking for physical disaster items |
| **Predictive Power** | Reactive (post-disaster) | **Risk Simulator + Live TGDPS Satellite Rainfall Maps** (state & district level) |
| **Dept. Coordination** | Phone calls between offices | **Unified Coordination Dashboard** — agencies, resources, SITREPs, volunteers |
| **Community Engagement** | None | **Volunteering Hub** — beach cleanups, tree planting, NGO onboarding |
| **Gamification** | None | **Points + Govt Certification + Leaderboards** with top performer recognition |

---

## 🔄 Complete Application Flow

The following is the end-to-end operational flow of Sentinel AI, from incident detection to community resilience building:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: INCIDENT DETECTION                         │
│                                                                             │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────────────┐ │
│  │ 📱 Online   │  │ 📞 Offline via   │  │ 🆘 SOS Button                 │ │
│  │   Report    │  │   AI Calling     │  │   (One-tap with lat/long,     │ │
│  │   (PWA)     │  │   Agent          │  │    auto-records audio,        │ │
│  │             │  │                  │  │    NLP extracts keywords)     │ │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────┬─────────────────┘ │
│         │                  │                           │                    │
│         └──────────────────┴───────────────────────────┘                    │
│                            │                                                │
│                   ┌────────▼────────┐                                       │
│                   │  🤖 AI Verification Engine                              │
│                   │  3-Parameter Accuracy System™                           │
│                   │                                                         │
│                   │  P1: Heatmap Match (33%)                                │
│                   │      → Similar reports in 5.5km / 24hr                  │
│                   │  P2: Climate Alignment (33%)                            │
│                   │      → Open-Meteo live weather validation               │
│                   │  P3: User Quality Score (34%)                           │
│                   │      → Historical credibility of reporter               │
│                   │                                                         │
│                   │  Score ≥ 85% → AUTO-APPROVED                            │
│                   │  Score < 85% → Queued for Official Review               │
│                   └────────┬────────┘                                       │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                   PHASE 2: ANALYST DASHBOARD & DIGITAL TWIN                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  🛰️ Live Satellite Climate Sources                                    │  │
│  │  • RainViewer real-time radar overlay                                  │  │
│  │  • Open-Meteo weather data (temp, humidity, wind, weather codes)       │  │
│  │  • TGDPS Live Rainfall Map — State Level (auto-refresh)               │  │
│  │  • TGDPS Live Rainfall Map — District Level (33 districts selectable) │  │
│  │  • INSAT satellite overlay                                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  📊 Analytics & Risk Simulation                                       │  │
│  │  • Hazard distribution charts                                         │  │
│  │  • Reports timeline & trend analysis                                  │  │
│  │  • User engagement metrics                                            │  │
│  │  • Risk Simulator: Input rainfall + sea-level → predict infra damage  │  │
│  │  • Urban Resilience Index (URI) per geographic zone                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│                   PHASE 3: OFFICIAL APPROVAL & ALERTING                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  🏛️ Official Review Panel                                       │       │
│  │  • View AI accuracy breakdown                                    │       │
│  │  • Approve / Reject with reasons                                 │       │
│  │  • Escalate priority (Normal → High → Critical)                  │       │
│  └────────────────────────┬────────────────────────────────────────┘       │
│                           │ APPROVED                                       │
│  ┌────────────────────────▼────────────────────────────────────────┐       │
│  │  📢 Smart Geo-Fenced Alerts (20km radius)                       │       │
│  │  • Push notifications to users within impact zone                │       │
│  │  • WhatsApp alerts with disaster report IMAGE                    │       │
│  │  • Safe rescue location coordinates included                     │       │
│  │  • Multi-language auto-translation                               │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│               PHASE 4: VOLUNTEER DISPATCH & RESCUE OPERATIONS               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  🤝 "Uber-Style" Volunteer Matching                              │       │
│  │  1. Query available volunteers within 10km radius                 │       │
│  │  2. Match by skills (medical, rescue, logistics)                  │       │
│  │  3. Fire WhatsApp message with photo + coordinates                │       │
│  │  4. Volunteer replies "1" Accept / "2" Decline                    │       │
│  │  5. Real-time status: Pending → Accepted → En Route → Completed  │       │
│  │  6. Upload completion photo as proof → earn points                │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│           PHASE 5: LIFELINE — SUPPLY CHAIN & RESOURCE MANAGEMENT            │
│                                                                             │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────────┐│
│  │ 🏪 P2P Resource Marketplace  │  │ 📦 Physical Supply Chain Tracking   ││
│  │                              │  │                                      ││
│  │ Citizens list:               │  │ Government & NGO agencies:           ││
│  │ • What they HAVE (food,      │  │ • Register in Agency Registry       ││
│  │   medicine, blankets, boats) │  │ • Track resource allocation          ││
│  │ • What they NEED             │  │   (Allocated → Deployed → Used)     ││
│  │                              │  │ • Situation Reports (SITREPs)       ││
│  │ SafeLink™ auto-matches      │  │ • Cross-department coordination     ││
│  │ donors ↔ requesters         │  │                                      ││
│  │ by proximity                 │  │ All reports by people & govt         ││
│  │                              │  │ consolidated in one dashboard        ││
│  └──────────────────────────────┘  └──────────────────────────────────────┘│
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│            PHASE 6: COMMUNITY VOLUNTEERING & RESILIENCE BUILDING            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  🌿 Shonha's Community Hub                                      │       │
│  │                                                                   │       │
│  │  Anyone can be a volunteer and help people:                       │       │
│  │  • Vacate & evacuate during disasters                             │       │
│  │  • Feed affected communities                                      │       │
│  │  • Join NGO/Govt initiatives directly through the app             │       │
│  │  • Beach cleanups & plastic reduction drives                      │       │
│  │  • Tree planting campaigns                                        │       │
│  │  • Environmental conservation activities                          │       │
│  │                                                                   │       │
│  │  Eco-Tracker: Log activities → earn carbon savings credits        │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────────┐
│              PHASE 7: GAMIFICATION, RECOGNITION & CERTIFICATION             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │  🏆 Points & Honours System                                      │       │
│  │                                                                   │       │
│  │  • Points earned for: reporting, volunteering, eco-activities     │       │
│  │  • Levels: Eco Beginner → Climate Hero                            │       │
│  │  • Badges: First Report, Rescue Hero, Eco Warrior, etc.           │       │
│  │  • Leaderboards: Individual, Community, Eco-specific              │       │
│  │  • Top performers recognized with Government Certification        │       │
│  │  • Social features: Follow users, view profiles, share reports    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Cutting Capabilities

| Capability | Description |
|:---|:---|
| **🌐 Multi-Lingual** | Auto-detects language from GPS coordinates. Supports English, Telugu, Tamil, Malayalam, Kannada, Hindi. Manual toggle available. |
| **📱 Progressive Web App** | Installable on mobile — no app store needed. Works offline via Service Worker caching. |
| **💬 WhatsApp Integration** | Full bot flow — account linking, volunteer dispatch, status updates, report submission — all via WhatsApp. |
| **🎖️ Govt Certification** | Top performers receive official government-recognized certificates for disaster response contributions. |
| **🔔 Real-time Notifications** | In-app notification bell with 5-second polling. Push notifications via Firebase. |

---

## ✨ Feature Deep-Dive

### 🚨 1. Omni-Channel Incident Reporting

| Channel | How It Works |
|:---|:---|
| **Online Report (PWA)** | Fast form-based reporting with photo/video upload, GPS auto-fill, hazard type selection |
| **Offline AI Calling Agent** | Citizens without internet call the AI agent, which transcribes speech, extracts hazard type and location, auto-creates a report |
| **SOS Button** | One-tap emergency — captures GPS coordinates (lat/long), records audio, NLP extracts keywords ("stuck", "water rising"), auto-categorizes hazard, elevates to Critical priority |

### 🤖 2. AI Verification Engine — 3-Parameter Accuracy System™

Every report is instantly scored:

| Parameter | Weight | How It Works |
|:---|:---|:---|
| **Heatmap Match** | 33% | Cross-references spatial density of similar reports in a 5.5km radius over 24 hours |
| **Climate Alignment** | 33% | Queries Open-Meteo API — validates that live weather conditions (wind speed, humidity, weather codes) support the claimed hazard |
| **User Quality Score** | 34% | Historical credibility — approval rate, account age, user level, role-based trust multiplier |

| Score | Classification | System Action |
|:---|:---|:---|
| **85–100%** | 🟢 Highly Reliable | Auto-approved → alerts dispatched immediately |
| **60–84%** | 🟡 Good Confidence | Queued for official review |
| **40–59%** | 🟠 Questionable | Held for investigation |
| **0–39%** | 🔴 Low Confidence | Flagged as potential misinformation |

### 🛰️ 3. Analyst Dashboard & City Digital Twin

The crown jewel of the platform — a comprehensive analytical command center:

- **Live Satellite Overlays**: RainViewer real-time precipitation radar overlaid on Leaflet.js maps
- **TGDPS Integration**: Live rainfall status maps from the Telangana Development Planning Society
  - **State-Level Map**: Full Telangana state with 500+ AWS station markers, auto-refreshing
  - **District-Level Map**: Select from 33 districts — Hyderabad, Adilabad, Warangal, etc. — for granular weather intelligence
- **Risk Simulator**: Input projected rainfall (mm) and sea-level anomalies → AI predicts sectoral infrastructure damage across Power, Water, Telecom, Housing → outputs evacuation priority
- **Urban Resilience Index (URI)**: Dynamic 0–100 score per geographic zone, calculated from response times, hazard frequency, and community eco-activity density
- **Analytics Charts**: Hazard distribution, reports timeline, user engagement, trending hazard types

### 🤝 4. Uber-Style Volunteer Dispatch

Once a hazard is verified:
1. **Query** — find registered, available volunteers within **10km radius**
2. **Match** — filter by skills (medical, rescue, logistics, general)
3. **Dispatch** — fire WhatsApp interactive message with hazard photo, coordinates, severity
4. **Respond** — volunteer replies "1" Accept or "2" Decline directly in WhatsApp
5. **Track** — real-time lifecycle: `Pending → Accepted → En Route → Completed`
6. **Verify** — upload completion photo as proof → earn gamified points

### 📢 5. Smart Geo-Fenced Alerts (20km Radius)

Prevents alert fatigue through precision targeting:
- Alerts only reach users whose home locations fall within the hazard impact radius
- Includes the **disaster report image** for visual context
- Includes **safe rescue location** coordinates
- Scaled radius based on hazard type (e.g., 15km for storm surge, 2km for localized swell)
- Multi-channel: in-app push + WhatsApp + notification bell

### 🛰️ 6. LifeLine — P2P Emergency Resource Marketplace

When supply chains break down, communities survive together:
- **SafeLink™ Matching Engine**: Users list what they NEED (insulin, boats, blankets) or what they HAVE → algorithm auto-pairs by proximity
- **Visual Mapping**: Glowing connection lines on the LifeLine map visualize successful supply matches
- **Government + Citizen Reports**: All reports consolidated — from citizens and government agencies — in one unified view

### 📦 7. Supply Chain Management

Physical resource tracking for disaster response operations:
- **Agency Registry**: Register government departments and NGOs
- **Resource Allocation Ledger**: Track quantities of medical/food supplies — `Allocated → Deployed → Used → Returned`
- **Situation Reports (SITREPs)**: Formal field reports mapped against ongoing emergency events
- **Inter-Department Coordination**: Break departmental silos with a unified coordination dashboard

### 🌿 8. Community Volunteering Hub (Shonha's App)

Building resilience before and after disasters:
- **Join as Volunteer**: Anyone can register — part of government or any NGO
- **Help during disasters**: Assist with evacuation, feeding, medical aid
- **Environmental Initiatives**: Beach cleanups, tree planting, plastic reduction drives
- **Eco-Tracker**: Log eco-friendly behaviors → earn estimated kg of CO2 saved
- **Levels**: Eco Beginner → Eco Enthusiast → Green Champion → Climate Hero

### 🏆 9. Gamification & Government Certification

| Element | Details |
|:---|:---|
| **Points System** | Earn points for reporting, volunteering, eco-activities, completing missions |
| **Levels** | Progressive leveling based on accumulated points |
| **Badges** | Achievement badges — First Report, Rescue Hero, Eco Warrior, Community Leader |
| **Leaderboards** | Individual rankings, community rankings, eco-specific rankings |
| **Top Performers** | Recognized with **Government Certification** for outstanding contributions |
| **Social Features** | Follow other users, view profiles, share reports as "reels" |

### 🌐 10. Multi-Lingual Support

| Language | Detection Method |
|:---|:---|
| English | Default |
| Telugu | GPS-detected (Telangana/AP coordinates) |
| Tamil | GPS-detected (Tamil Nadu coordinates) |
| Malayalam | GPS-detected (Kerala coordinates) |
| Kannada | GPS-detected (Karnataka coordinates) |
| Hindi | GPS-detected (Hindi belt coordinates) |

Auto-loads the correct language based on GPS coordinates upon first load. Manual toggling always available.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER / PWA CLIENT                             │
│                                                                          │
│  Bootstrap 5 · Glassmorphism CSS · Leaflet.js · Chart.js                 │
│  Service Worker (Offline) · Web App Manifest (Add-to-Homescreen)         │
│  Language: Auto-detected by GPS · Real-time polling every 5s             │
│  Voice SOS: MediaRecorder API + NLP keyword extraction                   │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │ HTTPS
                             │
┌────────────────────────────▼─────────────────────────────────────────────┐
│                        FLASK APPLICATION                                  │
│                     (Port 5001 · 116 Routes · 5600+ Lines)               │
│                                                                           │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────┐ ┌─────────────┐  │
│  │ 🔍 Detection  │ │ 📋 Prioritize  │ │ 🚁 Dispatch  │ │ 📡 Alert    │  │
│  │    Agent      │ │    Agent       │ │    Agent     │ │    Agent    │  │
│  │ 3-Param AI    │ │ Auto-approval  │ │ 10km Geo-Q   │ │ 20km Fence  │  │
│  │ NLP + SOS     │ │ Severity rank  │ │ WhatsApp bot │ │ Multi-lang  │  │
│  └───────┬───────┘ └───────┬────────┘ └──────┬───────┘ └──────┬──────┘  │
│          │                 │                  │                │          │
│  ┌───────▼─────────────────▼──────────────────▼────────────────▼───────┐  │
│  │                     SQLAlchemy ORM (23 Models)                       │  │
│  │                                                                      │  │
│  │  sqlite:///site.db  (development)                                    │  │
│  │  postgresql://...   (production — Render / Heroku / AWS)             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    APScheduler Background Jobs                        │ │
│  │  • Scheduled DB cleanup    • Weather data pre-fetching                │ │
│  │  • Alert expiry processing • TGDPS map proxy refresh                  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────┬──────────────┬──────────────┬──────────────┬────────────────┘
             │              │              │              │
   ┌─────────▼──────┐ ┌────▼─────────┐ ┌──▼──────────┐ ┌▼───────────────┐
   │  Twilio API    │ │ Open-Meteo   │ │ TGDPS Gov   │ │ RainViewer     │
   │  WhatsApp msgs │ │ Weather API  │ │ Live Rainfall│ │ Satellite Radar│
   │  Inbound hooks │ │ (Free, no-key│ │ Map Proxy   │ │ Precipitation  │
   │  Media attach. │ │  weather data│ │ (State+Dist)│ │ Overlay API    │
   └────────────────┘ └──────────────┘ └─────────────┘ └────────────────┘
```

---

## 📁 Project Structure

```
sentinel-ai/
│
├── app.py                  # Main Flask application — 116 routes, 5600+ lines
│                           # All business logic, AI engines, WhatsApp handler,
│                           # background jobs, TGDPS proxy, multi-lingual tables
│
├── models.py               # SQLAlchemy ORM — 23 database models
│
├── forms.py                # WTForms definitions for all user-facing forms
│
├── utils.py                # Core utility library:
│                           # - 3-Parameter AI validation engine
│                           # - Haversine distance calculator
│                           # - WhatsApp/Twilio message sender
│                           # - Geo-fenced alert logic
│                           # - Carbon savings calculator
│
├── translations.py         # Extended multilingual string tables (6 languages)
├── config.py               # Environment-aware Flask configuration
├── requirements.txt        # Python dependencies (19 packages)
├── Procfile                # Heroku/Render deployment entry point
├── start_system.sh         # Helper: start app + ngrok tunnel
├── setup_whatsapp.sh       # WhatsApp Twilio sandbox setup
│
├── static/
│   ├── css/style.css       # Global stylesheet (glassmorphism, animations)
│   ├── js/
│   │   ├── script.js       # Core frontend (maps, notifications, polling)
│   │   ├── analyst_dashboard.js  # TGDPS live map refresh + district selector
│   │   └── pwa.js          # PWA service worker registration
│   ├── sw.js               # Service Worker (offline caching)
│   ├── manifest.json       # PWA manifest (icons, display mode)
│   ├── icons/              # PWA app icons (multiple sizes)
│   ├── uploads/            # User-uploaded photos and videos
│   └── videos/             # Report video evidence
│
├── templates/              # 48+ Jinja2 HTML templates
│   ├── base.html               # Global layout, navbar, notification bell
│   ├── index.html              # Landing page + live report feed
│   ├── report.html             # Hazard submission (online reporting)
│   ├── dashboard.html          # Main user dashboard
│   ├── analyst_dashboard.html  # Full analyst command center + TGDPS maps
│   ├── simulation.html         # Risk simulator interface
│   ├── coordination_dashboard.html  # Inter-department coordination
│   ├── volunteer_management.html    # Volunteer dispatch & tracking
│   ├── lifeline.html           # P2P resource marketplace
│   ├── lifeline_map.html       # LifeLine visual mapping
│   ├── community_hub.html      # Community volunteering hub
│   ├── eco_tracker.html        # Eco-sustainability tracker
│   ├── notifications.html      # Alert center
│   ├── reels.html              # Social report sharing
│   └── ...                     # 34+ additional templates
│
├── migrations/             # Flask-Migrate Alembic database migrations
└── instance/               # SQLite database file (gitignored)
```

---

## 🗄️ Database Schema

The application uses **23 database models** managed via SQLAlchemy + Flask-Migrate:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE MODELS                                    │
├──────────────────┬──────────────────────────────────────────────────────┤
│ User             │ id · username · email · password_hash · role          │
│                  │ points · level · language · home_lat/lon              │
│                  │ whatsapp_number · whatsapp_session (multi-step)       │
│                  │ alert_preferences (JSON) · push_token                 │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Report           │ id · title · description · hazard_type · location     │
│                  │ latitude · longitude · image_file · video_file        │
│                  │ confidence_score · ai_analysis · priority             │
│                  │ verification_status (pending/approved/rejected)       │
│                  │ alert_radius · alert_sent · likes/comments/views      │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Notification     │ id · user_id · message · report_id · assignment_id   │
│                  │ is_read · is_alert · created_at · expires_at          │
├──────────────────┼──────────────────────────────────────────────────────┤
│ Like / Comment   │ Social interaction models                             │
│ LocalApproval    │ Crowd-verification of reports                         │
│ ReportView       │ Unique view tracking per user                         │
│ Badge / UserBadge│ Achievement system                                    │
│ followers        │ Association table (user ↔ user)                      │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      COORDINATION MODELS                                 │
├──────────────────┬──────────────────────────────────────────────────────┤
│ Agency           │ Government / NGO registry with contact details        │
│ EmergencyEvent   │ Formal incident creation by officials                 │
│ ResourceAlloc.   │ Agency resource → event allocation tracking          │
│ Volunteer        │ Profile: skills, availability, location, certif.      │
│ VolunteerAssign. │ Lifecycle: pending→accepted→en_route→completed       │
│ SituationReport  │ Structured field reports (SITREPs)                    │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                 SUSTAINABILITY & COMMUNITY MODELS                        │
├──────────────────┬──────────────────────────────────────────────────────┤
│ PlasticUsage     │ Plastic reduction log with AI verification            │
│ CarbonSavings    │ General eco-activity carbon offset records            │
│ CommunityEvent   │ Environmental meetups (beach cleanup, tree planting)  │
│ EventParticipant │ User ↔ CommunityEvent participation                 │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      LIFELINE P2P MODELS                                 │
├──────────────────┬──────────────────────────────────────────────────────┤
│ ResourceListing  │ Have / Need listings (food, water, medical, shelter)  │
│ ResourceMatch    │ SafeLink™ matching engine (donor ↔ requester)       │
└──────────────────┴──────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                URBAN RESILIENCE INDEX (URI) MODELS                       │
├──────────────────┬──────────────────────────────────────────────────────┤
│ ResilienceZone   │ Geographic grid zones for scoring                     │
│ ResilienceScore  │ Historical 0–100 URI scores per zone + period        │
└──────────────────┴──────────────────────────────────────────────────────┘
```

---

## 🎮 User Roles & Permissions

| Role | Who | Key Permissions |
|:---|:---|:---|
| `citizen` | General public | Submit reports, join LifeLine, earn points, participate in community events |
| `volunteer` | Registered responders | Accept rescue missions, complete assignments, upload proof, earn rescue points |
| `official` | Government officers | Approve/reject reports, create emergencies, assign volunteers, view all dashboards, issue certifications |
| `analyst` | Data scientists / planners | Full access to analyst dashboard, risk simulator, TGDPS maps, URI data, all analytics |
| `agency` | NGO / Emergency org | Manage agency resources, create SITREPs, coordinate cross-department responses |

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Notes |
|:---|:---|
| **Python 3.9+** | Tested on 3.11 |
| **Twilio Account** | Free trial works; needs WhatsApp Sandbox enabled |
| **Ngrok / tunnel** | Required for local WhatsApp webhook testing only |

### 1. Clone & Set Up Environment

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
DATABASE_URL=sqlite:///site.db       # For production: postgresql://user:pass@host/db

# --- Twilio WhatsApp ---
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886   # Twilio Sandbox number

# --- Optional ---
BASE_URL=https://your-ngrok-subdomain.ngrok-free.app
FIREBASE_SERVER_KEY=your_firebase_key    # For push notifications
```

### 3. Initialise the Database

```bash
flask db upgrade
```

### 4. Run the Application

```bash
python app.py
# Server starts on http://0.0.0.0:5001
# Access locally: http://localhost:5001
```

### 5. Expose to Internet (For WhatsApp Testing)

```bash
ngrok http 5001
# Set webhook URL in Twilio Console:
# https://YOUR-TUNNEL-URL/webhook/whatsapp
```

---

## 📡 API Reference

All JSON endpoints require authentication via session cookie unless noted.

### Reports & Detection

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/reports` | ✅ | Paginated list of all reports |
| `GET` | `/api/hazards/active` | ✅ | Active hazards for map overlay |
| `GET` | `/api/report/<id>/accuracy_3param` | ✅ | Full 3-param AI accuracy breakdown |
| `POST` | `/report` | ✅ | Submit a new hazard report |
| `POST` | `/api/submit_sos` | ✅ | Submit emergency SOS with audio + GPS |
| `POST` | `/verify_report/<id>` | 🔐 Official | Approve/reject a pending report |

### Coordination & Dispatch

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/api/coordination/assign-volunteer` | 🔐 Official | Assign volunteer to hazard |
| `POST` | `/api/coordination/assignment/respond` | ✅ Volunteer | Accept/decline assignment |
| `POST` | `/api/coordination/assignment/<id>/complete` | ✅ | Complete with proof photo |
| `GET` | `/api/coordination/volunteers/nearby` | 🔐 Official | Find volunteers within radius |
| `GET` | `/api/coordination/assignments/active` | 🔐 Official | Active assignments list |

### Analytics & Weather

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/weather_data` | ✅ | Live weather from Open-Meteo |
| `GET` | `/api/live_hazard_incidents` | ✅ | Active incidents for maps |
| `GET` | `/api/live_govt_hazards` | ✅ | Government-sourced hazard data |
| `GET` | `/api/proxy/tgdps_map?path=aws.jsp` | Public | Proxied TGDPS state rainfall map |
| `GET` | `/api/proxy/tgdps_map?path=livejsp/Hyderabad.jsp` | Public | District-level rainfall map |
| `POST` | `/api/simulate_impact` | ✅ | Risk simulation engine |

### Notifications

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/api/notifications/unread-count` | ✅ | Unread count (polled every 5s) |
| `POST` | `/api/notification/<id>/read` | ✅ | Mark notification as read |
| `POST` | `/clear_all_notifications` | ✅ | Clear all notifications |

### Community & LifeLine

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `GET` | `/lifeline` | ✅ | LifeLine P2P marketplace |
| `POST` | `/lifeline/create` | ✅ | Create resource listing (have/need) |
| `GET` | `/lifeline/map` | ✅ | Visual resource match mapping |
| `GET` | `/community_hub` | ✅ | Community events listing |
| `POST` | `/community/create` | ✅ | Create community event |
| `GET` | `/api/eco_stats` | ✅ | Eco-tracker statistics |

### WhatsApp

| Method | Endpoint | Auth | Description |
|:---|:---|:---|:---|
| `POST` | `/webhook/whatsapp` | Twilio | Inbound message handler |

---

## 📱 WhatsApp Bot

### Flow 1: Account Linking

```
User  →  "Hi"
Bot   →  "👋 Welcome to Sentinel AI! Please enter your username."
User  →  "john_doe"
Bot   →  "🔐 Please enter your password."
User  →  "••••••••"
Bot   →  "✅ Successfully linked! You'll now receive hazard alerts
          and volunteer assignments directly on WhatsApp."
```

### Flow 2: Volunteer Dispatch

```
[Hazard verified by system]

Bot   →  📸 [Hazard photo attached]
Bot   →  "🚨 *STORM SURGE ALERT*
          Location: Marina Beach, Chennai
          Distance: 3.2 km from you
          Severity: HIGH

          🤝 Your help is needed.
          Reply *1* to Accept
          Reply *2* to Decline"

User  →  "1"
Bot   →  "✅ *Mission Accepted!*
          📍 Hazard coordinates: 13.0566, 80.2783
          Reply *cancel* at any time."

[Volunteer completes rescue]
Bot   →  "🏆 Mission completed! You earned 50 points.
          Total: 340 points | Level: 7"
```

### Supported Commands

| Command | Response |
|:---|:---|
| `status` | Current assignment status |
| `cancel` | Cancel active assignment |
| `help` | List available commands |
| `Hi` / `hello` | Start account linking flow |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Language** | Python 3.9+ | Backend runtime |
| **Web Framework** | Flask ≥ 2.3.3 | HTTP server, routing, templating |
| **Auth** | Flask-Login ≥ 0.6.3 | Session management |
| **Forms** | Flask-WTF + WTForms | Server-side validation |
| **ORM** | Flask-SQLAlchemy ≥ 3.1.1 | Database abstraction |
| **Migrations** | Flask-Migrate (Alembic) | Schema version control |
| **Task Scheduler** | APScheduler ≥ 3.10.5 | Background jobs |
| **Messaging** | Twilio ≥ 9.0.0 | WhatsApp API |
| **Weather API** | Open-Meteo | Free live weather data |
| **Rainfall Data** | TGDPS (Telangana Govt) | Live state + district rainfall maps |
| **Maps** | Leaflet.js | Interactive maps + heatmaps |
| **Map Tiles** | OpenStreetMap / Voyager | Base map tiles |
| **Weather Radar** | RainViewer | Satellite precipitation overlay |
| **Charts** | Matplotlib + NumPy | Server-rendered analytics |
| **NLP** | TextBlob + NLTK | Report text analysis + SOS parsing |
| **DB (dev)** | SQLite | Development database |
| **DB (prod)** | PostgreSQL ≥ 14 | Production database |
| **WSGI** | Gunicorn ≥ 21.2 | Production app server |
| **Frontend** | Bootstrap 5 + Glassmorphism CSS | UI framework |
| **PWA** | Service Worker + Manifest | Installable web app |
| **Media** | Pillow ≥ 10.2 | Image processing |

---

## ☁️ Deployment

### Render (Recommended)

1. Push to GitHub
2. Create a **Web Service** on [render.com](https://render.com)
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn app:app`
5. Add environment variables from `.env`
6. Add free **PostgreSQL** database add-on
7. Deploy!

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

---

## 🔐 Security

- Passwords hashed with **Werkzeug PBKDF2-HMAC-SHA256**
- All forms protected by **CSRF tokens** (Flask-WTF)
- Role-based access control on every sensitive endpoint
- File uploads sanitised via `secure_filename` + extension allowlist
- Upload limit: **16 MB** — Allowed: `png jpg jpeg gif mp4 mov avi`
- Twilio webhook signature validation (recommended for production)
- TGDPS proxy route includes path traversal protection

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

**Built with ❤️ for Smart India Hackathon — SH-SVA-03**

*"Every minute in a disaster matters. Sentinel AI turns hours into seconds — unifying departments, empowering communities, saving lives."*

**116 API Routes · 23 Database Models · 48 Templates · 6 Languages · 5 AI Agents**

[⭐ Star this repo](https://github.com/varunmax7/sentinelai) if you find it useful!

</div>
