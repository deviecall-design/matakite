#!/usr/bin/env python3
"""
MATAKITE Fusion Server — Operation Kāhu
WebSocket backend for real-time dashboard data delivery.

Phase A: Mock data layer with live feed stubs.
Phase B: ESPN API integration — scoreboard, standings, plays, rosters.
         REST endpoints at /api/espn/* for dashboard to call directly.
         Polling loop syncs ESPN data into broadcast state every 30s (live).

Architecture:
  HTTP :3940  → serves dashboard HTML
  WS   :8080  → live broadcast (state diffs every 30s)
  REST :3940  → /api/espn/* endpoints (scoreboard, standings, roster, plays)
"""

import asyncio
import json
import logging
import os
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MATAKITE] %(message)s")
log = logging.getLogger(__name__)

WS_PORT = 8080
HTTP_PORT = 3940
DASHBOARD_FILE = "matakite-poc.html"

# ─── ESPN Config ──────────────────────────────────────────────────────────────

# Primary league (Super Rugby Pacific - All Blacks context)
# Override with MATAKITE_LEAGUE_ID env var for other leagues
ESPN_LEAGUE_ID = os.environ.get("MATAKITE_LEAGUE_ID", "242041")
ESPN_SITE_BASE = "https://site.api.espn.com"
ESPN_CORE_BASE = "https://sports.core.api.espn.com"
ESPN_TIMEOUT = 8  # seconds

# Cache TTLs (seconds)
CACHE_TTL_SCOREBOARD = 30
CACHE_TTL_STANDINGS = 3600    # 1 hour
CACHE_TTL_ROSTER = 86400      # 24 hours

# ─── ESPN API Helpers ─────────────────────────────────────────────────────────

_cache: dict = {}

def espn_fetch(url: str, timeout: int = ESPN_TIMEOUT) -> dict | None:
    """
    Fetch JSON from ESPN API with simple in-memory caching.
    Returns None on error (don't crash the server for a missed feed).
    """
    now = time.time()
    if url in _cache:
        data, ts = _cache[url]
        age = now - ts
        # Use cached value if fresh enough (caller sets TTL via cache key)
        if age < CACHE_TTL_SCOREBOARD:
            return data

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Matakite/0.2 rugby-intel/espn-integration"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            data = json.loads(body)
            _cache[url] = (data, now)
            return data
    except urllib.error.HTTPError as e:
        log.warning(f"ESPN HTTP {e.code}: {url}")
        return None
    except Exception as e:
        log.warning(f"ESPN fetch error {type(e).__name__}: {url} — {e}")
        return None


def espn_cache_with_ttl(url: str, ttl: int) -> dict | None:
    """Fetch with explicit TTL."""
    now = time.time()
    if url in _cache:
        data, ts = _cache[url]
        if now - ts < ttl:
            return data
    # Not fresh — force a new fetch by clearing
    if url in _cache:
        del _cache[url]
    return espn_fetch(url)


def espn_scoreboard(date: str | None = None) -> dict | None:
    base = f"{ESPN_SITE_BASE}/apis/site/v2/sports/rugby/{ESPN_LEAGUE_ID}/scoreboard"
    url = f"{base}?dates={date}" if date else base
    return espn_cache_with_ttl(url, CACHE_TTL_SCOREBOARD)


def espn_standings() -> dict | None:
    url = f"{ESPN_CORE_BASE}/v2/sports/rugby/leagues/{ESPN_LEAGUE_ID}/standings"
    return espn_cache_with_ttl(url, CACHE_TTL_STANDINGS)


def espn_teams() -> list:
    url = f"{ESPN_SITE_BASE}/apis/site/v2/sports/rugby/{ESPN_LEAGUE_ID}/teams"
    data = espn_cache_with_ttl(url, CACHE_TTL_ROSTER)
    if data:
        return data.get("teams", [])
    return []


def espn_team_roster(team_id: str) -> list:
    url = f"{ESPN_SITE_BASE}/apis/site/v2/sports/rugby/{ESPN_LEAGUE_ID}/teams/{team_id}/roster"
    data = espn_cache_with_ttl(url, CACHE_TTL_ROSTER)
    if data:
        return data.get("roster", data.get("athletes", []))
    return []


