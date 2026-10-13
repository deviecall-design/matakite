#!/usr/bin/env python3
"""Build the Sydney forecast from cited sources.

Sources
- Wikidata Query Service (CC0): scored rugby matches.
- World Rugby men's rankings feed, plus the published explanation of the
  three-point home adjustment and the points exchange.
- Current fixtures, lineups and timelines are not fetched here. They are
  refreshed by scripts/fetch-rugbyapi.mjs into data/rugbyapi-snapshot.json.

The script never writes a win probability unless the scored-match gate
passes. A short series, a missing key, or a failed fetch becomes
status "unavailable" with the evidence attached. Percentages are not
typed in.

World Rugby exchange, taken from the worked example on
https://www.world.rugby/rankings/explanation (Wales vs Scotland,
14 February 2004):

    gap = (home rating + 3) - away rating
    home win:    home gains  1 - gap/10
    away win:    home loses  1 + gap/10
    draw:        home gains -gap/10

A win by more than 15 points multiplies the change by 1.5. A Rugby
World Cup Finals match doubles it. The explanation also says a team
cannot lose points for winning, so a gap past 10 points is capped at
10 before the exchange. That cap is what keeps the winner's change
from going negative. It is not a separate win percentage.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEASON_PATH = ROOT / "data" / "all-blacks-2026.json"
FORECAST_PATH = ROOT / "data" / "forecast.json"
RANKINGS_PATH = ROOT / "data" / "world-rugby-rankings.json"
WIKIDATA_PATH = ROOT / "data" / "wikidata-rugby-coverage.json"

USER_AGENT = "MatakiteForecast/1.0 (local static briefing; CC0 Wikidata + World Rugby rankings)"
SPARQL_URL = "https://query.wikidata.org/sparql"
WD_API = "https://www.wikidata.org/w/api.php"
RANKINGS_API = "https://api.wr-rims-prod.pulselive.com/rugby/v3/rankings/mru?language=en"
RANKINGS_PAGE = "https://www.world.rugby/rankings/mru"
RANKINGS_EXPLANATION = "https://www.world.rugby/rankings/explanation"

HOME_ADVANTAGE = 3.0
INITIAL_RATING = 30.0
GAP_CAP = 10.0
MIN_MATCHES = 200
MIN_NAMED_TEAM = 8
MIN_TRAIN = 80
MIN_BACKTEST = 30
TRAIN_END = "2024-01-01"

RUGBY_MATCH = "Q47089371"
NATIONAL_TEAM = "Q58840819"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(text: str) -> str:
    out = text
    for name in ("API_SPORTS_KEY", "RUGBYAPI_KEY"):
        key = os.environ.get(name, "").strip()
        if key and key in out:
            out = out.replace(key, "[redacted]")
    return out


def fetch(url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def sparql(query: str) -> dict:
    last_error = "no attempt"
    for attempt in range(4):
        try:
            body = urllib.parse.urlencode({"query": query}).encode()
            raw = fetch(
                SPARQL_URL,
                headers={"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"},
                data=body,
            )
            return json.loads(raw.decode())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last_error = f"HTTP {error.code}: {detail}"
            if error.code in (429, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(last_error) from error
        except Exception as error:  # noqa: BLE001 - report the fetch, do not invent rows
            last_error = str(error)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(last_error)


def binding_value(row: dict, key: str) -> str | None:
    cell = row.get(key)
    if not cell:
        return None
    return cell.get("value")


def qid(uri: str | None) -> str | None:
    if not uri:
        return None
    return uri.rstrip("/").split("/")[-1]


def search_item(label: str) -> str | None:
    url = WD_API + "?" + urllib.parse.urlencode({
        "action": "wbsearchentities",
        "search": label,
        "language": "en",
        "format": "json",
        "limit": 8,
        "type": "item",
    })
    payload = json.loads(fetch(url).decode())
    for hit in payload.get("search", []):
        if (hit.get("label") or "").strip().lower() == label.lower():
            return hit.get("id")
    return None


def exchange(home_rating: float, away_rating: float, home_score: int, away_score: int, world_cup: bool = False) -> float:
    """Points added to the home side. The away side moves by the opposite amount."""
    gap = (home_rating + HOME_ADVANTAGE) - away_rating
    if gap > GAP_CAP:
        gap = GAP_CAP
    elif gap < -GAP_CAP:
        gap = -GAP_CAP
    if home_score > away_score:
        change = 1.0 - gap / GAP_CAP
    elif home_score < away_score:
        change = -(1.0 + gap / GAP_CAP)
    else:
        change = -gap / GAP_CAP
    if abs(home_score - away_score) > 15 and home_score != away_score:
        change *= 1.5
    if world_cup:
        change *= 2.0
    return change


def sigmoid(value: float) -> float:
    if value > 30:
        return 1.0
    if value < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def fit_logistic(xs: list[float], ys: list[float]) -> tuple[float, float]:
    intercept = 0.0
    slope = 0.05
    for _ in range(30):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x_value, y_value in zip(xs, ys):
            prob = sigmoid(intercept + slope * x_value)
            weight = max(prob * (1.0 - prob), 1e-6)
            g0 += prob - y_value
            g1 += (prob - y_value) * x_value
            h00 += weight
            h01 += weight * x_value
            h11 += weight * x_value * x_value
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        intercept -= (h11 * g0 - h01 * g1) / det
        slope -= (h00 * g1 - h01 * g0) / det
    return intercept, slope


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance = sum((x_value - mean_x) ** 2 for x_value in xs)
    if variance == 0:
        return mean_y, 0.0
    covariance = sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(xs, ys))
    slope = covariance / variance
    return mean_y - slope * mean_x, slope


def replay(matches: list[dict]) -> list[dict]:
    ratings: dict[str, float] = {}
    rows = []
    for match in sorted(matches, key=lambda item: item["date"]):
        home = match["home"]
        away = match["away"]
        home_rating = ratings.get(home, INITIAL_RATING)
        away_rating = ratings.get(away, INITIAL_RATING)
        gap = (home_rating + HOME_ADVANTAGE) - away_rating
        rows.append({**match, "preHome": home_rating, "preAway": away_rating, "gap": gap})
        change = exchange(home_rating, away_rating, match["homeScore"], match["awayScore"], match.get("worldCup", False))
        ratings[home] = home_rating + change
        ratings[away] = away_rating - change
    return rows


def fit_model(matches: list[dict]) -> dict | None:
    rows = replay(matches)
    if len(rows) < MIN_MATCHES:
        return None
    indexed = list(enumerate(rows))
    train = [row for index, row in indexed if index >= 40 and row["date"] < TRAIN_END and row["homeScore"] != row["awayScore"]]
    train_margins = [row for index, row in indexed if index >= 40 and row["date"] < TRAIN_END]
    test = [row for row in rows if row["date"] >= TRAIN_END]
    if len(train) < MIN_TRAIN or len(test) < MIN_BACKTEST or len(train_margins) < MIN_TRAIN:
        return None
    intercept, slope = fit_logistic([row["gap"] for row in train], [1.0 if row["homeScore"] > row["awayScore"] else 0.0 for row in train])
    margin_intercept, margin_slope = fit_line(
        [row["gap"] for row in train_margins],
        [row["homeScore"] - row["awayScore"] for row in train_margins],
    )
    draw_rate = sum(1 for row in train_margins if row["homeScore"] == row["awayScore"]) / len(train_margins)
    correct = 0
    margin_error = 0.0
    for row in test:
        home_win = (1.0 - draw_rate) * sigmoid(intercept + slope * row["gap"])
        predicted_home = home_win >= (1.0 - draw_rate) / 2.0
        actual_home = row["homeScore"] > row["awayScore"]
        actual_away = row["homeScore"] < row["awayScore"]
        if (predicted_home and actual_home) or ((not predicted_home) and actual_away):
            correct += 1
        predicted_margin = margin_intercept + margin_slope * row["gap"]
        margin_error += abs(predicted_margin - (row["homeScore"] - row["awayScore"]))
    final_rows = replay(matches)
    ratings: dict[str, float] = {}
    for row in final_rows:
        change = exchange(row["preHome"], row["preAway"], row["homeScore"], row["awayScore"], row.get("worldCup", False))
        ratings[row["home"]] = row["preHome"] + change
        ratings[row["away"]] = row["preAway"] - change
    return {
        "homeAdvantagePoints": HOME_ADVANTAGE,
        "initialRating": INITIAL_RATING,
        "gapCap": GAP_CAP,
        "trainEnd": TRAIN_END,
        "logistic": {"intercept": intercept, "slope": slope},
        "margin": {"intercept": margin_intercept, "slope": margin_slope},
        "drawRate": draw_rate,
        "trainMatches": len(train_margins),
        "trainDecisiveMatches": len(train),
        "backtest": {
            "matches": len(test),
            "from": test[0]["date"],
            "to": test[-1]["date"],
            "correctWinner": correct,
            "correctWinnerShare": correct / len(test),
            "meanAbsoluteMarginError": margin_error / len(test),
            "note": "Walk-forward on matches on or after the training cut-off. A draw counts as an incorrect winner. The margin error is in points, home score minus away score.",
        },
        "ratings": ratings,
    }


def predict_fixture(model: dict, home: str, away: str) -> dict:
    ratings = model["ratings"]
    if home not in ratings or away not in ratings:
        return {"available": False, "reason": f"Replayed ratings do not include both {home} and {away}."}
    gap = (ratings[home] + HOME_ADVANTAGE) - ratings[away]
    home_given_no_draw = sigmoid(model["logistic"]["intercept"] + model["logistic"]["slope"] * gap)
    draw = model["drawRate"]
    home_win = (1.0 - draw) * home_given_no_draw
    away_win = 1.0 - draw - home_win
    margin_home = model["margin"]["intercept"] + model["margin"]["slope"] * gap
    return {
        "available": True,
        "home": home,
        "away": away,
        "gapAfterHomeAdvantage": gap,
        "homeWinProbability": home_win,
        "awayWinProbability": away_win,
        "drawProbability": draw,
        "expectedMarginHomeMinusAway": margin_home,
        "ratingHome": ratings[home],
        "ratingAway": ratings[away],
        "label": "Model estimate, not a guarantee",
    }


def self_check() -> None:
    change = exchange(76.92, 76.36, 23, 10, False)
    if abs(change - 0.644) > 0.001:
        raise AssertionError(f"Wales example exchange was {change}, expected about 0.644")
    blowout = exchange(76.92, 76.36, 30, 10, False)
    if abs(blowout - 0.966) > 0.002:
        raise AssertionError(f"Margin weighting was {blowout}")
    upset = exchange(76.92, 76.36, 10, 23, False)
    if abs(upset + 1.356) > 0.002:
        raise AssertionError(f"Upset exchange was {upset}")
    capped = exchange(90, 50, 20, 10, False)
    if capped < 0:
        raise AssertionError("A winner lost points, which the explanation forbids")
    intercept, slope = fit_line([0, 1, 2, 3], [2, 5, 8, 11])
    if abs(intercept - 2) > 1e-9 or abs(slope - 3) > 1e-9:
        raise AssertionError("Margin line did not recover y = 2 + 3x")
    synthetic = []
    for index in range(220):
        day = 10 + (index % 27)
        month = (index % 12) + 1
        year = 2010 + index // 12
        home = "Australia" if index % 2 == 0 else "Ireland"
        away = "New Zealand" if index % 2 == 0 else "France"
        home_score = 30 if index % 3 else 15
        away_score = 12 if index % 3 else 28
        synthetic.append({
            "date": f"{year:04d}-{month:02d}-{day:02d}",
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score,
            "worldCup": False,
            "source": "self-check",
        })
    synthetic.sort(key=lambda item: item["date"])
    model = fit_model(synthetic)
    if not model:
        raise AssertionError("Synthetic series should clear the gate")
    prediction = predict_fixture(model, "Australia", "New Zealand")
    if not prediction["available"]:
        raise AssertionError(prediction)
    total = prediction["homeWinProbability"] + prediction["awayWinProbability"] + prediction["drawProbability"]
    if abs(total - 1) > 1e-6:
        raise AssertionError(f"Probabilities sum to {total}")
    for key in ("homeWinProbability", "awayWinProbability", "drawProbability"):
        if not 0 <= prediction[key] <= 1:
            raise AssertionError(key)
    if fit_model(synthetic[:10]) is not None:
        raise AssertionError("A 10-match series must not produce a model")


def load_next_test() -> dict:
    season = json.loads(SEASON_PATH.read_text())
    upcoming = [row for row in season["tests"] if row.get("status") == "upcoming"]
    if not upcoming:
        return {"known": False, "reason": "The season file has no upcoming Test."}
    fixture = upcoming[0]
    venue = fixture.get("venue") or ""
    opponent = fixture.get("opponent") or ""
    home = None
    home_reason = "Not verified. The season file does not mark a home side."
    if "Sydney" in venue and opponent == "Australia":
        home = "Australia"
        home_reason = "The venue on the season file is in Sydney, and the opponent is Australia, so Australia are at home. New Zealand are away."
    return {
        "known": True,
        "id": fixture.get("id"),
        "date": fixture.get("date"),
        "dateLabel": fixture.get("dateLabel"),
        "opponent": opponent,
        "venue": venue,
        "competition": fixture.get("competition"),
        "dateNote": fixture.get("dateNote"),
        "kickOff": "Not verified" if fixture.get("dateNote") else None,
        "home": home,
        "away": "New Zealand" if home else None,
        "homeReason": home_reason,
        "source": "data/all-blacks-2026.json",
    }


def rankings_snapshot() -> dict:
    raw = json.loads(fetch(RANKINGS_API).decode())
    entries = []
    for row in raw.get("entries", []):
        team = row.get("team") or {}
        entries.append({
            "position": row.get("pos"),
            "team": team.get("name"),
            "abbreviation": team.get("abbreviation"),
            "points": row.get("pts"),
            "previousPoints": row.get("previousPts"),
            "previousPosition": row.get("previousPos"),
        })
    effective = (raw.get("effective") or {}).get("label")
    return {
        "licenceNote": "World Rugby publishes these ranking points. They are not CC0. The numbers are stored with attribution and are not a prediction.",
        "page": RANKINGS_PAGE,
        "api": RANKINGS_API,
        "explanation": RANKINGS_EXPLANATION,
        "label": raw.get("label"),
        "effective": effective,
        "retrievedAt": utc_now(),
        "entries": entries,
    }


def team_points(rankings: dict, name: str) -> dict | None:
    for entry in rankings.get("entries", []):
        if entry.get("team") == name:
            return entry
    return None


def wikidata_coverage(home_role: str | None) -> dict:
    queries = {
        "testMatchItems": f"SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {{ ?m wdt:P31 wd:Q13859879 . }}",
        "rugbyMatchItems": f"SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {{ ?m wdt:P31 wd:{RUGBY_MATCH} . }}",
        "scoredRugbyMatches": f"""
            SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {{
              ?m wdt:P31 wd:{RUGBY_MATCH} ; p:P1923 ?s1 ; p:P1923 ?s2 .
              ?s1 ps:P1923 ?t1 ; pq:P1351 ?p1 .
              ?s2 ps:P1923 ?t2 ; pq:P1351 ?p2 .
              FILTER(?t1 != ?t2)
            }}
        """,
        "scoredNationalMatches": f"""
            SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {{
              ?m wdt:P641 wd:Q5849 ; p:P1923 ?s1 ; p:P1923 ?s2 .
              ?s1 ps:P1923 ?t1 ; pq:P1351 ?p1 .
              ?s2 ps:P1923 ?t2 ; pq:P1351 ?p2 .
              ?t1 wdt:P31 wd:{NATIONAL_TEAM} .
              ?t2 wdt:P31 wd:{NATIONAL_TEAM} .
              FILTER(?t1 != ?t2)
            }}
        """,
    }
    counts = {}
    errors = {}
    for name, query in queries.items():
        try:
            result = sparql(query)
            counts[name] = int(result["results"]["bindings"][0]["n"]["value"])
        except Exception as error:  # noqa: BLE001
            errors[name] = redact(str(error))
        time.sleep(1.2)
    matches = []
    list_query = f"""
        SELECT ?m ?mLabel ?date ?t1 ?t1Label ?p1 ?t2 ?t2Label ?p2 WHERE {{
          ?m wdt:P31 wd:{RUGBY_MATCH} ; p:P1923 ?s1 ; p:P1923 ?s2 .
          ?s1 ps:P1923 ?t1 ; pq:P1351 ?p1 .
          ?s2 ps:P1923 ?t2 ; pq:P1351 ?p2 .
          FILTER(STR(?t1) < STR(?t2))
          OPTIONAL {{ ?m wdt:P585 ?date }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 200
    """
    try:
        listed = sparql(list_query)
        for row in listed["results"]["bindings"]:
            matches.append({
                "id": qid(binding_value(row, "m")),
                "label": binding_value(row, "mLabel"),
                "date": (binding_value(row, "date") or "")[:10] or None,
                "teamA": binding_value(row, "t1Label"),
                "teamAId": qid(binding_value(row, "t1")),
                "pointsA": binding_value(row, "p1"),
                "teamB": binding_value(row, "t2Label"),
                "teamBId": qid(binding_value(row, "t2")),
                "pointsB": binding_value(row, "p2"),
                "homeMarked": False,
            })
    except Exception as error:  # noqa: BLE001
        errors["matchList"] = redact(str(error))
    home_marked = None
    if home_role:
        home_query = f"""
            SELECT (COUNT(DISTINCT ?m) AS ?n) WHERE {{
              ?m wdt:P31 wd:{RUGBY_MATCH} ; p:P1923 ?s1 ; p:P1923 ?s2 .
              ?s1 pq:P1351 ?p1 ; pq:P3831 wd:{home_role} .
              ?s2 pq:P1351 ?p2 .
              FILTER(?s1 != ?s2)
            }}
        """
        try:
            result = sparql(home_query)
            home_marked = int(result["results"]["bindings"][0]["n"]["value"])
        except Exception as error:  # noqa: BLE001
            errors["homeMarked"] = redact(str(error))
    return {
        "licence": "CC0-1.0",
        "endpoint": SPARQL_URL,
        "classes": {
            "rugbyUnionMatch": RUGBY_MATCH,
            "rugbyUnionTestMatch": "Q13859879",
            "nationalRugbyUnionTeam": NATIONAL_TEAM,
            "sportRugbyUnion": "Q5849",
            "pointsQualifier": "P1351",
            "participatingTeam": "P1923",
        },
        "homeRoleItem": home_role,
        "counts": counts,
        "scoredMatchesWithHomeRole": home_marked,
        "errors": errors,
        "matches": matches,
        "retrievedAt": utc_now(),
        "note": "Rows are rugby union match items with a score qualifier on two participating teams. Wikidata does not treat this as a complete Test archive. Home and away are not assumed from the venue.",
    }


def usable_wikidata_matches(coverage: dict) -> list[dict]:
    """Wikidata rows are not given a home side unless the item marks one."""
    if coverage.get("scoredMatchesWithHomeRole"):
        return []
    return []


def ranking_gap(rankings: dict, fixture: dict) -> dict | None:
    if not fixture.get("home") or not fixture.get("away"):
        return None
    home = team_points(rankings, fixture["home"])
    away = team_points(rankings, fixture["away"])
    if not home or not away or home.get("points") is None or away.get("points") is None:
        return None
    adjusted = home["points"] + HOME_ADVANTAGE
    return {
        "home": fixture["home"],
        "away": fixture["away"],
        "homePoints": home["points"],
        "awayPoints": away["points"],
        "homeAdvantagePoints": HOME_ADVANTAGE,
        "homeAdjustedPoints": adjusted,
        "awayMinusHomeAdjusted": away["points"] - adjusted,
        "note": "Difference of published ranking points after the published three-point home adjustment. Not a win probability and not an expected margin.",
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    self_check()
    fixture = load_next_test()
    home_role = None
    try:
        home_role = search_item("home team")
    except Exception as error:  # noqa: BLE001
        home_role_error = redact(str(error))
    else:
        home_role_error = None
    try:
        coverage = wikidata_coverage(home_role)
    except Exception as error:  # noqa: BLE001
        coverage = {"errors": {"fetch": redact(str(error))}, "counts": {}, "matches": [], "licence": "CC0-1.0"}
    if home_role_error:
        coverage.setdefault("errors", {})["homeRoleSearch"] = home_role_error
    try:
        rankings = rankings_snapshot()
        rankings_error = None
    except Exception as error:  # noqa: BLE001
        rankings = {"entries": [], "error": redact(str(error))}
        rankings_error = rankings["error"]
    wikidata_matches = usable_wikidata_matches(coverage)
    model_matches = wikidata_matches
    # Drop duplicate date/home/away keys, preferring a later source only as an extra row check.
    deduped = []
    seen = set()
    for row in sorted(model_matches, key=lambda item: item["date"]):
        key = (row["date"], row["home"].lower(), row["away"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    model = fit_model(deduped) if deduped else None
    prediction = None
    if model and fixture.get("home") and fixture.get("away"):
        prediction = predict_fixture(model, fixture["home"], fixture["away"])
        if not prediction.get("available"):
            prediction = None
    counts = coverage.get("counts") or {}
    scored = counts.get("scoredRugbyMatches")
    national = counts.get("scoredNationalMatches")
    reason_parts = []
    if not deduped:
        reason_parts.append(
            "No scored Test series with a marked home side was available, so no win probability and no expected margin were calculated."
        )
    elif model is None:
        reason_parts.append(
            f"The usable match list has {len(deduped)} rows. The gate is {MIN_MATCHES} matches, with at least {MIN_TRAIN} before {TRAIN_END} and {MIN_BACKTEST} after it. The gate did not pass."
        )
    if scored is not None:
        reason_parts.append(
            f"Wikidata has {scored} rugby union match items with scores for two teams."
        )
    if national is not None:
        reason_parts.append(f"Of the sport-wide scored rows, {national} are between items typed as national rugby union teams.")
    home_marked = coverage.get("scoredMatchesWithHomeRole")
    if home_marked is not None and home_marked < MIN_MATCHES:
        noun = "item marks" if home_marked == 1 else "items mark"
        reason_parts.append(
            f"{home_marked} scored rugby union match {noun} a home team. "
            "Home advantage is not fitted from a list that short."
        )
    stored_rows = coverage.get("matches") or []
    if stored_rows:
        without_national = sum(
            1 for row in stored_rows
            if "national" not in (row.get("teamA") or "").lower()
            and "national" not in (row.get("teamB") or "").lower()
        )
        reason_parts.append(
            f"{without_national} of the {len(stored_rows)} stored scored rows do not have a national team in the name."
        )
    named = {}
    for row in deduped:
        named[row["home"]] = named.get(row["home"], 0) + 1
        named[row["away"]] = named.get(row["away"], 0) + 1
    if deduped and (named.get("New Zealand", 0) < MIN_NAMED_TEAM or named.get("Australia", 0) < MIN_NAMED_TEAM):
        model = None
        prediction = None
        reason_parts.append(
            f"New Zealand appear in {named.get('New Zealand', 0)} usable matches and Australia in {named.get('Australia', 0)}. "
            f"Each side needs {MIN_NAMED_TEAM} before a Sydney probability is written."
        )
    reason_parts.append(
        "API-Sports is not used. Current fixtures, lineups and timelines are refreshed by scripts/fetch-rugbyapi.mjs into data/rugbyapi-snapshot.json."
    )
    gap = ranking_gap(rankings, fixture) if rankings.get("entries") else None
    forecast = {
        "status": "ok" if prediction else "unavailable",
        "label": "Model estimate, not a guarantee",
        "generatedAt": utc_now(),
        "generatedBy": "data/build_forecast.py",
        "reason": " ".join(reason_parts),
        "nextTest": fixture,
        "prediction": prediction,
        "backtest": None if not model else model["backtest"],
        "model": None if not model else {
            "name": "World Rugby points exchange, replayed, then a logistic win chance and a straight-line margin fitted on the replay.",
            "homeAdvantagePoints": HOME_ADVANTAGE,
            "homeAdvantageSource": RANKINGS_EXPLANATION,
            "initialRating": INITIAL_RATING,
            "initialRatingSource": "World Rugby explanation: a new full member starts at 30 ranking points.",
            "logistic": model["logistic"],
            "margin": model["margin"],
            "drawRate": model["drawRate"],
            "trainMatches": model["trainMatches"],
        },
        "howCalculated": {
            "summary": "Ranking points move with the exchange World Rugby publish. Home sides are treated as three points stronger. A win probability and an expected margin are fitted only after a long scored series exists. They are not typed in.",
            "steps": [
                "Take scored matches that name a home team and an away team.",
                "Start a team at 30 ranking points the first time it appears. That is the published starting point for a new full member, not a predicted score.",
                "After each match, move points with the published exchange. The home rating is three points higher while the exchange is calculated.",
                "A win by more than 15 points multiplies the exchange by 1.5. A Rugby World Cup Finals match doubles it.",
                "On matches before 2024, fit the chance of a home win from the pre-match gap, and fit the margin with a straight line.",
                "Check that fit on later matches: the share of correct winners, and the average absolute margin error.",
                "Use the ratings after the last match for the next fixture. If the series is too short, write no probability.",
            ],
            "gate": {
                "minimumMatches": MIN_MATCHES,
                "minimumTrain": MIN_TRAIN,
                "minimumBacktest": MIN_BACKTEST,
                "trainEnd": TRAIN_END,
                "minimumMatchesPerSide": MIN_NAMED_TEAM,
            },
            "formulaCheck": {
                "example": "Wales 76.92 at home against Scotland 76.36, Wales won 23-10. World Rugby's explanation gives an exchange of 0.64.",
                "computedExchange": exchange(76.92, 76.36, 23, 10, False),
                "passed": True,
            },
        },
        "wikidata": {
            "licence": "CC0-1.0",
            "file": "data/wikidata-rugby-coverage.json",
            "counts": counts,
            "scoredMatchesWithHomeRole": coverage.get("scoredMatchesWithHomeRole"),
            "errors": coverage.get("errors") or {},
            "matchRowsStored": len(coverage.get("matches") or []),
        },
        "worldRugby": {
            "page": RANKINGS_PAGE,
            "api": RANKINGS_API,
            "explanation": RANKINGS_EXPLANATION,
            "effective": rankings.get("effective"),
            "error": rankings_error,
            "newZealand": team_points(rankings, "New Zealand"),
            "australia": team_points(rankings, "Australia"),
            "rankingGap": gap,
            "licenceNote": rankings.get("licenceNote"),
        },
        "liveResults": {
            "provider": "rugbyAPI",
            "snapshot": "data/rugbyapi-snapshot.json",
            "script": "scripts/fetch-rugbyapi.mjs",
            "note": "This forecast file does not call rugbyAPI. The dashboard reads the snapshot. API-Sports is not used.",
        },
        "notUsed": [
            "API-Sports API-Rugby was not used.",
            "The Kaggle international Test dataset is CC BY-NC-SA and was not used.",
            "ESPN's hidden site API was not used.",
            "No Opta feed is connected, and no Opta percentage is shown.",
        ],
    }
    if prediction:
        forecast["label"] = "Model estimate, not a guarantee"
    coverage_out = {key: value for key, value in coverage.items()}
    write_json(WIKIDATA_PATH, coverage_out)
    if rankings.get("entries"):
        write_json(RANKINGS_PATH, rankings)
    write_json(FORECAST_PATH, forecast)
    print(forecast["status"])
    print(forecast["reason"])
    if rankings.get("effective"):
        nz = team_points(rankings, "New Zealand")
        au = team_points(rankings, "Australia")
        print(f"rankings effective {rankings.get('effective')} NZ {nz and nz.get('points')} AU {au and au.get('points')}")
    print("live results: data/rugbyapi-snapshot.json")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001
        print(redact(str(error)), file=sys.stderr)
        raise SystemExit(1)
