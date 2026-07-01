# MATAKITE — Intelligence Platform
### Operation Kāhu · Rugby intelligence cell for All Blacks coaching staff

---

## Quick Start (Local POC)

```bash
cd ~/.openclaw/workspace/ventures/matakite

# Install backend dependency
pip3 install websockets

# Run fusion server (serves dashboard + WebSocket)
python3 fusion_server.py

# Dashboard opens at:
# http://localhost:3940
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  matakite-poc.html          (Static Frontend)           │
│  Command center dashboard · 7 tabs · Dark theme         │
└─────────────────────┬───────────────────────────────────┘
                      │ WebSocket (ws://localhost:8080)
┌─────────────────────▼───────────────────────────────────┐
│  fusion_server.py           (Python Backend)            │
│  WebSocket + HTTP server · Mock data · Broadcast loop   │
│  Phase B: Opta REST + Highlightly live events           │
└─────────────────────────────────────────────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `matakite-poc.html` | Full dashboard (7 tabs: Overview, Game Model, Forecast, Dossier, Calibration, Data Feeds, Live) |
| `fusion_server.py` | Python WebSocket server + HTTP dashboard server |
| `src/matakite-ontology.ts` | TypeScript data model with provenance tagging |
| `docs/` | Operating model + deployment guide |

---

## Tabs

| Tab | Status |
|-----|--------|
| Overview | ✅ Live — KPIs, Collection Plan, Priority Targets, The Cell |
| Game Model | ✅ Live — Ensemble prediction, Battleground forecasts |
| Forecast | ✅ Live — Score distributions, SA series |
| Dossier | 🔲 Next — Opponent dossier builder |
| Calibration | ✅ Live — Brier score, Reliability diagram, Scenario accuracy |
| Data Feeds | ✅ Live — Full feed register with provenance |
| Live | 🔲 Match day — WebSocket activated on game day |

---

## Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **A** | POC: Dashboard + Fusion server + Mock data | ✅ Complete |
| **B** | Real data: Opta/Highlightly API integration | 🔲 Next |
| **C** | Live Box View: Match-day WebSocket + The Call | 🔲 Pending |
| **D** | Cloud deploy: EC2/DigitalOcean + SSL + Auth | 🔲 Pending |

---

## Cloud Deployment (Phase D)

See `docs/deployment-guide.md`. Summary:

**Backend:** EC2 t3.small or DigitalOcean Droplet
- `pip install websockets`
- PM2 for process management
- Nginx reverse proxy for SSL (Let's Encrypt)
- Open ports 80, 443, 8080

**Frontend:** Vercel (static HTML)
- Push to GitHub → connect to Vercel
- Update WebSocket URL to `wss://your-domain.com`

**Security:**
- JWT token in WebSocket connection string
- IP whitelist for stadium/coaching box

---

## Data Feeds (Phase B integration targets)

| Provider | Endpoint | Tier |
|----------|----------|------|
| Highlightly | `https://rugby.highlightly.net` | Free → Paid |
| Data Sports Group | Sports XML feed | Paid (RWC teams) |
| API-Sports | REST API | $10/mo |
| Opta/Stats Perform | Licensed feed | Enterprise |

---

## Calibration (missing keystone)

The Accountability cell is live in the Calibration tab:
- Brier score per series + season
- Reliability diagram (forecast vs actual)
- Scenario accuracy log (The Call outcomes)

Post-match T+1 pipeline (Phase B): parse results → score predictions → retrain.

---

*Operation Kāhu · MATAKITE v0.1 | Deviecall*
