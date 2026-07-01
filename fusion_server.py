#!/usr/bin/env python3
"""
MATAKITE Fusion Server — Operation Kāhu
WebSocket backend for real-time dashboard data delivery.

Phase A: Mock data layer with live feed stubs.
Phase B: Connect to Opta/Highlightly API + GPS telemetry.
"""

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MATAKITE] %(message)s")
log = logging.getLogger(__name__)

WS_PORT = 8080
HTTP_PORT = 3940
DASHBOARD_FILE = "matakite-poc.html"

# ─── Mock Data Layer ──────────────────────────────────────────────────────────

MOCK_STATE = {
    "match": {
        "id": "ABvRSA-20260822",
        "home": "New Zealand",
        "away": "South Africa",
        "venue": "Ellis Park, Johannesburg",
        "altitude_m": 1755,
        "kickoff": "2026-08-22T15:05:00+02:00",
        "minute": 0,
        "phase": "pre-match",
        "score": {"home": 0, "away": 0},
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
    "feeds": {
        "opta": "observed",
        "gps": "own",
        "broadcast": "observed",
        "weather": "observed",
        "referee": "observed",
        "mirofish": "modelled",
    },
    "meta": {
        "provenance": ["OWN", "OBSERVED", "MODELLED"],
        "classification": "INTERNAL",
        "version": "v0.1",
    },
}


def simulate_live_match(state):
    """Advance match state by one phase (mock)."""
    minute = state["match"]["minute"]
    if minute >= 80:
        return state

    # Advance phase
    state["match"]["minute"] = minute + random.randint(2, 5)

    # Bayesian win-prob drift
    drift = random.gauss(0, 0.02)
    state["prediction"]["win_prob_home"] = max(
        0.05, min(0.95, state["prediction"]["win_prob_home"] + drift)
    )
    state["prediction"]["win_prob_away"] = (
        1 - state["prediction"]["win_prob_home"]
    )

    # Occasional scoring event
    if random.random() < 0.12:
        team = "home" if random.random() < 0.47 else "away"
        pts = random.choice([3, 5, 7])
        state["match"]["score"][team] += pts
        log.info(f"Score event: {team} +{pts}")

    # Update The Call
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
    log.info(f"Client connected: {client} | Total: {len(CONNECTED_CLIENTS)}")

    try:
        # Send initial state
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
                await websocket.send(json.dumps({
                    "type": "state",
                    "payload": MOCK_STATE,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))

            elif msg_type == "subscribe_live":
                log.info(f"Client {client} subscribed to live stream")

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        log.info(f"Client disconnected: {client} | Remaining: {len(CONNECTED_CLIENTS)}")


async def broadcast_loop():
    """Push state updates to all connected clients every 30s (match pace)."""
    while True:
        await asyncio.sleep(30)
        if not CONNECTED_CLIENTS:
            continue

        # Advance match state
        simulate_live_match(MOCK_STATE)

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
        log.info(
            f"Broadcast sent | min {MOCK_STATE['match']['minute']} "
            f"| score {MOCK_STATE['match']['score']} "
            f"| win-prob {MOCK_STATE['prediction']['win_prob_home']:.2f}"
        )


# ─── HTTP Server (serves the dashboard HTML) ─────────────────────────────────

class DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.path = f"/{DASHBOARD_FILE}"
        return super().do_GET()


def run_http_server():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("", HTTP_PORT), DashboardHandler)
    log.info(f"Dashboard: http://localhost:{HTTP_PORT}")
    server.serve_forever()


# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 60)
    log.info("MATAKITE Fusion Server | Operation Kāhu")
    log.info("=" * 60)
    log.info(f"Dashboard: http://localhost:{HTTP_PORT}")
    log.info(f"WebSocket: ws://localhost:{WS_PORT}")
    log.info("Phase A: Mock data layer active")
    log.info("=" * 60)

    # HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # WebSocket server + broadcast loop
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await asyncio.gather(broadcast_loop())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Fusion server stopped.")
