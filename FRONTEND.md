# Frontend Documentation — Sentinel AI Disaster Management Platform

## Tech Stack

| Layer | Library / Tool | Version |
|---|---|---|
| CSS Framework | Bootstrap | 5.x |
| Fonts | Outfit (Google Fonts) | 300–800 |
| Icons | Font Awesome | 6.x |
| Map Engine (Primary) | MapLibre GL JS | 3.6.2 |
| Map Engine (Dashboard) | Leaflet.js | 1.9.4 |
| Heatmap Plugin | Leaflet.heat | — |
| Charts | Chart.js | 4.4.0 |
| PDF Export | jsPDF + html2canvas | 2.5.1 / 1.4.1 |
| Satellite Tiles | ESRI World Imagery | (no API key) |
| Base Map Tiles | CARTO Voyager GL | (no API key) |
| Live Weather Maps | Windy Embed | embed2.html |
| Templating | Jinja2 (Flask) | — |

---

## Global Layout — `base.html`

### Navbar
- Fixed sticky navbar (70px) with Sentinel AI branding
- Responsive hamburger menu with backdrop overlay
- Language selector — 6 languages: English, Tamil, Hindi, Telugu, Malayalam, Kannada
- Notification bell with unread count badge (polls every 3 seconds)
- User profile dropdown — username, level badge, quick links
- Role-gated nav items — Professional Tools visible to Officials and Analysts only
- **Report** button (red) always visible in navbar
- **Complete Rescue** button (cyan) — conditionally shown when user has an active rescue assignment (checks every 30 seconds)

### Navigation Structure
- Home, About
- Community — Reels, Community Hub, LifeLine P2P
- Professional Tools *(Officials/Analysts only)* — Coordination Platform, Basic Dashboard, Analyst Dashboard, Risk Simulator, Emergency Management, Resource Management, Volunteer Management, Situation Reports, Search

### Floating Action Buttons (Fixed, Bottom-Right)
1. 🚨 Report Hazard
2. 🤝 Be a Volunteer
3. 🧭 Coordination Platform *(Officials only)*
4. 🤖 AI Assistant
5. 🆘 SOS Panic Mode *(with pulse animation)*

### SOS Panic Mode
- Full-screen modal with dark red theme
- Real-time voice transcription via Web Speech API
- GPS location with high-accuracy mode
- Status indicator — "GPS Locked" vs "Approximate"
- Submits to `/api/submit_sos`; auto-redirects on success

### AI Assistant (Chatbot)
- Slide-in modal with embedded iframe
- Powered by external Replit-hosted chatbot server
- Available on every page via floating button

### Flash Message System
- Type-aware alert banners (success / danger / warning / info)
- Each type has a paired icon
- Dismissible via close button
- Only Flask flash messages trigger this (not generic `.alert` divs)

### Footer
- Two-column layout (desktop), stacked (mobile)
- Quick links: Home, About, Reels, Community Hub, Coordination
- Social media icons: Twitter, Facebook, LinkedIn
- Copyright + organization collaboration notice

### Global Styling Tokens
```
--primary:   #0ea5e9
--danger:    #ef4444
--success:   #10b981
--warning:   #f59e0b
--info:      #06b6d4
--dark-bg:   #0f172a
```
- Glassmorphism cards — `backdrop-filter: blur(12–25px)`
- RTL language support (Arabic, Hebrew, Farsi, Urdu)
- Smooth scroll, fade-in on load, slide-in toast notifications

---

## Homepage — `index.html`

### Full-Screen Hero Map
- Leaflet.js map with ESRI World Imagery satellite tiles (100vh)
- Animated gradient overlay (dark top-to-bottom)
- "Sentinel AI ACTIVE" blinking status banner
- Auto-zooms to user's current location via Geolocation API (flyTo animation)
- Reverse geocoding via Nominatim — displays city, state, country in badge
- Pulsing user marker with animated rings and 500m radius circle

### Climate / Weather Panel (Top-Right Overlay)
- Collapsible weather widget (state saved to localStorage)
- Live data from Open-Meteo and AQI APIs
- Displays: temperature, weather condition icon, humidity, wind speed, AQI level
- Color-coded AQI bar (green → yellow → orange → red)

### Search with Autocomplete
- Large search input with 200ms debounce
- Live dropdown below input as user types
- **Three result categories:**
  - Users — gradient avatar with initials, links to `/profile/username`
  - Reports — icon + title + location
  - Hazard Types — color badge
- Keyboard navigation: Arrow Up/Down to move, Enter to select, Escape to close
- Click outside to close
- Local instant filter for 10 built-in hazard suggestions
- Falls back to `/api/search?q=` for live results

### Quick Search Buttons
- Preset shortcut buttons with emojis (Tsunami, Storm Surge, Chennai, High Waves)
- Trending hazards list with live occurrence counts

### Feature Cards
- Report Hazard → `/report`
- Analytics Dashboard → `/dashboard`

### User Stats *(authenticated users)*
- Points, Reports Submitted, Level — 3-column grid
- Leaderboard link