def espn_event(event_id: str) -> dict | None:
    url = f"{ESPN_CORE_BASE}/v2/sports/rugby/leagues/{ESPN_LEAGUE_ID}/events/{event_id}"
    return espn_fetch(url)


def espn_summary(event_id: str) -> dict | None:
    url = f"{ESPN_SITE_BASE}/apis/site/v2/sports/rugby/{ESPN_LEAGUE_ID}/summary?event={event_id}"
    return espn_cache_with_ttl(url, CACHE_TTL_SCOREBOARD)


def espn_plays(event_id: str, competition_id: str) -> list:
    url = f"{ESPN_CORE_BASE}/v2/sports/rugby/leagues/{ESPN_LEAGUE_ID}/events/{event_id}/competitions/{competition_id}/plays"
    data = espn_fetch(url)
    if data:
        return data.get("items", [])
    return []


def espn_officials(event_id: str, competition_id: str) -> list:
    url = f"{ESPN_CORE_BASE}/v2/sports/rugby/leagues/{ESPN_LEAGUE_ID}/events/{event_id}/competitions/{competition_id}/officials"
    data = espn_fetch(url)
    if data:
        return data.get("items", [])
    return []


def espn_news() -> list:
    url = f"{ESPN_SITE_BASE}/apis/site/v2/sports/rugby/{ESPN_LEAGUE_ID}/news"
    data = espn_fetch(url)
    if data:
        return data.get("articles", [])[:5]  # Top 5 headlines
    return []


# ─── State Transforms ─────────────────────────────────────────────────────────

def status_type_to_phase(status_type: str, period: int) -> str:
    s = status_type.upper()
    if "FINAL" in s:
        return "full-time"
    if "END_PERIOD" in s or "HALFTIME" in s:
        return "half-time"
    if "IN_PROGRESS" in s:
        return "first-half" if period <= 1 else "second-half"
    return "pre-match"


def clock_to_minute(display_clock: str | None) -> int:
    if not display_clock:
        return 0
    parts = display_clock.split(":")
    if len(parts) >= 2:
        try:
            return int(parts[0])
        except ValueError:
            return 0
    return 0


def extract_match_state(scoreboard: dict) -> dict | None:
    """
    Extract dashboard match state from ESPN scoreboard response.
    Returns None if no events found.
    """
    events = scoreboard.get("events", [])
    if not events:
        return None

    # Prefer in-progress
    event = next(
        (e for e in events if "IN_PROGRESS" in e.get("status", {}).get("type", {}).get("name", "")),
        events[0]
    )

    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})

    status = comp.get("status", {})
    status_type = status.get("type", {})
    status_name = status_type.get("name", "") if isinstance(status_type, dict) else str(status_type)
    period = status.get("period", 0)

    home_team = home.get("team", {})
    away_team = away.get("team", {})

    return {
        "id": event.get("id"),
        "home": home.get("displayName") or home_team.get("displayName", "Home"),
        "homeAbbr": home.get("abbreviation") or home_team.get("abbreviation", "HOM"),
        "homeLogo": home_team.get("logo", ""),
        "away": away.get("displayName") or away_team.get("displayName", "Away"),
        "awayAbbr": away.get("abbreviation") or away_team.get("abbreviation", "AWY"),
        "awayLogo": away_team.get("logo", ""),
        "venue": comp.get("venue", {}).get("fullName", "TBC"),
        "kickoff": event.get("date", ""),
        "minute": clock_to_minute(status.get("displayClock")),
        "phase": status_type_to_phase(status_name, period),
        "score": {
            "home": int(home.get("score", 0) or 0),
            "away": int(away.get("score", 0) or 0),
        },
        "status": status_name,
        "period": period,
        "league": ESPN_LEAGUE_ID,
        "source": "espn",
    }


