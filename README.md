# 🛡️ Sentinel AI

<div align="center">

[![JacHacks Spring 2026](https://img.shields.io/badge/JacHacks_Spring-2026-FF6B35?style=for-the-badge)](https://jachacks.devpost.com)
[![Track](https://img.shields.io/badge/Track-Social_Impact-00BFA5?style=for-the-badge)](https://jachacks.devpost.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Twilio](https://img.shields.io/badge/Twilio-WhatsApp_API-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)
[![Leaflet](https://img.shields.io/badge/Leaflet.js-Maps-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

### 🏆 Submission for JacHacks Spring 2026 — Social Impact Track

**A multi-agent AI command platform that turns hours of fragmented disaster response into seconds of autonomous, coordinated action.**

*Six specialized AI agents working in concert — Detection, Prioritization, Dispatch, Alert, Analytics, Coordination — unifying urban crisis management for India's 170M+ coastal residents.*

[The Problem](#-the-problem) • [Our Solution](#-our-solution) • [Multi-Agent Architecture](#-multi-agent-architecture) • [Demo](#-demo) • [Quick Start](#-quick-start) • [Roadmap](#-roadmap)

</div>

---

## 🎯 The Problem

India has **7,516 km of coastline** with **170+ million people** living in low-lying urban zones vulnerable to cyclones, floods, storm surges, and tsunamis. Yet when disaster strikes, urban response collapses under fragmentation:

| Failure Mode | Impact |
|:---|:---|
| **🏛️ Departmental Silos** | Fire, police, municipal, health, and disaster agencies operate on separate channels. A single flood requires 5+ departments to coordinate manually. |
| **⏱️ Hours-Long Detection** | Citizen reports of rising floodwater take hours to verify. Officials check social media. Volunteers wait for orders. |
| **📞 Manual Dispatch** | Coordinators phone volunteers one by one, losing precious minutes while lives are at stake. |
| **🌐 Language Barriers** | Critical alerts in English get ignored by Telugu, Tamil, Malayalam, Kannada, and Hindi-speaking communities. |
| **📊 No Predictive Power** | Agencies react to disasters — there's no city-wide digital twin to simulate impact ahead of time. |

**The cost:** Response times measured in hours. Lives lost that could have been saved.

---

## 🧠 Our Solution

**Sentinel AI is not just another disaster app — it's an autonomous multi-agent nervous system for urban crisis response.**

The platform deploys **six specialized AI agents** that perceive, reason, plan, and act across the entire disaster response lifecycle — from incident detection to community recovery.

### 🤖 Multi-Agent Architecture

Each agent has bounded responsibility, autonomous decision-making, and tool-use capabilities. They communicate through a shared state layer to coordinate without conflicts.

| Agent | Role | Autonomy | Tools Used |
|:---|:---|:---|:---|
| **🔍 Detection Agent** | Ingests citizen reports, SOS pings, AI phone calls, satellite data, and weather feeds. Performs multi-step reasoning to cross-validate hazards. | **Fully autonomous** | Open-Meteo API, NLP (TextBlob/NLTK), Geo-spatial clustering |
| **📋 Prioritization Agent** | Scores every incident via a 3-parameter accuracy system (heatmap + climate + user credibility). Auto-approves ≥85% confidence reports. | **Fully autonomous** | Weighted scoring, historical user memory, Haversine geo-distance |
| **🚁 Dispatch Agent** | Uber-style volunteer matching within 10km. Plans skill-matched assignments, fires WhatsApp messages, tracks acceptance/completion. | **Semi-autonomous** | Twilio WhatsApp API, geo-query, skill-filter, state machine |
| **📡 Alert Agent** | Geo-fenced 20km push notifications with disaster images, safe rescue coordinates, and multi-language translation. | **Fully autonomous** | Push notifications, multi-lingual translation tables, WhatsApp |
| **📊 Analytics Agent** | Powers the analyst dashboard with live TGDPS rainfall maps, satellite radar, risk simulators, and Urban Resilience Index. | **Continuous** | TGDPS proxy, RainViewer, Open-Meteo, Matplotlib, NumPy |
| **🤝 Coordination Agent** | Manages inter-departmental SITREPs, resource allocation, agency registry. Breaks silos through unified command dashboard. | **Semi-autonomous** | Agency registry, SITREP templating, resource ledger |

### Why Multi-Agent? Why Now?

Single-LLM apps fail at real-world crisis workflows because they can't maintain state across long horizons or coordinate parallel actions. **Sentinel AI's agents demonstrate true agentic AI:**

- ✅ **Planning** — Dispatch agent plans optimal volunteer-to-hazard matching
- ✅ **Tool use** — Every agent calls external APIs, databases, and messaging services
- ✅ **Memory** — User credibility scores build over time; agents learn from history
- ✅ **Multi-step reasoning** — Detection agent runs 3-parameter validation before approval
- ✅ **Inter-agent communication** — Agents pass verified incidents through a shared state pipeline

---

## ✨ Key Features

### 🚨 Omni-Channel Incident Reporting
- **Online PWA** — Form-based with photo/video upload, GPS auto-fill
- **Offline AI Calling Agent** — Citizens without internet call an AI agent that transcribes speech and creates reports
- **One-Tap Voice SOS** — Captures GPS, records audio, NLP extracts keywords, auto-elevates to Critical priority
- **WhatsApp Bot** — Full account linking + dispatch flow

### 🤖 3-Parameter AI Verification System

Every report is instantly scored by the Detection Agent:

| Parameter | Weight | How It Works |
|:---|:---|:---|
| **Heatmap Match** | 33% | Spatial density of similar reports in 5.5km / 24hr |
| **Climate Alignment** | 33% | Open-Meteo API validates weather supports the claim |
| **User Quality Score** | 34% | Historical credibility, approval rate, account age |

| Score | Action |
|:---|:---|
| ≥85% | 🟢 Auto-approved → alerts dispatched immediately |
| 60–84% | 🟡 Official review queue |
| 40–59% | 🟠 Held for investigation |
| <40% | 🔴 Flagged as potential misinformation |

### 🛰️ City Digital Twin (Analyst Dashboard)
- **RainViewer real-time precipitation radar**
- **TGDPS Live Rainfall Maps** — Telangana state + 33 districts, auto-refreshing
- **Risk Simulator** — Input rainfall + sea-level → AI predicts infra damage across Power/Water/Telecom/Housing
- **Urban Resilience Index (URI)** — Dynamic 0–100 score per geographic zone

### 🚁 Uber-Style Volunteer Dispatch
1. Query volunteers within 10km
2. Match by skills (medical, rescue, logistics)
3. Fire WhatsApp message with hazard photo + coordinates
4. Volunteer replies `1` Accept or `2` Decline
5. Track: `Pending → Accepted → En Route → Completed`
6. Upload completion proof → earn gamified points

### 📢 Smart Geo-Fenced Alerts (20km Radius)
- Reaches only users whose home falls within impact zone
- Includes disaster image + safe rescue coordinates
- Scaled radius per hazard type (15km storm surge, 2km localized swell)
- Multi-language auto-translation

### 🛟 LifeLine — P2P Emergency Resource Marketplace
- **SafeLink™ Matching** — Citizens list HAVE/NEED → algorithm pairs by proximity
- **Visual Map** — Glowing connection lines show successful matches
- **Unified View** — Citizen + government reports in one dashboard

### 🌐 Multi-Lingual (6 Languages, GPS Auto-Detected)
English · Telugu · Tamil · Malayalam · Kannada · Hindi

### 🏆 Gamification + Government Certification
Points, levels, badges, leaderboards. Top performers earn official government-recognized disaster response certificates.

---

## 🏗️ System Architecture
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER / PWA CLIENT                             │
│  Bootstrap 5 · Leaflet.js · Chart.js · Service Worker · MediaRecorder    │
└────────────────────────────┬─────────────────────────────────────────────┘
│ HTTPS
┌────────────────────────────▼─────────────────────────────────────────────┐
│                  FLASK APPLICATION (116 routes · 5,600+ LOC)             │
│                                                                           │
│  ┌───────────────────────── AGENT LAYER ────────────────────────────┐    │
│  │ 🔍 Detection · 📋 Prioritization · 🚁 Dispatch                    │    │
│  │ 📡 Alert · 📊 Analytics · 🤝 Coordination                         │    │
│  └────────────────────────────┬──────────────────────────────────────┘    │
│                               │                                           │
│  ┌────────────────────────────▼──────────────────────────────────────┐   │
│  │              SQLAlchemy ORM · 23 Database Models                  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌────────── APScheduler Background Jobs · Multi-Lingual Engine ────┐    │
│  └───────────────────────────────────────────────────────────────────┘   │
└────────────┬────────────┬────────────┬────────────┬─────────────────────┘
│            │            │            │
┌─────────▼─────┐ ┌────▼──────┐ ┌──▼────────┐ ┌─▼──────────────┐
│ Twilio        │ │ Open-Meteo│ │ TGDPS Gov │ │ RainViewer     │
│ WhatsApp API  │ │ Weather   │ │ Rainfall  │ │ Satellite Radar│
└───────────────┘ └───────────┘ └───────────┘ └────────────────┘

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Twilio Account (free trial works) with WhatsApp Sandbox enabled
- ngrok (for local WhatsApp webhook testing)

### Installation

```bash
git clone https://github.com/varunmax7/SentinelAI-JacHacks.git
cd SentinelAI-JacHacks

python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure Environment

Create a `.env` file:

```env
SECRET_KEY=your-long-random-string
DATABASE_URL=sqlite:///site.db
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
BASE_URL=https://your-ngrok-subdomain.ngrok-free.app
```

### Run

```bash
flask db upgrade
python app.py
# Server: http://localhost:5001
```

### Expose for WhatsApp (Optional)

```bash
ngrok http 5001
# Set webhook in Twilio: https://YOUR-TUNNEL/webhook/whatsapp
```

---

## 🎮 Demo

📹 **Demo Video:** https://youtu.be/3t-uq-Sa3Zo

🌐 **Live Demo:** _(deployment link if available)_

---

## 🛠️ Tech Stack

| Category | Technologies |
|:---|:---|
| **Backend** | Python 3.9+, Flask, SQLAlchemy, Flask-Migrate, APScheduler, Gunicorn |
| **Database** | SQLite (dev), PostgreSQL (prod) |
| **AI / NLP** | TextBlob, NLTK, custom 3-parameter scoring engine |
| **Messaging** | Twilio WhatsApp API |
| **Maps** | Leaflet.js, OpenStreetMap, RainViewer satellite overlay |
| **Weather** | Open-Meteo API, TGDPS Government Rainfall feeds |
| **Frontend** | Bootstrap 5, Glassmorphism CSS, Chart.js |
| **PWA** | Service Worker, Web App Manifest |
| **Analytics** | Matplotlib, NumPy |

---

## 📊 By the Numbers

- 🔢 **116** API routes
- 🗄️ **23** database models
- 📄 **48** HTML templates
- 🤖 **6** AI agents
- 🌐 **6** languages (auto-detected by GPS)
- 💻 **5,600+** lines of code

---

## 🗺️ Roadmap

### ✅ Built for JacHacks
- [x] 6-agent autonomous architecture
- [x] 3-parameter AI verification system
- [x] WhatsApp dispatch bot (end-to-end)
- [x] TGDPS government data integration
- [x] Multi-lingual GPS auto-detection
- [x] LifeLine P2P marketplace
- [x] PWA with offline support

### 🚀 Next Steps
- [ ] **Migrate core agent logic to Jac** — leverage walkers and graph-native data modeling for the multi-agent state machine
- [ ] Use `by llm()` for natural language hazard categorization
- [ ] Integrate INSAT satellite imagery for cyclone tracking
- [ ] Pilot deployment with Telangana district administration
- [ ] Expand to flood-prone North Indian regions (Bihar, UP)
- [ ] Predictive evacuation routing agent with real-time road conditions

---

## 🏆 Why This Wins

| Criteria | How Sentinel AI Delivers |
|:---|:---|
| **Technical Execution** | 5,600+ LOC, 116 endpoints, full PWA + WhatsApp integration, working end-to-end |
| **Agentic AI Depth** | True multi-agent architecture — six agents with planning, tool use, memory, and multi-step reasoning |
| **Creativity & Innovation** | 3-Parameter AI Verification, Uber-style WhatsApp dispatch, GPS-based language auto-detection, government data proxy |
| **Real-World Impact** | Addresses life-or-death problem for 170M+ Indians; production-ready architecture; clear path to government pilot |

---

## 🤝 Team

Built with passion for JacHacks Spring 2026.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

<div align="center">

**"Every minute in a disaster matters. Sentinel AI turns hours into seconds."**

⭐ Star this repo if you believe AI can save lives.

[🎬 Watch Demo](https://youtu.be/3t-uq-Sa3Zo) • [🐛 Report Bug](https://github.com/varunmax7/SentinelAI-JacHacks/issues) • [💡 Request Feature](https://github.com/varunmax7/SentinelAI-JacHacks/issues)

</div>