### Community Activity Feed
- Last 3 community reports with avatar, hazard badge, location, timestamp

### Live Reports Sidebar
- Last 4 reports with title, hazard type badge, location, timestamp
- Camera icon if media is attached; click to go to `/view_report`

---

## Analyst Dashboard — `analyst_dashboard.html`

### Stats Bar (4 Cards)
| Card | Color |
|---|---|
| Total Incidents | Blue |
| Verification Rate % | Green |
| Active Personnel | Cyan |
| Pending Reports | Orange |

### Dual Map Row (50/50 Split) — Satellite Base
Both maps use **ESRI World Imagery satellite tiles** via the `GodModeMap` class:

1. **Incident Hotspots Heatmap** — Heatmap overlay from live report coordinates
2. **Weather & Early Warnings** — Live weather circles color-coded by severity; shockwave markers for active hazards; real-time data from `/api/weather_data`, `/api/live_hazard_incidents`, `/api/live_govt_hazards`

### TGDPS Live Rainfall Maps
1. **State-Level Rainfall** — Proxied iframe of TGDPS `aws.jsp` (750px, live government data)
2. **District-Level Rainfall** — Dropdown selector for 31 Telangana districts; iframe auto-refreshes every 30 seconds with cache-bust parameter

### Windy Embedded Maps
| Map | Overlay | Size |
|---|---|---|
| 🌡️ Live Temperature | `temp` | 50vh |
| 🛰️ Live Satellite View | `satellite` | 55vh |
| 🔥 Fire Danger Map | `firedanger` (ECMWF) | 55vh |

All Windy maps centered on India (lat 20.59, lon 78.96) with "Open Full ↗" links.

### Telangana Flood Monitoring Map (72vh) — Satellite
- MapLibre GL with ESRI satellite + reference label layers
- **6 major rivers** drawn as GeoJSON lines with cyan glow: Godavari, Krishna, Musi, Manjira, Pranahita, Bhima
- **17 CWC flood gauge stations** as interactive dot markers:
  - 🔴 Danger — Bhadrachalam, Mancherial, Kaleswaram
  - 🟠 High — Nandikonda, Jogulamba, Dummugudem, Asifabad, Yellandu
  - 🟡 Moderate — Nalgonda
  - 🟢 Normal — 9 stations
- Dot size is fixed (28px container); inner circle scales on hover without position shift
- Click → popup with water level, warning level, trend (Rising / Steady / Falling)
- Bottom-left legend; top-right counter tiles (Danger / High / Normal)
- "Google Flood Hub ↗" and "CWC Portal ↗" header buttons

### Charts (3-Column)
1. Hazard Distribution — Pie chart
2. Incident Velocity / Timeline — Line chart
3. Network Participation — Bar chart

### Incident Intelligence Log
- Table with columns: #ID, Timestamp, Type, Confidence %, Status
- First 10 rows shown; "Load More" expands remainder
- Status badges: approved / pending / rejected

### Global Alert Modal
- Location checklist (scrollable, max 400px)
- Select All checkbox with selected count tracker
- Send Alert button disabled until at least one location chosen
- Location detail: name, icon, coordinates, hazard type, severity, radius

---

## Risk Simulator — `simulation.html` (Sentinel Resilience Engine)

### Control Panel
- **Rainfall Intensity slider** — 0–300 mm/h
- **Sea Level Rise slider** — 0–15 m (0.1 m steps)
- **Time Horizon toggle** — Current / 2030 / 2050 (IPCC trajectories)
- **Sectoral Impact Bars** — Power Grid, Water Supply, Telecom (animated gradient fill, 0.8s cubic-bezier)
- **AI Strategic Insight box** — dynamically updated text with green pulse indicator

### Simulation Map — Satellite
- MapLibre GL via `GodModeMap` (pitch 55°, bearing -12.5°)
- **ESRI World Imagery satellite tiles** with reference labels
- Risk zone overlays rendered on simulation run (red / orange / blue)
- Risk intensity legend overlay (bottom-left)

### Metrics
- Population at Risk, Financial Risk (USD millions)

### Actions
- Reset — clears sliders
- Generate Assessment — POSTs to `/api/simulate_impact`, shows "ANALYZING…" spinner, renders returned zones + AI summary

---

## User Dashboard — `dashboard.html`

### Header Actions
- Export PDF (html2canvas → jsPDF)
- Register as Volunteer
- Refresh

### Stats (4 Cards)
- Total Reports, Active Hazards, Reports with Media, Top Hazard Type

### Map — Incident Hotspots
- Leaflet.js with heatLayer
- Toggle "Urban Resilience" overlay (colour-coded zones: green/yellow/red by score)
- Zone click → detail modal with resilience score, contributing factors, 30-day metrics, trend
- Reset map button

### Hazard Distribution Chart
- Chart.js doughnut, color-coded by hazard type

### Recent Submissions Table
- Columns: Incident (thumbnail), Type badge, Location, Status, Action
- Row hover effect; green/red status badges; View Details button

---