def extract_standings(standings_data: dict) -> list:
    """
    Transform ESPN core standings response into dashboard rows.
    """
    rows = []
    rank = 1

    groups = standings_data.get("groups", [])
    if not groups:
        # Some leagues return flat standings
        groups = [{"teams": standings_data.get("teams", [])}]

    for group in groups:
        for entry in group.get("teams", []):
            team = entry.get("team", {})
            stats = {
                s["name"]: (s.get("value") or float(s.get("displayValue", 0) or 0))
                for s in entry.get("stats", [])
                if s.get("name")
            }

            rows.append({
                "rank": rank,
                "team": team.get("displayName", "Unknown"),
                "teamId": team.get("id", ""),
                "logo": team.get("logo", ""),
                "played": int(stats.get("gamesPlayed", stats.get("played", 0))),
                "wins": int(stats.get("wins", stats.get("won", 0))),
                "losses": int(stats.get("losses", stats.get("lost", 0))),
                "draws": int(stats.get("ties", stats.get("drawn", 0))),
                "points": int(stats.get("points", 0)),
                "pointsFor": int(stats.get("pointsFor", stats.get("scored", 0))),
                "pointsAgainst": int(stats.get("pointsAgainst", stats.get("conceded", 0))),
            })
            rank += 1

    return rows


def extract_roster(roster_data: list) -> list:
    """
    Transform ESPN roster into dossier-friendly athlete profiles.
    """
    profiles = []
    for athlete in roster_data[:23]:  # Max squad size (23 for rugby)
        stats_map = {
            s["name"]: s.get("value", 0)
            for s in athlete.get("statistics", [])
            if s.get("name")
        }
        profiles.append({
            "id": athlete.get("id"),
            "displayName": athlete.get("displayName"),
            "shortName": athlete.get("shortDisplayName", athlete.get("displayName")),
            "position": athlete.get("position", {}).get("displayName")
                        if isinstance(athlete.get("position"), dict)
                        else athlete.get("position", "—"),
            "jersey": athlete.get("jersey"),
            "age": athlete.get("age"),
            "height": athlete.get("height"),
            "weight": athlete.get("weight"),
            "active": athlete.get("active", True),
            "carries": stats_map.get("carries"),
            "metres": stats_map.get("metres") or stats_map.get("meters"),
            "tackles": stats_map.get("tackles"),
            "passes": stats_map.get("passes"),
        })
    return profiles


# ─── Shared State ─────────────────────────────────────────────────────────────

MOCK_STATE = {
    "match": {
        "id": "ABvRSA-20260822",
        "home": "New Zealand",
        "homeAbbr": "NZ",
        "homeLogo": "",
        "away": "South Africa",
        "awayAbbr": "RSA",
        "awayLogo": "",
        "venue": "Ellis Park, Johannesburg",
        "altitude_m": 1755,
        "kickoff": "2026-08-22T15:05:00+02:00",
        "minute": 0,
        "phase": "pre-match",
        "score": {"home": 0, "away": 0},
        "status": "STATUS_SCHEDULED",
        "period": 0,
        "league": ESPN_LEAGUE_ID,
        "source": "mock",
    },
    "prediction": {
        "win_prob_home": 0.47,
        "win_prob_away": 0.53,
        "confidence": 0.92,
        "brier_season": 0.151,
        "hit_rate": 0.74,
        "calibration_error": 0.038,
    },
    "battlegrounds": {
        "scrum": 0.61,
        "lineout": 0.38,
        "breakdown": 0.54,
        "territory": 0.51,
        "aerial": 0.43,
    },
    "the_call": {
        "action": "Maintain kick-to-corner strategy — Feinberg showing early fatigue",
        "expected_points": 2.3,
        "window_closes": "min 58",
        "confidence": 0.81,
    },
    "standings": [],
    "roster": [],
    "feeds": {
        "espn": {"name": "ESPN Core API", "source": "espn", "latency": "live", "status": "idle"},
        "opta": {"name": "Opta/Stats Perform", "source": "opta", "latency": "live", "status": "stub"},
        "gps": {"name": "GPS/IMU Telemetry", "source": "own", "latency": "live", "status": "stub"},
        "broadcast": {"name": "Broadcast Tracking", "source": "observed", "latency": "live", "status": "stub"},
        "mirofish": {"name": "MiroFish Swarm", "source": "modelled", "latency": "event-based", "status": "stub"},
    },
    "meta": {
        "provenance": ["OWN", "OBSERVED", "MODELLED"],
        "classification": "INTERNAL",
        "version": "v0.2-espn",
        "espnLeagueId": ESPN_LEAGUE_ID,
        "lastRefreshed": datetime.now(timezone.utc).isoformat(),
    },
}


