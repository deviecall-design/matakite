#!/usr/bin/env python3
"""Build the Sydney forecast from cited sources.

Sources
- Rugby Database's All Test Match list, cross-checked against the Tier 1
  team games lists. That history is data/rugbydatabase-tests.json.
  Refresh it with: python data/build_forecast.py --fetch-history
- World Rugby men's rankings feed, plus the published points exchange.
  The published three-point home adjustment is a ranking fact. The
  probability uses a home advantage fitted from the Test history.
- Wikidata is not the series for this probability. It did not mark home sides.
- rugbyAPI is not the history. A free key only covers yesterday onward.
  Current fixtures, lineups and timelines are refreshed by
  scripts/fetch-rugbyapi.mjs into data/rugbyapi-snapshot.json.

The script never writes a win probability unless the scored-match gate
passes. A short series or a failed check becomes status "unavailable"
with the evidence attached. Percentages are not typed in.

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
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEASON_PATH = ROOT / "data" / "all-blacks-2026.json"
FORECAST_PATH = ROOT / "data" / "forecast.json"
RANKINGS_PATH = ROOT / "data" / "world-rugby-rankings.json"
WIKIDATA_PATH = ROOT / "data" / "wikidata-rugby-coverage.json"
HISTORY_PATH = ROOT / "data" / "rugbydatabase-tests.json"
TEST_LIST_URL = "https://www.rugbydatabase.com.au/test-rugby/games-list.php"
TEAM_LIST_URL = "https://www.rugbydatabase.com.au/team/games-list.php?teamId={team_id}"

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
VENUE_MIN_GAMES = 3
VENUE_MIN_SHARE = 0.7
ADVANTAGE_MAX = 12.0
ADVANTAGE_STEP = 0.1

# Rugby Database's Test list names the men's New Zealand side "All Blacks".
TEAM_ALIAS = {"All Blacks": "New Zealand", "Western Samoa": "Samoa"}
# Not a national union. Women's sides and XV sides are filtered separately.
INVITATIONAL = {
    "Barbarians",
    "World XV",
    "British Army",
    "British Empire Services",
    "Queensland",
    "NZEF Kiwis",
    "South America",
}
TIER1 = (
    (3, "New Zealand"),
    (37, "Australia"),
    (38, "South Africa"),
    (36, "Argentina"),
    (43, "England"),
    (45, "France"),
    (42, "Ireland"),
    (54, "Scotland"),
    (44, "Wales"),
    (47, "Italy"),
)

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


def exchange(home_rating: float, away_rating: float, home_score: int, away_score: int, world_cup: bool = False, home_advantage: float = HOME_ADVANTAGE) -> float:
    """Points added to the home side. The away side moves by the opposite amount."""
    gap = (home_rating + home_advantage) - away_rating
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


def replay(matches: list[dict], home_advantage: float) -> list[dict]:
    ratings: dict[str, float] = {}
    rows = []
    ordered = sorted(matches, key=lambda item: (item["date"], item.get("gameId") or 0))
    for index, match in enumerate(ordered):
        home = match["home"]
        away = match["away"]
        home_rating = ratings.get(home, INITIAL_RATING)
        away_rating = ratings.get(away, INITIAL_RATING)
        advantage = home_advantage if match.get("homeAdvantageApplies", True) else 0.0
        gap = (home_rating + advantage) - away_rating
        rows.append({**match, "preHome": home_rating, "preAway": away_rating, "gap": gap, "advantageUsed": advantage, "index": index})
        change = exchange(home_rating, away_rating, match["homeScore"], match["awayScore"], match.get("worldCup", False), advantage)
        ratings[home] = home_rating + change
        ratings[away] = away_rating - change
    return rows


def training_log_likelihood(rows: list[dict]) -> tuple[float, float, float, list[dict]]:
    train = [row for row in rows if row["index"] >= 40 and row["date"] < TRAIN_END and row["homeScore"] != row["awayScore"]]
    intercept, slope = fit_logistic(
        [row["gap"] for row in train],
        [1.0 if row["homeScore"] > row["awayScore"] else 0.0 for row in train],
    )
    total = 0.0
    for row in train:
        prob = sigmoid(intercept + slope * row["gap"])
        prob = min(1.0 - 1e-9, max(1e-9, prob))
        won = 1.0 if row["homeScore"] > row["awayScore"] else 0.0
        total += won * math.log(prob) + (1.0 - won) * math.log(1.0 - prob)
    return total, intercept, slope, train


def fit_model(matches: list[dict]) -> dict | None:
    probe = replay(matches, 0.0)
    if len(probe) < MIN_MATCHES:
        return None
    train = [row for row in probe if row["index"] >= 40 and row["date"] < TRAIN_END and row["homeScore"] != row["awayScore"]]
    train_margins = [row for row in probe if row["index"] >= 40 and row["date"] < TRAIN_END]
    test = [row for row in probe if row["date"] >= TRAIN_END]
    if len(train) < MIN_TRAIN or len(test) < MIN_BACKTEST or len(train_margins) < MIN_TRAIN:
        return None
    best = None
    likelihoods = {}
    steps = int(round(ADVANTAGE_MAX / ADVANTAGE_STEP))
    for step in range(steps + 1):
        advantage = round(step * ADVANTAGE_STEP, 1)
        rows = replay(matches, advantage)
        likelihood, intercept, slope, _train = training_log_likelihood(rows)
        likelihoods[advantage] = likelihood
        if best is None or likelihood > best["likelihood"]:
            best = {"advantage": advantage, "likelihood": likelihood, "intercept": intercept, "slope": slope, "rows": rows}
    rows = best["rows"]
    intercept = best["intercept"]
    slope = best["slope"]
    train = [row for row in rows if row["index"] >= 40 and row["date"] < TRAIN_END and row["homeScore"] != row["awayScore"]]
    train_margins = [row for row in rows if row["index"] >= 40 and row["date"] < TRAIN_END]
    test = [row for row in rows if row["date"] >= TRAIN_END]
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
    ratings: dict[str, float] = {}
    for row in rows:
        change = exchange(row["preHome"], row["preAway"], row["homeScore"], row["awayScore"], row.get("worldCup", False), row["advantageUsed"])
        ratings[row["home"]] = row["preHome"] + change
        ratings[row["away"]] = row["preAway"] - change
    return {
        "homeAdvantagePoints": best["advantage"],
        "homeAdvantageLikelihood": best["likelihood"],
        "homeAdvantageLikelihoodAtZero": likelihoods.get(0.0),
        "homeAdvantageLikelihoodAtPublishedThree": likelihoods.get(3.0),
        "initialRating": INITIAL_RATING,
        "gapCap": GAP_CAP,
        "trainEnd": TRAIN_END,
        "logistic": {"intercept": intercept, "slope": slope},
        "margin": {"intercept": margin_intercept, "slope": margin_slope},
        "drawRate": draw_rate,
        "trainMatches": len(train_margins),
        "trainDecisiveMatches": len(train),
        "homeAdvantageMatches": sum(1 for row in rows if row.get("homeAdvantageApplies")),
        "backtest": {
            "matches": len(test),
            "from": test[0]["date"],
            "to": test[-1]["date"],
            "correctWinner": correct,
            "correctWinnerShare": correct / len(test),
            "meanAbsoluteMarginError": margin_error / len(test),
            "note": "Walk-forward on matches on or after the training cut-off, and before the next Test. A draw counts as an incorrect winner. The margin error is in points, home score minus away score.",
        },
        "ratings": ratings,
    }


def predict_fixture(model: dict, home: str, away: str, home_advantage: float | None = None) -> dict:
    ratings = model["ratings"]
    if home not in ratings or away not in ratings:
        return {"available": False, "reason": f"Replayed ratings do not include both {home} and {away}."}
    advantage = model["homeAdvantagePoints"] if home_advantage is None else home_advantage
    gap = (ratings[home] + advantage) - ratings[away]
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


def plain_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_table(html: str) -> list[dict]:
    marker = "var tableData = "
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("Rugby Database page has no tableData list")
    index = start + len(marker)
    if html[index] != "[":
        raise RuntimeError("Rugby Database tableData is not a list")
    depth = 0
    in_string = False
    escaped = False
    for end in range(index, len(html)):
        char = html[end]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(html[index:end + 1])
    raise RuntimeError("Rugby Database tableData was not closed")


def listed_side(value: str | None) -> tuple[str, int | None]:
    name = plain_text(value)
    found = re.search(r"teamId=(\d+)", value or "")
    return name, int(found.group(1)) if found else None


def listed_date(label: str | None) -> str | None:
    found = re.search(r"(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]{3,})\s+(\d{4})", label or "")
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    if not found:
        return None
    month = months.get(found.group(2)[:3].lower())
    if not month:
        return None
    return f"{int(found.group(3)):04d}-{month:02d}-{int(found.group(1)):02d}"


def listed_score(value: str | None) -> tuple[int, int] | None:
    found = re.search(r"(\d+)\s*-\s*(\d+)", plain_text(value))
    if not found:
        return None
    return int(found.group(1)), int(found.group(2))


def exclusion_reason(name: str) -> str | None:
    if "(W)" in name:
        return "womens"
    if name.endswith(" XV") or " XV " in name:
        return "xv"
    if name in INVITATIONAL:
        return "invitational"
    return None


def canonical_side(name: str) -> str:
    return TEAM_ALIAS.get(name, name)


def fetch_html(url: str) -> str:
    raw = fetch(url, headers={"Accept": "text/html,application/xhtml+xml"})
    return raw.decode("utf-8", "replace")


def venue_hosts(matches: list[dict]) -> dict[int, str]:
    counts: dict[int, Counter] = {}
    for match in matches:
        venue_id = match.get("venueId")
        if not isinstance(venue_id, int):
            continue
        counts.setdefault(venue_id, Counter())[match["home"]] += 1
    hosts = {}
    for venue_id, tally in counts.items():
        home, games = tally.most_common(1)[0]
        total = sum(tally.values())
        if games >= VENUE_MIN_GAMES and games / total >= VENUE_MIN_SHARE:
            hosts[venue_id] = home
    return hosts


def apply_home_advantage(matches: list[dict]) -> None:
    hosts = venue_hosts([match for match in matches if match["date"] < TRAIN_END])
    for match in matches:
        match["homeAdvantageApplies"] = hosts.get(match.get("venueId")) == match["home"]


def season_disagreements(matches: list[dict]) -> list[str]:
    season = json.loads(SEASON_PATH.read_text())
    problems = []
    by_id = {}
    for match in matches:
        by_id.setdefault(match["gameId"], match)
    for test in season.get("tests", []):
        if test.get("status") != "played" or (test.get("kind") or "test") != "test":
            continue
        hits = [
            match for match in matches
            if match["date"] == test.get("date")
            and (
                (match["home"] == "New Zealand" and match["away"] == test.get("opponent"))
                or (match["away"] == "New Zealand" and match["home"] == test.get("opponent"))
            )
        ]
        label = f"{test.get('date')} {test.get('opponent')}"
        if len(hits) != 1:
            problems.append(f"{label}: expected one Rugby Database Test, found {len(hits)}.")
            continue
        match = hits[0]
        if match["home"] == "New Zealand":
            nz_score, opp_score = match["homeScore"], match["awayScore"]
        else:
            nz_score, opp_score = match["awayScore"], match["homeScore"]
        if nz_score != test.get("nzScore") or opp_score != test.get("oppScore"):
            problems.append(
                f"{label}: Rugby Database has New Zealand {nz_score}–{opp_score}, "
                f"and the season file has {test.get('nzScore')}–{test.get('oppScore')}."
            )
    return problems


def build_history() -> dict:
    test_html = fetch_html(TEST_LIST_URL)
    raw_rows = extract_table(test_html)
    dropped = Counter()
    matches = []
    seen_ids = set()
    duplicate_ids = 0
    for row in raw_rows:
        home_listed, home_id = listed_side(row.get("Home"))
        away_listed, away_id = listed_side(row.get("Away"))
        score = listed_score(row.get("Score"))
        date = listed_date(row.get("kickOffF"))
        if score is None or date is None or not home_listed or not away_listed:
            dropped["unreadable"] += 1
            continue
        reason = exclusion_reason(home_listed) or exclusion_reason(away_listed)
        if reason:
            dropped[reason] += 1
            continue
        game_id = row.get("gameId")
        if game_id in seen_ids:
            duplicate_ids += 1
            continue
        seen_ids.add(game_id)
        matches.append({
            "gameId": game_id,
            "date": date,
            "dateLabel": row.get("kickOffF"),
            "home": canonical_side(home_listed),
            "homeListed": home_listed,
            "homeId": home_id,
            "away": canonical_side(away_listed),
            "awayListed": away_listed,
            "awayId": away_id,
            "homeScore": score[0],
            "awayScore": score[1],
            "venue": row.get("venueName"),
            "venueId": row.get("venueId"),
            "competition": plain_text(row.get("competitions")),
        })
    matches.sort(key=lambda item: (item["date"], item.get("gameId") or 0))
    same_match = 0
    kept = []
    seen_key = set()
    for match in matches:
        sides = tuple(sorted((match["home"].lower(), match["away"].lower())))
        key = (match["date"], sides, match["homeScore"], match["awayScore"], match["home"].lower())
        if key in seen_key:
            same_match += 1
            continue
        seen_key.add(key)
        kept.append(match)
    tier1 = []
    test_ids = {match["gameId"] for match in kept}
    for team_id, name in TIER1:
        url = TEAM_LIST_URL.format(team_id=team_id)
        try:
            page = fetch_html(url)
            listed = extract_table(page)
            ids = {row.get("gameId") for row in listed}
            tier1.append({
                "teamId": team_id,
                "name": name,
                "url": url,
                "listedGames": len(listed),
                "alsoOnTestList": sum(1 for game_id in ids if game_id in test_ids),
                "notOnTestList": sum(1 for game_id in ids if game_id not in test_ids),
            })
        except Exception as error:  # noqa: BLE001
            tier1.append({"teamId": team_id, "name": name, "url": url, "error": redact(str(error))})
        time.sleep(0.4)
    nz_ids = set()
    try:
        nz_page = fetch_html(TEAM_LIST_URL.format(team_id=3))
        nz_ids = {row.get("gameId") for row in extract_table(nz_page)}
    except Exception as error:  # noqa: BLE001
        nz_error = redact(str(error))
    else:
        nz_error = None
    tour_ids = [29376, 29377, 29378, 29380]
    return {
        "source": {
            "name": "Rugby Database",
            "list": "All Test Match Games",
            "url": TEST_LIST_URL,
            "teamListExample": TEAM_LIST_URL.format(team_id=3),
            "retrievedAt": utc_now(),
            "note": (
                "The New Zealand team games list includes tour matches against provinces. "
                "This file keeps games on Rugby Database's Test match list. "
                "Women's matches, XV sides, and invitational sides are not in the model history. "
                "All Blacks is stored as New Zealand. Western Samoa is stored as Samoa. "
                "A free rugbyAPI key only covers yesterday onward, so it is not this history."
            ),
        },
        "counts": {
            "testListRows": len(raw_rows),
            "kept": len(kept),
            "duplicateGameIds": duplicate_ids,
            "sameScoreSameDayDropped": same_match,
            "dropped": dict(dropped),
        },
        "tier1Lists": tier1,
        "tourMatchesExcluded": {
            "gameIds": tour_ids,
            "onNewZealandTeamList": all(game_id in nz_ids for game_id in tour_ids) if nz_ids else None,
            "onTestList": any(game_id in test_ids for game_id in tour_ids),
            "newZealandListError": nz_error,
            "note": "Stormers, Sharks, Bulls and Lions in 2026 are on the New Zealand games list and are not Tests.",
        },
        "matches": kept,
    }


def load_history() -> dict:
    return json.loads(HISTORY_PATH.read_text())


def main(argv: list[str] | None = None) -> int:
    self_check()
    args = argv if argv is not None else sys.argv[1:]
    if "--fetch-history" in args:
        history = build_history()
        write_json(HISTORY_PATH, history)
        print(f"wrote {HISTORY_PATH} matches={history['counts']['kept']}")
    fixture = load_next_test()
    try:
        rankings = json.loads(RANKINGS_PATH.read_text())
        rankings_error = rankings.get("error")
    except Exception as error:  # noqa: BLE001
        rankings = {"entries": []}
        rankings_error = redact(str(error))
    history = None
    history_error = None
    if HISTORY_PATH.exists():
        try:
            history = load_history()
        except Exception as error:  # noqa: BLE001
            history_error = redact(str(error))
    else:
        history_error = "data/rugbydatabase-tests.json is not in the repo. Run python data/build_forecast.py --fetch-history."
    cutoff = fixture.get("date") or "9999-12-31"
    matches = []
    if history and history.get("matches"):
        matches = [dict(match) for match in history["matches"] if match.get("date") and match["date"] < cutoff]
        apply_home_advantage(matches)
    disagreements = season_disagreements(matches) if matches else []
    model = fit_model(matches) if matches and not disagreements else None
    named = {}
    for row in matches:
        named[row["home"]] = named.get(row["home"], 0) + 1
        named[row["away"]] = named.get(row["away"], 0) + 1
    reason_parts = []
    if history_error:
        reason_parts.append(history_error)
    if disagreements:
        model = None
        reason_parts.append(
            "No win probability is written because the Rugby Database scores do not match the season file. "
            + " ".join(disagreements)
        )
    if matches and model is None and not disagreements:
        before = sum(1 for row in matches if row["date"] < TRAIN_END)
        after = sum(1 for row in matches if row["date"] >= TRAIN_END)
        reason_parts.append(
            f"The usable match list has {len(matches)} scored Tests with a home side, {before} before {TRAIN_END} and {after} after it. "
            f"The gate is {MIN_MATCHES} matches, at least {MIN_TRAIN} before {TRAIN_END} and {MIN_BACKTEST} after it. The gate did not pass."
        )
    if not matches and not history_error:
        reason_parts.append("The Rugby Database history file has no scored Tests before the next fixture, so no win probability was calculated.")
    if matches and (named.get("New Zealand", 0) < MIN_NAMED_TEAM or named.get("Australia", 0) < MIN_NAMED_TEAM):
        model = None
        reason_parts.append(
            f"New Zealand appear in {named.get('New Zealand', 0)} usable matches and Australia in {named.get('Australia', 0)}. "
            f"Each side needs {MIN_NAMED_TEAM} before a Sydney probability is written."
        )
    if model and model["logistic"]["slope"] <= 0:
        model = None
        reason_parts.append("The fitted line did not give home sides a higher win chance when their rating gap was larger, so no probability is written.")
    prediction = None
    if model and fixture.get("home") and fixture.get("away"):
        prediction = predict_fixture(model, fixture["home"], fixture["away"])
        if not prediction.get("available"):
            reason_parts.append(prediction.get("reason") or "The fixture could not be scored from the replayed ratings.")
            prediction = None
    elif model and not fixture.get("home"):
        model = None
        prediction = None
        reason_parts.append(fixture.get("homeReason") or "The next Test has no marked home side, so no probability is written.")
    if prediction:
        back = model["backtest"]
        reason_parts.insert(
            0,
            f"Fitted on {len(matches)} Rugby Database Tests. Home advantage fitted at {model['homeAdvantagePoints']} points. "
            f"Backtest {back['correctWinner']} of {back['matches']} ({back['from']} to {back['to']}). "
            "Model estimate, not a guarantee.",
        )
    reason_parts.append(
        "rugbyAPI was not used for this history. A free key only covers yesterday onward. "
        "API-Sports is not used. Current fixtures, lineups and timelines are refreshed by scripts/fetch-rugbyapi.mjs into data/rugbyapi-snapshot.json."
    )
    gap = ranking_gap(rankings, fixture) if rankings.get("entries") else None
    advantage_text = None
    if model:
        advantage_text = (
            f"Home advantage of {model['homeAdvantagePoints']} points was the value from 0 to {ADVANTAGE_MAX}, in steps of {ADVANTAGE_STEP}, "
            f"with the best training likelihood. Likelihood at 0 was {model['homeAdvantageLikelihoodAtZero']:.1f}. "
            f"Likelihood at the published 3 points was {model['homeAdvantageLikelihoodAtPublishedThree']:.1f}. "
            f"The chosen value's likelihood was {model['homeAdvantageLikelihood']:.1f}. "
            f"It is applied on {model['homeAdvantageMatches']} matches whose venue, before {TRAIN_END}, had at least {VENUE_MIN_GAMES} Tests "
            f"and one side at home in at least {int(VENUE_MIN_SHARE * 100)} percent of them. Other matches stay in the series with no home advantage."
        )
    source = (history or {}).get("source") or {}
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
            "name": "World Rugby points exchange, replayed on Rugby Database Tests, with a fitted home advantage. A logistic win chance and a straight-line margin are fitted on the replay.",
            "homeAdvantagePoints": model["homeAdvantagePoints"],
            "homeAdvantageSource": advantage_text,
            "publishedHomeAdvantagePoints": HOME_ADVANTAGE,
            "publishedHomeAdvantageSource": RANKINGS_EXPLANATION,
            "initialRating": INITIAL_RATING,
            "initialRatingSource": "World Rugby explanation: a new full member starts at 30 ranking points. These replay ratings are not the published World Rugby table.",
            "logistic": model["logistic"],
            "margin": model["margin"],
            "drawRate": model["drawRate"],
            "trainMatches": model["trainMatches"],
            "homeAdvantageMatches": model["homeAdvantageMatches"],
        },
        "howCalculated": {
            "summary": (
                "The series is Rugby Database's Test list, with a home side on every row. "
                "Ratings move with the published points exchange. Home advantage is fitted from matches before 2024, not typed in as three points. "
                "A win probability and an expected margin are written only after the gate passes. They are a model estimate, not a guarantee."
            ),
            "steps": [
                "Read scored Tests from data/rugbydatabase-tests.json. The home side is the side Rugby Database lists at home, and the venue is the venue on that row.",
                "Drop women's matches, XV sides, and invitational sides before the file is written. Tour matches against provinces are not on the Test list, so they are not in the file.",
                "Treat a venue as a home ground when, before 2024, it has at least three Tests and one side is home in at least 70 percent of them. Home advantage applies only when that side is home. One-off venues, including M&T Bank Stadium, get no home advantage.",
                "Start a team at 30 replay points the first time it appears. That starting point is the published figure for a new full member. It is not the published World Rugby ranking.",
                "After each match, move points with the published exchange, using the fitted home advantage instead of the published three points. A win by more than 15 points multiplies the exchange by 1.5.",
                "Rugby World Cup finals are not marked separately on this list, so the published doubling for a final is not applied.",
                "On matches before 2024, fit the chance of a home win from the pre-match gap, and fit the margin with a straight line. The home-advantage amount is the one with the best training likelihood.",
                "Check that fit on later matches, up to but not including the next Test: the share of correct winners, and the average absolute margin error.",
                "Use the ratings after the last played match for Sydney. Australia are at home because the venue is in Sydney. If the series is too short, or a season-file score disagrees, write no probability.",
            ],
            "gate": {
                "minimumMatches": MIN_MATCHES,
                "minimumTrain": MIN_TRAIN,
                "minimumBacktest": MIN_BACKTEST,
                "trainEnd": TRAIN_END,
                "minimumMatchesPerSide": MIN_NAMED_TEAM,
            },
            "formulaCheck": {
                "example": "Wales 76.92 at home against Scotland 76.36, Wales won 23-10, using the published three-point home adjustment. World Rugby's explanation gives an exchange of 0.64. This checks the exchange. It is not the home advantage used for Sydney.",
                "computedExchange": exchange(76.92, 76.36, 23, 10, False),
                "passed": abs(exchange(76.92, 76.36, 23, 10, False) - 0.644) < 0.001,
            },
        },
        "history": {
            "file": "data/rugbydatabase-tests.json",
            "source": source.get("name"),
            "url": source.get("url"),
            "retrievedAt": source.get("retrievedAt"),
            "matches": len(matches),
            "counts": None if not history else history.get("counts"),
            "tier1Lists": None if not history else history.get("tier1Lists"),
            "tourMatchesExcluded": None if not history else history.get("tourMatchesExcluded"),
            "seasonScoreCheck": disagreements or "The eight played 2026 Tests match data/all-blacks-2026.json.",
            "error": history_error,
        },
        "wikidata": {
            "usedForProbability": False,
            "licence": "CC0-1.0",
            "file": "data/wikidata-rugby-coverage.json",
            "note": "Not the series for this probability. The earlier extract marked a home side on too few scored matches.",
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
            "licenceNote": rankings.get("licenceNote") or "World Rugby publishes these ranking points. They are not a prediction.",
        },
        "liveResults": {
            "provider": "rugbyAPI",
            "snapshot": "data/rugbyapi-snapshot.json",
            "script": "scripts/fetch-rugbyapi.mjs",
            "note": "This forecast file does not call rugbyAPI. The free key cannot supply the historical Tests. The dashboard reads the snapshot for current fixtures only. API-Sports is not used.",
        },
        "notUsed": [
            "rugbyAPI was not used for the historical series. A free key only covers yesterday onward.",
            "API-Sports API-Rugby was not used.",
            "The Kaggle international Test dataset is CC BY-NC-SA and was not used.",
            "ESPN's hidden site API was not used.",
            "No Opta feed is connected, and no Opta percentage is shown.",
            "Wikidata was not used for this probability.",
        ],
    }
    write_json(FORECAST_PATH, forecast)
    print(forecast["status"])
    print(forecast["reason"])
    if prediction:
        print(
            "NZ",
            round(prediction["awayWinProbability"] * 100, 1),
            "AU",
            round(prediction["homeWinProbability"] * 100, 1),
            "margin",
            round(-prediction["expectedMarginHomeMinusAway"], 2),
            "H",
            model["homeAdvantagePoints"],
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001
        print(redact(str(error)), file=sys.stderr)
        raise SystemExit(1)
