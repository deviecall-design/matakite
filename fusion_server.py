#!/usr/bin/env python3
"""
MATAKITE Fusion Server — Operation Kāhu
WebSocket backend for real-time dashboard data delivery.

The dashboard scoreboard is the sourced 2026 All Blacks record in
data/all-blacks-2026.json. There is no prediction model.

ESPN league 242041 is Super Rugby Pacific. It is not the All Blacks
Test feed, and this server does not copy it onto the match state.
The random score simulator has been removed.

Architecture:
  HTTP :3940  → serves dashboard HTML
  WS   :8080  → live broadcast (state diffs every 30s)
  REST :3940  → /api/espn/* endpoints (scoreboard, standings, roster, plays)
"""

import asyncio
import json
import logging
import os
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

# ESPN league 242041 is Super Rugby Pacific, not All Blacks Tests.
# Kept only so the old debug endpoints still name the league they call.
# The dashboard does not treat this feed as the Test scoreboard.
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

def load_season() -> dict:
    """Sourced 2026 Test record. Same file the page renders."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "all-blacks-2026.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


SEASON = load_season()

NOT_CONNECTED = "not_connected"

MOCK_STATE = {
    "match": {
        "id": None,
        "home": "New Zealand",
        "homeAbbr": "NZ",
        "homeLogo": "",
        "away": None,
        "awayAbbr": None,
        "awayLogo": "",
        "venue": None,
        "minute": None,
        "phase": "no match today",
        "score": None,
        "status": "NO_LIVE_TEST",
        "source": "none",
        "note": "No All Blacks Test is live. Results are in data/all-blacks-2026.json.",
    },
    "prediction": None,
    "modelConnected": False,
    "battlegrounds": None,
    "the_call": None,
    "standings": [],
    "roster": [],
    "season": SEASON.get("derived"),
    "feeds": {
        "espn": {"name": "ESPN", "status": NOT_CONNECTED, "note": "League 242041 is Super Rugby Pacific, not All Blacks Tests."},
        "opta": {"name": "Opta/Stats Perform", "status": NOT_CONNECTED},
        "gps": {"name": "GPS/IMU Telemetry", "status": NOT_CONNECTED},
        "biometrics": {"name": "Biometrics", "status": NOT_CONNECTED},
        "weather": {"name": "Weather / Venue", "status": NOT_CONNECTED},
        "referee": {"name": "Referee Intelligence", "status": NOT_CONNECTED},
        "broadcast": {"name": "Broadcast Tracking", "status": NOT_CONNECTED},
        "mirofish": {"name": "MiroFish Swarm", "status": NOT_CONNECTED},
        "coaching_dna": {"name": "Coaching DNA", "status": NOT_CONNECTED},
        "scouting": {"name": "Scouting Network", "status": NOT_CONNECTED},
    },
    "meta": {
        "provenance": ["sourced-record"],
        "classification": "PUBLIC_REPORTING",
        "version": "v0.3-sourced-2026",
        "dataAsOf": SEASON["meta"]["asOf"],
        "espnLeagueId": ESPN_LEAGUE_ID,
        "espnUsedForScoreboard": False,
        "lastRefreshed": SEASON["meta"]["asOf"],
    },
}


def espn_sync_state():
    """
    Do not copy ESPN into the All Blacks match.

    League 242041 is Super Rugby Pacific. Writing that scoreboard
    onto this dashboard would present the wrong competition as a
    Test, and the old code then left typed-in win probabilities in place.
    """
    MOCK_STATE["feeds"]["espn"]["status"] = NOT_CONNECTED
    return False


# ─── Mock Simulation (fallback when ESPN data unavailable) ───────────────────

def simulate_live_match(state: dict):
    """Disabled. This used to invent scores, win chances and coaching calls."""
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
    """Tell connected clients there is no live Test and no model.

    CONNECTED_CLIENTS is a module global. Do not rebind it with -=
    or Python treats the name as local and the loop crashes.
    """
    while True:
        await asyncio.sleep(30)
        if not CONNECTED_CLIENTS:
            continue

        payload = json.dumps({
            "type": "state",
            "payload": MOCK_STATE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        disconnected = set()
        for ws in list(CONNECTED_CLIENTS):
            try:
                await ws.send(payload)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(ws)

        CONNECTED_CLIENTS.difference_update(disconnected)


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

    def send_data_file(self, rel: str):
        """Serve only the sourced record and the source list."""
        root = os.path.dirname(os.path.abspath(__file__))
        allowed = {
            "data/all-blacks-2026.json": "application/json; charset=utf-8",
            "data/SOURCES.md": "text/markdown; charset=utf-8",
        }
        if rel not in allowed:
            self.send_error(404)
            return
        full = os.path.join(root, rel)
        try:
            with open(full, "rb") as handle:
                body = handle.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", allowed[rel])
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
            self.send_json(MOCK_STATE)

        elif path == "/api/season":
            self.send_json(SEASON)

        elif path.startswith("/data/"):
            self.send_data_file(path.lstrip("/"))

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
                "version": "v0.3-sourced-2026",
                "modelConnected": False,
                "leagueId": ESPN_LEAGUE_ID,
                "espnUsedForScoreboard": False,
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
    log.info("Scoreboard: sourced 2026 record. No prediction model. ESPN is not the Test feed.")
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