def espn_sync_state():
    """
    Pull latest ESPN data into MOCK_STATE.
    Called by background polling loop + on REST requests.
    Returns True if something changed.
    """
    changed = False

    # 1. Scoreboard → match state
    sb = espn_scoreboard()
    if sb:
        match = extract_match_state(sb)
        if match:
            MOCK_STATE["match"] = match
            MOCK_STATE["feeds"]["espn"]["status"] = "live"
            MOCK_STATE["feeds"]["espn"]["lastFetched"] = datetime.now(timezone.utc).isoformat()
            changed = True
            log.info(f"ESPN sync: {match['home']} {match['score']['home']} — {match['score']['away']} {match['away']} [{match['phase']}]")
    else:
        MOCK_STATE["feeds"]["espn"]["status"] = "error"

    # 2. Standings (less frequent — uses TTL in espn_cache_with_ttl)
    standings_data = espn_standings()
    if standings_data:
        rows = extract_standings(standings_data)
        if rows:
            MOCK_STATE["standings"] = rows
            changed = True
            log.info(f"ESPN sync: {len(rows)} standings rows loaded")

    # 3. Update meta
    MOCK_STATE["meta"]["lastRefreshed"] = datetime.now(timezone.utc).isoformat()

    return changed


# ─── Mock Simulation (fallback when ESPN data unavailable) ───────────────────

def simulate_live_match(state: dict):
    """Advance match state by one phase (mock — only used when ESPN is unavailable)."""
    if state["match"].get("source") != "mock":
        return state  # Don't simulate if we have real data

    minute = state["match"]["minute"]
    if minute >= 80:
        return state

    state["match"]["minute"] = minute + random.randint(2, 5)

    drift = random.gauss(0, 0.02)
    state["prediction"]["win_prob_home"] = max(
        0.05, min(0.95, state["prediction"]["win_prob_home"] + drift)
    )
    state["prediction"]["win_prob_away"] = 1 - state["prediction"]["win_prob_home"]

    if random.random() < 0.12:
        team = "home" if random.random() < 0.47 else "away"
        pts = random.choice([3, 5, 7])
        state["match"]["score"][team] += pts
        log.info(f"[Mock] Score: {team} +{pts}")

    calls = [
        "Apply early lineout pressure — Kolbe tracking shallow",
        "Shift attack to right channel — Bomb Squad clock at T-6",
        "Kick to corner — Feinberg fatigue window open",
        "Box-kick left — aerial contest favoured",
        "Maul off lineout — scrum advantage > 60%",
    ]
    state["the_call"]["action"] = random.choice(calls)
    state["the_call"]["expected_points"] = round(random.uniform(1.2, 3.8), 1)

    return state


# ─── WebSocket Handler ────────────────────────────────────────────────────────

CONNECTED_CLIENTS = set()


