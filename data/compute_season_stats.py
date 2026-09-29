#!/usr/bin/env python3
"""Add up the 2026 All Blacks Test record from data/all-blacks-2026.json.

Rules, also used by matakite-poc.html:
  try = 5, conversion = 2, penalty goal = 3
  a penalty try = 7, counts as a try, and is not credited to a player

Final scores on each Test are the source for points for and against.
Scorer lists must add up to those final scores or this script stops.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "all-blacks-2026.json"

TRY = 5
CONVERSION = 2
PENALTY_GOAL = 3
PENALTY_TRY = 7


def side_points(tries: list, kickers: list) -> tuple[int, int]:
    points = 0
    try_count = 0
    for item in tries:
        count = int(item["count"])
        try_count += count
        points += (PENALTY_TRY if item.get("penaltyTry") else TRY) * count
    for kicker in kickers:
        points += int(kicker.get("conversions") or 0) * CONVERSION
        points += int(kicker.get("penalties") or 0) * PENALTY_GOAL
    return points, try_count


def player_points(tests: list) -> dict[str, dict]:
    players: dict[str, dict] = {}

    def bucket(name: str) -> dict:
        row = players.get(name)
        if row is None:
            row = {"player": name, "tries": 0, "conversions": 0, "penalties": 0, "points": 0}
            players[name] = row
        return row

    for test in tests:
        if test.get("status") != "played":
            continue
        for item in test.get("nzTries") or []:
            if item.get("penaltyTry"):
                continue
            row = bucket(item["player"])
            row["tries"] += int(item["count"])
            row["points"] += TRY * int(item["count"])
        for kicker in test.get("nzKickers") or []:
            row = bucket(kicker["player"])
            cons = int(kicker.get("conversions") or 0)
            pens = int(kicker.get("penalties") or 0)
            row["conversions"] += cons
            row["penalties"] += pens
            row["points"] += cons * CONVERSION + pens * PENALTY_GOAL
    return players


def result_letter(nz: int, opp: int) -> str:
    if nz > opp:
        return "W"
    if nz < opp:
        return "L"
    return "D"


def is_test(item: dict) -> bool:
    return item.get("kind", "test") == "test"


def compute(data: dict) -> dict:
    upcoming = [t for t in data["tests"] if t.get("status") == "upcoming"]
    won = lost = drawn = 0
    points_for = points_against = 0
    tries_for = tries_against = 0
    results = []
    all_won = all_lost = all_drawn = 0
    all_for = all_against = 0
    test_count = 0
    played_count = 0

    for test in data["tests"]:
        if test.get("status") != "played":
            continue
        played_count += 1
        nz = int(test["nzScore"])
        opp = int(test["oppScore"])
        letter = result_letter(nz, opp)
        if letter == "W":
            all_won += 1
        elif letter == "L":
            all_lost += 1
        else:
            all_drawn += 1
        all_for += nz
        all_against += opp

        has_scorers = test.get("nzTries") is not None
        if has_scorers:
            calc_nz, nz_tries = side_points(test.get("nzTries") or [], test.get("nzKickers") or [])
            calc_opp, opp_tries = side_points(test.get("oppTries") or [], test.get("oppKickers") or [])
            if calc_nz != nz or calc_opp != opp:
                raise SystemExit(
                    f"{test['id']}: scorers add to NZ {calc_nz}–{calc_opp} opp, "
                    f"but the final score is {nz}–{opp}"
                )
        else:
            nz_tries = None
            opp_tries = None

        if not is_test(test):
            continue
        test_count += 1
        if letter == "W":
            won += 1
        elif letter == "L":
            lost += 1
        else:
            drawn += 1
        points_for += nz
        points_against += opp
        if nz_tries is None or opp_tries is None:
            raise SystemExit(f"{test['id']}: a Test is missing a score sheet")
        tries_for += nz_tries
        tries_against += opp_tries
        results.append(
            {
                "id": test["id"],
                "date": test["date"],
                "dateLabel": test["dateLabel"],
                "opponent": test["opponent"],
                "venue": test["venue"],
                "competition": test["competition"],
                "result": letter,
                "nzScore": nz,
                "oppScore": opp,
                "line": f"{letter} {nz}–{opp}",
                "triesFor": nz_tries,
                "triesAgainst": opp_tries,
                "sources": test["sources"],
            }
        )

    tests_only = [t for t in data["tests"] if t.get("status") == "played" and is_test(t)]
    players = player_points(tests_only)
    ranked = sorted(players.values(), key=lambda row: (-row["points"], -row["tries"], row["player"]))
    top_points = ranked[0] if ranked else None
    top_tries = sorted(players.values(), key=lambda row: (-row["tries"], -row["points"], row["player"]))
    top_try = top_tries[0] if top_tries else None

    return {
        "played": test_count,
        "upcoming": len(upcoming),
        "won": won,
        "lost": lost,
        "drawn": drawn,
        "pointsFor": points_for,
        "pointsAgainst": points_against,
        "pointsDifference": points_for - points_against,
        "triesFor": tries_for,
        "triesAgainst": tries_against,
        "topTryScorer": top_try,
        "topPointsScorer": top_points,
        "results": results,
        "allGames": {
            "played": played_count,
            "won": all_won,
            "lost": all_lost,
            "drawn": all_drawn,
            "pointsFor": all_for,
            "pointsAgainst": all_against,
            "note": "Tests plus the four tour matches on the Rugby Database list. Try counts are Tests only.",
        },
        "rules": "Tests only for tries and points scorers. try 5, conversion 2, penalty goal 3, penalty try 7 (counts as a try, no player credited). Tour matches have no score sheet here, so they are in the all-games record only.",
    }


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    derived = compute(data)
    data["derived"] = derived
    DATA_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(
        f"Played {derived['played']}  "
        f"W{derived['won']} L{derived['lost']} D{derived['drawn']}  "
        f"PF {derived['pointsFor']} PA {derived['pointsAgainst']}  "
        f"TF {derived['triesFor']} TA {derived['triesAgainst']}"
    )
    top_t = derived["topTryScorer"]
    top_p = derived["topPointsScorer"]
    print(f"Top tries: {top_t['player']} {top_t['tries']}")
    print(f"Top points: {top_p['player']} {top_p['points']}")
    for row in derived["results"]:
        print(f"  {row['dateLabel']}  {row['opponent']:14}  {row['line']}")


if __name__ == "__main__":
    main()