## Coordination Dashboard — `coordination_dashboard.html`

### Stats (4 Cards)
- Active Events, Available Volunteers, Resources, Recent SitReps

### Priority Situations Panel
- Active emergency event cards — title, location, severity badge, hazard type badge, Connect button

### Situation Reports Panel
- Field report cards — title, content preview, priority badge

### Operations Console (4 Button Cards)
| Unit | Color | Destination |
|---|---|---|
| Emergency Command | Red | `/new_emergency` |
| Logistics Unit | Orange | `/resource_management` |
| Corps Personnel | Green | `/volunteer_management` |
| Agency Cloud | Cyan | `/agency_management` |

---

## GodModeMap Class — `static/js/god-mode-maps.js`

Shared mapping class used by Analyst Dashboard, User Dashboard, and Risk Simulator.

### Constructor Options
| Option | Default | Description |
|---|---|---|
| `style` | CARTO Voyager GL | MapLibre style object or URL |
| `center` | `[78.9, 20.5]` | Map center (India) |
| `zoom` | `4` | Initial zoom level |
| `showLiveUI` | `false` | Show "LIVE" badge top-right |

**Default view:** pitch 55°, bearing -12.5° (God-mode perspective)

### Methods
| Method | Description |
|---|---|
| `executeWhenLoaded(fn)` | Queue function until map tiles loaded |
| `addLiveUIBadge()` | Animated "LIVE" indicator top-right |
| `addPulsingDot()` | Canvas-rendered pulsing dot marker |
| `setHeatmapData(points)` | Render heatmap from `[lat, lng, intensity]` array |
| `addCirclePolygon(lat, lng, radius, color, opacity, html)` | Draw circle zone with popup |
| `addShockwaveMarker(lat, lng, html)` | Animated expanding-ring marker |
| `clearDynamicData()` | Remove all dynamically added layers and sources |
| `renderSimulationZones(zones)` | Render risk zones for the simulator |
| `setRainEffect(intensity)` | CSS filter rain visual effect |

---

## API Endpoints Called from Frontend

| Endpoint | Used By |
|---|---|
| `/api/search?q=` | Homepage autocomplete, trending hazards |
| `/api/submit_sos` | SOS panic mode |
| `/api/weather_data` | Analyst dashboard weather map |
| `/api/live_hazard_incidents` | Analyst dashboard incident map |
| `/api/live_govt_hazards` | Analyst dashboard warning map |
| `/api/weather_warnings` | Analyst dashboard warning circles |
| `/api/simulate_impact` | Risk simulator |
| `/api/resilience/zones` | Dashboard urban resilience overlay |
| `/api/resilience/zone/<id>` | Resilience zone detail modal |
| `/api/coordination/emergency/<id>/status` | Coordination dashboard |
| `/api/coordination/emergency/<id>/alert` | Send emergency alert |
| `/api/coordination/volunteers/match` | Volunteer matching |
| `/api/coordination/assignments/active` | Active rescue check (every 30s) |
| `/api/proxy/tgdps_map?path=` | Proxied TGDPS rainfall iframes |
| `/send_global_alert` | Analyst dashboard global alert modal |

---

## External Services

| Service | Purpose | API Key Required |
|---|---|---|
| ESRI World Imagery | Satellite base tiles | No |
| ESRI Reference Labels | City/boundary labels on satellite | No |
| CARTO Voyager GL | Light base map (fallback) | No |
| Windy Embed (`embed2.html`) | Temperature, Satellite, Fire Danger maps | No |
| Open-Meteo | Live temperature, humidity, wind | No |
| Open-Meteo AQI | Air quality index | No |
| Nominatim | Reverse geocoding on homepage | No |
| Google Flood Hub | Flood forecast link (external, not iframe) | No |
| CWC | River flood gauge data source | No |
| Replit Chatbot | AI assistant iframe | No |

---

## Responsive Breakpoints

| Breakpoint | Behaviour |
|---|---|
| < 400px | Extra-small phones — max font scaling, single column everything |
| < 576px | Mobile — hamburger nav, stacked cards, 2-col quick buttons |
| < 768px | Tablet portrait — sidebars collapse, maps full-width |
| < 992px | Tablet landscape — 2-col grids, reduced padding |
| ≥ 1200px | Desktop — full multi-column layouts |

---

## Accessibility

- Semantic HTML throughout (`<nav>`, `<main>`, `<footer>`, `<section>`)
- ARIA attributes: `aria-expanded`, `aria-label`, `role="button"`
- Keyboard navigation in autocomplete dropdown (Arrow Up/Down, Enter, Escape)
- Focus states on all interactive elements
- High-contrast color tokens
- Alt text on images
- RTL layout support for right-to-left languages

---

## PWA Support

- `manifest.json` — app name, icons, theme color, display mode
- `static/sw.js` — service worker for offline caching
- `static/js/pwa.js` — install prompt and offline sync registration
- `static/js/offline-sync.js` — queues actions made offline and replays on reconnect
- `templates/offline.html` — custom offline fallback page