async def ws_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    client = websocket.remote_address
    log.info(f"WS connected: {client} | Total: {len(CONNECTED_CLIENTS)}")

    try:
        await websocket.send(json.dumps({
            "type": "init",
            "payload": MOCK_STATE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

            elif msg_type == "request_update":
                # Force ESPN sync on explicit request
                espn_sync_state()
                await websocket.send(json.dumps({
                    "type": "state",
                    "payload": MOCK_STATE,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))

            elif msg_type == "subscribe_live":
                log.info(f"WS {client} subscribed to live stream")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        log.info(f"WS disconnected: {client} | Remaining: {len(CONNECTED_CLIENTS)}")


async def broadcast_loop():
    """Push state updates to all connected clients every 30s."""
    # Initial ESPN sync on startup
    await asyncio.get_event_loop().run_in_executor(None, espn_sync_state)

    while True:
        await asyncio.sleep(30)

        # Sync ESPN data
        await asyncio.get_event_loop().run_in_executor(None, espn_sync_state)

        # Fallback mock simulation if ESPN unavailable
        simulate_live_match(MOCK_STATE)

        if not CONNECTED_CLIENTS:
            continue

        payload = json.dumps({
            "type": "state",
            "payload": MOCK_STATE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        disconnected = set()
        for ws in CONNECTED_CLIENTS:
            try:
                await ws.send(payload)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(ws)

        CONNECTED_CLIENTS -= disconnected
        if CONNECTED_CLIENTS:
            log.info(
                f"Broadcast | {MOCK_STATE['match']['home']} "
                f"{MOCK_STATE['match']['score']['home']}–{MOCK_STATE['match']['score']['away']} "
                f"{MOCK_STATE['match']['away']} | {MOCK_STATE['match']['phase']} "
                f"min {MOCK_STATE['match']['minute']}"
            )


# ─── HTTP + REST Handler ──────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Suppress noisy HTTP logs

    def send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, path: str):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        # ── Dashboard HTML ──────────────────────────────────────────
        if path in ("", "/", "/index.html"):
            self.send_html(DASHBOARD_FILE)

        # ── ESPN REST Endpoints ─────────────────────────────────────

        elif path == "/api/espn/state":
            espn_sync_state()
            self.send_json(MOCK_STATE)

        elif path == "/api/espn/scoreboard":
            data = espn_scoreboard()
            match = extract_match_state(data) if data else None
            self.send_json({"match": match, "raw": data})

        elif path == "/api/espn/standings":
            data = espn_standings()
            rows = extract_standings(data) if data else []
            self.send_json({"standings": rows, "count": len(rows)})

        elif path == "/api/espn/teams":
            teams = espn_teams()
            self.send_json({"teams": teams, "count": len(teams)})

        elif path.startswith("/api/espn/roster/"):
            parts = path.split("/")
            team_id = parts[-1] if len(parts) > 4 else None
            if not team_id:
                self.send_json({"error": "team_id required"}, 400)
            else:
                roster = espn_team_roster(team_id)
                profiles = extract_roster(roster)
                self.send_json({"roster": profiles, "count": len(profiles)})

        elif path.startswith("/api/espn/event/"):
            parts = path.split("/")
            event_id = parts[-1] if len(parts) > 4 else None
            if not event_id:
                self.send_json({"error": "event_id required"}, 400)
            else:
                event = espn_event(event_id)
                self.send_json(event or {"error": "not found"}, 200 if event else 404)

        elif path.startswith("/api/espn/summary/"):
            parts = path.split("/")
            event_id = parts[-1] if len(parts) > 4 else None
            if not event_id:
                self.send_json({"error": "event_id required"}, 400)
            else:
                summary = espn_summary(event_id)
                self.send_json(summary or {"error": "not found"}, 200 if summary else 404)

        elif path == "/api/espn/news":
            articles = espn_news()
            self.send_json({"articles": articles, "count": len(articles)})

        elif path == "/api/health":
            self.send_json({
                "status": "ok",
                "version": "v0.2-espn",
                "leagueId": ESPN_LEAGUE_ID,
                "connectedClients": len(CONNECTED_CLIENTS),
                "cacheKeys": len(_cache),
            })

        else:
            self.send_error(404)


def run_http_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("", HTTP_PORT), DashboardHandler)
    log.info(f"HTTP server ready: http://localhost:{HTTP_PORT}")
    server.serve_forever()


# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 60)
    log.info("MATAKITE Fusion Server | Operation Kāhu")
    log.info("=" * 60)
    log.info(f"Dashboard:  http://localhost:{HTTP_PORT}")
    log.info(f"WebSocket:  ws://localhost:{WS_PORT}")
    log.info(f"ESPN League: {ESPN_LEAGUE_ID} (set MATAKITE_LEAGUE_ID to change)")
    log.info("Phase B: ESPN integration active")
    log.info("")
    log.info("REST Endpoints:")
    log.info("  GET /api/espn/state          — Full synced dashboard state")
    log.info("  GET /api/espn/scoreboard     — Live scoreboard (30s cache)")
    log.info("  GET /api/espn/standings      — League standings (1h cache)")
    log.info("  GET /api/espn/teams          — Team list")
    log.info("  GET /api/espn/roster/{id}    — Team roster by ID")
    log.info("  GET /api/espn/event/{id}     — Event detail")
    log.info("  GET /api/espn/summary/{id}   — Match summary + boxscore")
    log.info("  GET /api/espn/news           — Latest headlines")
    log.info("  GET /api/health              — Server health")
    log.info("=" * 60)

    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await asyncio.gather(broadcast_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Fusion server stopped.")
