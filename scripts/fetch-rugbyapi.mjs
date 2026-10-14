#!/usr/bin/env node
/**
 * Refresh data/rugbyapi-snapshot.json from rugbyAPI.
 *
 *   RUGBYAPI_KEY=... node scripts/fetch-rugbyapi.mjs
 *   node scripts/fetch-rugbyapi.mjs --self-check
 *
 * The key is read from process.env.RUGBYAPI_KEY and is never written.
 * Authorization: Bearer, which is what rugbyAPI documents. X-API-Key is
 * the documented fallback and is not used here.
 *
 * A free key covers 11 endpoints and 50 lookups a day, from yesterday
 * forward, without include. Form, player profiles, lineups and timelines
 * need Archive. A 403 plan_required is recorded and the rest of the
 * snapshot is still written. The site reads the snapshot only.
 *
 * Quality flags (https://rugbyapi.com/documentation/guides/data-quality):
 *   timeline: complete | short | over | partial | none
 *   lineups:  complete | partial | contaminated | missing
 *   duplicate_of: the weaker record points at the better one
 * A timeline is stored only when the flag is complete and the event
 * points add up to the final score. Lineups are stored only when the
 * flag is complete and no player is on both sides. Scores that disagree
 * with data/all-blacks-2026.json are kept as disagreements. They do not
 * replace the season file.
 */

import { readFileSync, writeFileSync, renameSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SEASON_PATH = path.join(ROOT, "data", "all-blacks-2026.json");
const SNAPSHOT_PATH = path.join(ROOT, "data", "rugbyapi-snapshot.json");
const BASE = "https://api.rugbyapi.com/v1";
const DOCS = "https://rugbyapi.com/documentation";
const REQUEST_CAP = Number(process.env.RUGBYAPI_MAX_REQUESTS || 24);
const PLAYER_CAP = 8;

const EVENT_POINTS = {
  try: 5,
  penalty_try: 7,
  conversion: 2,
  penalty_goal: 3,
  drop_goal: 3,
  yellow_card: 0,
  red_card: 0,
};

const CLUB_COMPETITION = /super rugby|premiership|top 14|pro d2|united rugby|champions cup|currie cup|national provincial|major league rugby|\burc\b/i;
const TEST_COMPETITION = /test match|tests\b|nations championship|nations cup|rugby championship|bledisloe|world cup|six nations|autumn nations|pacific nations|friendly international|greatest rivalry/i;

const SAME_SIDE = [
  ["new zealand", "all blacks"],
  ["australia", "wallabies"],
  ["south africa", "springboks"],
  ["france", "les bleus"],
  ["england"],
  ["wales"],
  ["scotland"],
  ["ireland"],
  ["italy"],
  ["argentina", "pumas"],
  ["fiji"],
  ["samoa"],
  ["tonga"],
  ["japan"],
  ["georgia"],
];

export function redact(text, key) {
  let out = String(text ?? "");
  if (key) out = out.split(key).join("[redacted]");
  out = out.replace(/rug_live_[A-Za-z0-9]+/g, "[redacted]");
  out = out.replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
  return out;
}

export function normName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[’‘]/g, "'")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9']+/g, " ")
    .trim();
}

export function sameSide(left, right) {
  const a = normName(left);
  const b = normName(right);
  if (!a || !b) return false;
  if (a === b) return true;
  return SAME_SIDE.some((group) => group.includes(a) && group.includes(b));
}

export function eventPoints(event) {
  if (event && Number.isFinite(event.points)) return event.points;
  return EVENT_POINTS[event && event.type] ?? null;
}

export function timelineSums(events) {
  const total = { home: 0, away: 0 };
  let unknown = false;
  for (const event of events || []) {
    const points = eventPoints(event);
    if (points == null) {
      unknown = true;
      continue;
    }
    if (event.side === "home" || event.side === "away") total[event.side] += points;
    else unknown = true;
  }
  return { total, unknown };
}

export function assessQuality(match) {
  const quality = (match && match.quality) || {};
  const timelineFlag = quality.timeline || "none";
  const lineupFlag = quality.lineups || "missing";
  const events = timelineEvents(match);
  const summed = timelineSums(events);
  const homeScore = scoreOf(match && match.home);
  const awayScore = scoreOf(match && match.away);
  const addsUp = homeScore != null
    && awayScore != null
    && !summed.unknown
    && summed.total.home === homeScore
    && summed.total.away === awayScore;

  let timelineUsed = false;
  let timelineReason = "";
  if (quality.duplicate_of) {
    timelineReason = "This record points at " + quality.duplicate_of + ". It is not the canonical match.";
  } else if (timelineFlag !== "complete") {
    timelineReason = "Timeline flag is " + timelineFlag + ". Only complete is stored.";
  } else if (!events.length) {
    timelineReason = "Timeline flag is complete, but no events were returned.";
  } else if (!addsUp) {
    timelineReason = "Timeline flag is complete, but the event points do not add up to the final score. They are not stored.";
  } else {
    timelineUsed = true;
    timelineReason = "Timeline flag is complete and the event points add up to the final score.";
  }

  const lineups = lineupSides(match);
  const shared = sharedPlayers(lineups);
  let lineupsUsed = false;
  let lineupsReason = "";
  if (quality.duplicate_of) {
    lineupsReason = "This record points at " + quality.duplicate_of + ". Lineups are not stored.";
  } else if (lineupFlag !== "complete") {
    lineupsReason = "Lineups flag is " + lineupFlag + ". Only complete is stored.";
  } else if (!lineups.home.length || !lineups.away.length) {
    lineupsReason = "Lineups flag is complete, but one side has no players.";
  } else if (shared.length) {
    lineupsReason = "A player is listed on both sides (" + shared.join(", ") + "). Lineups are not stored.";
  } else {
    lineupsUsed = true;
    lineupsReason = "Lineups flag is complete and no player is on both sides.";
  }

  return {
    duplicateOf: quality.duplicate_of || null,
    timelineFlag,
    lineupFlag,
    timelineUsed,
    timelineReason,
    lineupsUsed,
    lineupsReason,
    summed,
  };
}

function scoreOf(side) {
  if (!side || side.score == null || side.score === "") return null;
  const number = Number(side.score);
  return Number.isFinite(number) ? number : null;
}

function timelineEvents(match) {
  const block = match && match.timeline;
  if (!block) return [];
  if (Array.isArray(block)) return block;
  if (Array.isArray(block.data)) return block.data;
  return [];
}

function lineupSides(match) {
  const block = match && (match.lineups || match.lineup);
  const empty = { home: [], away: [] };
  if (!block) return empty;
  return {
    home: Array.isArray(block.home) ? block.home : [],
    away: Array.isArray(block.away) ? block.away : [],
  };
}

function playerId(entry) {
  const player = entry && (entry.player || entry);
  return player && player.id ? String(player.id) : "";
}

function sharedPlayers(lineups) {
  const home = new Set(lineups.home.map(playerId).filter(Boolean));
  return lineups.away.map(playerId).filter((id) => id && home.has(id));
}

export function nzView(match, teamId) {
  const home = match.home || {};
  const away = match.away || {};
  const homeIsNz = (teamId && home.id === teamId) || sameSide(home.name, "New Zealand");
  const awayIsNz = (teamId && away.id === teamId) || sameSide(away.name, "New Zealand");
  if (homeIsNz === awayIsNz) return null;
  if (homeIsNz) {
    return {
      nzScore: scoreOf(home),
      oppScore: scoreOf(away),
      opponent: away.name || "",
      nzHome: true,
      nzTeamId: home.id || teamId || null,
    };
  }
  return {
    nzScore: scoreOf(away),
    oppScore: scoreOf(home),
    opponent: home.name || "",
    nzHome: false,
    nzTeamId: away.id || teamId || null,
  };
}

function dayDistance(left, right) {
  if (!left || !right) return null;
  const a = Date.parse(left + "T00:00:00Z");
  const b = Date.parse(right + "T00:00:00Z");
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return Math.round((a - b) / 86400000);
}

export function crossCheckMatch(match, seasonGames, teamId) {
  const view = nzView(match, teamId);
  const quality = assessQuality(match);
  const base = {
    rugbyId: match && match.id || null,
    date: match && match.date || null,
    status: match && match.status || null,
    opponent: view ? view.opponent : null,
    nzScore: view ? view.nzScore : null,
    oppScore: view ? view.oppScore : null,
    seasonId: null,
    decision: "no-season-row",
    note: "No season-file game shares this date and opponent.",
    timelineUsed: false,
    timelineReason: quality.timelineReason,
    lineupsUsed: false,
    lineupsReason: quality.lineupsReason,
  };
  if (quality.duplicateOf) {
    return {
      ...base,
      decision: "withheld-duplicate",
      note: "duplicate_of is " + quality.duplicateOf + ". The season file is unchanged.",
    };
  }
  if (!view) {
    return { ...base, decision: "not-all-blacks", note: "New Zealand are not exactly one of the two sides." };
  }
  const candidates = seasonGames.filter((game) => {
    const distance = dayDistance(match.date, game.date);
    return distance != null && Math.abs(distance) <= 1 && sameSide(view.opponent, game.opponent);
  });
  if (candidates.length !== 1) {
    if (candidates.length > 1) {
      return { ...base, decision: "ambiguous", note: "More than one season-file game is within a day of this opponent." };
    }
    return base;
  }
  const game = candidates[0];
  const played = game.status === "played" && game.nzScore != null && game.oppScore != null;
  const rugbyFinished = view.nzScore != null && view.oppScore != null && match.status === "finished";
  let decision = "fixture";
  let note = "Dates and opponent agree. rugbyAPI has no final score, so the season file is unchanged.";
  if (played && rugbyFinished) {
    if (view.nzScore === game.nzScore && view.oppScore === game.oppScore) {
      decision = "agree";
      note = "Score agrees with " + game.id + ". The season file stays the record.";
    } else {
      decision = "disagree";
      note = "Score disagrees with " + game.id + " (" + game.nzScore + "–" + game.oppScore + "). The season file is kept.";
    }
  } else if (!played && rugbyFinished) {
    decision = "unverified-final";
    note = "rugbyAPI has a final score and the season file still lists this game as not played. The score is not copied onto the season card.";
  }
  const trustDetails = decision === "agree" || decision === "fixture";
  return {
    ...base,
    seasonId: game.id,
    seasonKind: game.kind || "test",
    sourcedNz: game.nzScore,
    sourcedOpp: game.oppScore,
    decision,
    note,
    timelineUsed: trustDetails && quality.timelineUsed && decision === "agree",
    timelineReason: decision === "disagree"
      ? "Score disagrees with the season file, so the timeline is not used."
      : (trustDetails ? quality.timelineReason : "No agreed final score, so the timeline is not used."),
    lineupsUsed: trustDetails && quality.lineupsUsed && (decision === "agree" || decision === "fixture"),
    lineupsReason: decision === "disagree"
      ? "Score disagrees with the season file, so the lineups are not used."
      : quality.lineupsReason,
  };
}

export function isAllBlacksTest(match, teamId) {
  const view = nzView(match, teamId);
  if (!view) return false;
  const competition = (match.competition && match.competition.name) || "";
  if (CLUB_COMPETITION.test(competition)) return false;
  if (TEST_COMPETITION.test(competition)) return true;
  return SAME_SIDE.some((group) => group.includes(normName(view.opponent)));
}

function trimSide(side) {
  if (!side) return null;
  return { id: side.id || null, name: side.name || null, score: scoreOf(side) };
}

function trimPlayer(entry) {
  const player = entry.player || {};
  return {
    id: player.id || null,
    name: player.name || null,
    shirt: entry.shirt ?? null,
    role: entry.role || null,
    position: entry.position || null,
    captain: entry.captain === true,
  };
}

export function publicMatch(match, check) {
  const quality = (match && match.quality) || {};
  const row = {
    id: match.id || null,
    date: match.date || null,
    kickoffUtc: match.kickoff_utc || null,
    status: match.status || null,
    competition: match.competition ? { id: match.competition.id || null, name: match.competition.name || null } : null,
    venue: match.venue ? { name: match.venue.name || null, city: match.venue.city || null, country: match.venue.country || null } : null,
    home: trimSide(match.home),
    away: trimSide(match.away),
    quality: {
      timeline: quality.timeline || null,
      lineups: quality.lineups || null,
      duplicate_of: quality.duplicate_of || null,
    },
    crossCheck: check.decision,
    crossCheckNote: check.note,
    seasonId: check.seasonId,
    timelineUsed: check.timelineUsed,
    timelineReason: check.timelineReason,
    lineupsUsed: check.lineupsUsed,
    lineupsReason: check.lineupsReason,
    timeline: null,
    lineups: null,
  };
  if (check.timelineUsed) {
    row.timeline = timelineEvents(match).map((event) => ({
      id: event.id || null,
      minute: event.minute ?? null,
      minuteExtra: event.minute_extra ?? null,
      type: event.type || null,
      side: event.side || null,
      player: event.player ? { id: event.player.id || null, name: event.player.name || null } : null,
      points: eventPoints(event),
      score: event.score || null,
    }));
  }
  if (check.lineupsUsed) {
    const sides = lineupSides(match);
    row.lineups = {
      home: sides.home.map(trimPlayer),
      away: sides.away.map(trimPlayer),
    };
  }
  return row;
}

export function seasonGamesFrom(season) {
  return (season.tests || []).map((game) => ({
    id: game.id,
    date: game.date,
    opponent: game.opponent,
    status: game.status,
    kind: game.kind || "test",
    nzScore: game.nzScore,
    oppScore: game.oppScore,
  }));
}

function unavailableSnapshot(reason) {
  return {
    schema: 1,
    generatedAt: new Date().toISOString(),
    generatedBy: "scripts/fetch-rugbyapi.mjs",
    source: sourceBlock(),
    connected: false,
    keyPresent: false,
    reason,
    requests: [],
    team: null,
    fixtures: [],
    matches: [],
    form: null,
    players: [],
    disagreements: [],
    qualityPolicy: qualityPolicy(),
    notUsed: notUsed(),
  };
}

function sourceBlock() {
  return {
    name: "rugbyAPI",
    base: BASE,
    docs: DOCS,
    terms: "https://rugbyapi.com/legal/terms",
    freeEndpoints: [
      "/v1/matches",
      "/v1/matches/{id}",
      "/v1/fixtures",
      "/v1/results",
      "/v1/competitions",
      "/v1/seasons/{id}/standings",
      "/v1/teams/{id}",
      "/v1/rankings",
      "/v1/search",
      "/v1/usage",
      "/v1/status",
    ],
    freeLookupsPerDay: 50,
    archiveNeeded: [
      "GET /v1/matches/{id}?include=lineups,timeline",
      "GET /v1/teams/{id}/form",
      "GET /v1/players/{id}",
    ],
    licenceNote: "rugbyAPI terms. This file is a snapshot. It does not contain an API key.",
  };
}

function qualityPolicy() {
  return "Timeline events are stored only when quality.timeline is complete and the event points add up to the final score. Lineups are stored only when quality.lineups is complete and no player is on both sides. duplicate_of records are not canonical. A score that disagrees with data/all-blacks-2026.json is listed and is not copied onto the season card.";
}

function notUsed() {
  return [
    "API-Sports API-Rugby is not called.",
    "The Kaggle international Test dataset is not used.",
    "ESPN's hidden site API is not used.",
  ];
}

function readJson(file) {
  return JSON.parse(readFileSync(file, "utf8"));
}

function writeSnapshot(payload, key) {
  const text = JSON.stringify(payload, null, 2) + "\n";
  if (key && text.includes(key)) {
    throw new Error("Refusing to write the snapshot because the API key was still in it.");
  }
  if (/rug_live_[A-Za-z0-9]+/.test(text)) {
    throw new Error("Refusing to write the snapshot because a key-shaped token was still in it.");
  }
  mkdirSync(path.dirname(SNAPSHOT_PATH), { recursive: true });
  const tmp = SNAPSHOT_PATH + ".tmp";
  writeFileSync(tmp, text);
  renameSync(tmp, SNAPSHOT_PATH);
}

function pickTeam(results) {
  const teams = (results || []).filter((row) => row && row.type === "team" && row.id);
  const exact = teams.filter((row) => normName(row.name) === "new zealand");
  const pool = exact.length ? exact : teams.filter((row) => normName(row.name) === "all blacks");
  const rejected = /u20|women|xv|maori|māori|sevens|schools/i;
  return pool.find((row) => !rejected.test(row.name || "")) || null;
}

function errorCode(body) {
  return body && body.error && body.error.code ? body.error.code : null;
}

function planLimited(result) {
  return result.status === 403 && errorCode(result.body) === "plan_required";
}

export async function buildSnapshot(options) {
  const key = (options.key || "").trim();
  const season = options.season;
  const games = seasonGamesFrom(season);
  const client = options.client;
  const cap = options.requestCap || REQUEST_CAP;
  if (!key) {
    return unavailableSnapshot("RUGBYAPI_KEY is not set. No request was sent. The dashboard keeps data/all-blacks-2026.json.");
  }
  const requests = [];
  let sent = 0;
  const limited = { include: false, form: false, players: false, history: false };

  async function get(requestPath, query) {
    if (sent >= cap) {
      const error = new Error("Stopped at " + cap + " requests so the daily allowance is not used up.");
      error.code = "request_cap";
      throw error;
    }
    sent += 1;
    let result;
    try {
      result = await client.get(new URL(BASE + requestPath + queryString(query)), key);
    } catch (error) {
      const message = redact(error && error.message, key);
      requests.push({ path: requestPath, status: 0, code: "network", message });
      throw new Error(message);
    }
    const code = errorCode(result.body);
    requests.push({
      path: requestPath,
      status: result.status,
      code,
      remaining: result.remaining ?? null,
    });
    return result;
  }

  const snapshot = {
    schema: 1,
    generatedAt: new Date().toISOString(),
    generatedBy: "scripts/fetch-rugbyapi.mjs",
    source: sourceBlock(),
    connected: false,
    keyPresent: true,
    reason: "",
    requests,
    team: null,
    fixtures: [],
    matches: [],
    form: null,
    players: [],
    disagreements: [],
    planLimits: limited,
    qualityPolicy: qualityPolicy(),
    notUsed: notUsed(),
  };

  try {
    const search = await get("/search", { q: "New Zealand" });
    if (search.status === 401) {
      snapshot.reason = "rugbyAPI refused the key (" + (errorCode(search.body) || "401") + "). No All Blacks rows were stored.";
      return snapshot;
    }
    if (search.status !== 200) {
      snapshot.reason = "Team search returned HTTP " + search.status + " (" + (errorCode(search.body) || "no code") + ").";
      return snapshot;
    }
    const found = pickTeam((search.body && search.body.data) || []);
    if (!found) {
      snapshot.reason = "Search did not return a New Zealand national side. No match was stored.";
      return snapshot;
    }
    const team = await get("/teams/" + found.id);
    if (team.status !== 200) {
      snapshot.reason = "GET /v1/teams/" + found.id + " returned HTTP " + team.status + ".";
      return snapshot;
    }
    const teamBody = team.body || {};
    if (teamBody.type && teamBody.type !== "national") {
      snapshot.reason = found.id + " is type " + teamBody.type + ", not a national side. No match was stored.";
      return snapshot;
    }
    if (!sameSide(teamBody.name, "New Zealand")) {
      snapshot.reason = "Team " + found.id + " is named " + (teamBody.name || "unknown") + ". It was not stored as the All Blacks.";
      return snapshot;
    }
    snapshot.team = {
      id: teamBody.id,
      name: teamBody.name,
      tag: teamBody.tag || null,
      country: teamBody.country || null,
      type: teamBody.type || null,
    };
    snapshot.connected = true;

    const fixtures = await get("/fixtures", { days: 60 });
    const fixtureRows = fixtures.status === 200 && fixtures.body && Array.isArray(fixtures.body.data) ? fixtures.body.data : [];
    if (fixtures.status !== 200) {
      snapshot.reason = "Fixtures returned HTTP " + fixtures.status + " (" + (errorCode(fixtures.body) || "no code") + ").";
    }

    const history = await get("/matches", {
      team: snapshot.team.id,
      date_from: "2026-01-01",
      date_to: new Date().toISOString().slice(0, 10),
      status: "finished",
    });
    let historyRows = [];
    if (planLimited(history)) {
      limited.history = true;
    } else if (history.status === 200 && history.body && Array.isArray(history.body.data)) {
      historyRows = history.body.data;
    }

    const byId = new Map();
    for (const row of fixtureRows.concat(historyRows)) {
      if (row && row.id && isAllBlacksTest(row, snapshot.team.id)) byId.set(row.id, row);
    }

    const detailed = [];
    for (const row of byId.values()) {
      if (sent >= cap) break;
      let full = row;
      if (!limited.include) {
        const withInclude = await get("/matches/" + row.id, { include: "lineups,timeline" });
        if (planLimited(withInclude)) {
          limited.include = true;
          const plain = await get("/matches/" + row.id);
          if (plain.status === 200) full = plain.body;
          else if (planLimited(plain)) limited.history = true;
        } else if (withInclude.status === 200) {
          full = withInclude.body;
        } else if (withInclude.status === 422) {
          const timelineOnly = await get("/matches/" + row.id, { include: "timeline" });
          if (timelineOnly.status === 200) full = timelineOnly.body;
        }
      } else {
        const plain = await get("/matches/" + row.id);
        if (plain.status === 200) full = plain.body;
        else if (planLimited(plain)) continue;
      }
      detailed.push(full);
    }

    const form = await get("/teams/" + snapshot.team.id + "/form", { last: 12 });
    if (planLimited(form)) {
      limited.form = true;
      snapshot.form = { available: false, reason: "GET /v1/teams/{id}/form needs Archive. The free key returned plan_required. No form is shown." };
    } else if (form.status === 200) {
      snapshot.form = {
        available: true,
        form: form.body.form || null,
        matches: (form.body.data || []).map((item) => {
          const check = crossCheckMatch(item, games, snapshot.team.id);
          return {
            id: item.id || null,
            date: item.date || null,
            result: item.result || null,
            competition: item.competition ? item.competition.name : null,
            home: trimSide(item.home),
            away: trimSide(item.away),
            crossCheck: check.decision,
            crossCheckNote: check.note,
            seasonId: check.seasonId,
          };
        }),
      };
    } else {
      snapshot.form = { available: false, reason: "Form returned HTTP " + form.status + "." };
    }

    const playerIds = [];
    for (const match of detailed) {
      const check = crossCheckMatch(match, games, snapshot.team.id);
      if (!check.lineupsUsed) continue;
      const sides = lineupSides(match);
      const nzSide = check && nzView(match, snapshot.team.id) && nzView(match, snapshot.team.id).nzHome ? sides.home : sides.away;
      for (const entry of nzSide) {
        const id = playerId(entry);
        if (id && !playerIds.includes(id)) playerIds.push(id);
      }
    }
    if (!playerIds.length) {
      snapshot.players = [];
      snapshot.playersNote = "No usable lineup carried a player id, so GET /v1/players/{id} was not called.";
    }
    for (const id of playerIds.slice(0, PLAYER_CAP)) {
      if (limited.players || sent >= cap) break;
      const player = await get("/players/" + id);
      if (planLimited(player)) {
        limited.players = true;
        snapshot.playersNote = "GET /v1/players/{id} needs Archive. The free key returned plan_required.";
        break;
      }
      if (player.status === 200 && player.body) {
        snapshot.players.push({
          id: player.body.id || id,
          name: player.body.name || null,
          position: player.body.position || null,
          nationality: player.body.nationality || null,
          status: player.body.status || null,
          team: player.body.team ? { id: player.body.team.id || null, name: player.body.team.name || null } : null,
        });
      }
    }

    snapshot.matches = detailed.map((match) => {
      const check = crossCheckMatch(match, games, snapshot.team.id);
      return publicMatch(match, check);
    });
    snapshot.fixtures = snapshot.matches.filter((match) => match.status !== "finished");
    snapshot.disagreements = snapshot.matches
      .filter((match) => match.crossCheck === "disagree")
      .map((match) => ({ id: match.id, seasonId: match.seasonId, note: match.crossCheckNote }));

    const agreed = snapshot.matches.filter((match) => match.crossCheck === "agree").length;
    const fixtureCount = snapshot.matches.filter((match) => match.crossCheck === "fixture").length;
    snapshot.reason = [
      "Fetched All Blacks Test rows for " + snapshot.team.name + " (" + snapshot.team.id + ").",
      agreed + " finished scores agree with the season file.",
      fixtureCount + " fixtures match a season-file date and opponent and have no rugbyAPI final score.",
      snapshot.disagreements.length + " scores disagree and were not copied onto the season file.",
      limited.include ? "include=lineups,timeline returned plan_required, so lineups and timelines were not stored." : "",
      limited.history ? "Finished matches before yesterday are outside the free key, so older Tests stay on the season file." : "",
      limited.form ? "Team form is an Archive endpoint and was not stored." : "",
      limited.players ? "Player profiles are an Archive endpoint and were not stored." : "",
    ].filter(Boolean).join(" ");
    if (!snapshot.matches.length && !snapshot.reason.includes("HTTP")) {
      snapshot.reason += " No All Blacks Test in the returned window.";
    }
    return snapshot;
  } catch (error) {
    snapshot.connected = Boolean(snapshot.team);
    snapshot.reason = redact(error && error.message, key);
    return snapshot;
  }
}

function queryString(query) {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(query || {})) {
    if (value != null && value !== "") params.set(name, String(value));
  }
  const text = params.toString();
  return text ? "?" + text : "";
}

function fakeResponse(status, body, remaining) {
  return { status, body, remaining: remaining ?? null };
}

export function selfCheck() {
  const failures = [];
  function check(name, ok) {
    if (!ok) failures.push(name);
  }

  const secret = "rug_live_examplekey0123456789abcd";
  check("redact", redact("bad " + secret + " Bearer " + secret, secret) === "bad [redacted] Bearer [redacted]");

  const complete = {
    id: "mt_ok",
    date: "2026-10-10",
    status: "finished",
    competition: { name: "Bledisloe Cup" },
    home: { id: "tm_nz", name: "New Zealand", score: 7 },
    away: { id: "tm_au", name: "Australia", score: 0 },
    quality: { timeline: "complete", lineups: "complete", duplicate_of: null },
    timeline: { data: [{ type: "try", side: "home", points: 5, player: { id: "pl_1", name: "Will Jordan" } }, { type: "conversion", side: "home", points: 2, player: { id: "pl_2", name: "Damian McKenzie" } }] },
    lineups: {
      home: [{ player: { id: "pl_1", name: "Will Jordan" }, shirt: 15, role: "starter", position: "Fullback", captain: false }],
      away: [{ player: { id: "pl_9", name: "Tom Wright" }, shirt: 15, role: "starter", position: "Fullback", captain: false }],
    },
  };
  const season = { tests: [{ id: "2026-10-10-australia-eden-park", date: "2026-10-10", opponent: "Australia", status: "played", kind: "test", nzScore: 50, oppScore: 19 }] };
  const shortTimeline = assessQuality(complete);
  check("complete timeline adds up", shortTimeline.timelineUsed === true);
  check("complete lineups used", shortTimeline.lineupsUsed === true);

  const short = { ...complete, quality: { ...complete.quality, timeline: "short" } };
  check("short flag withheld", assessQuality(short).timelineUsed === false);
  for (const flag of ["over", "partial", "none"]) {
    check(flag + " withheld", assessQuality({ ...complete, quality: { ...complete.quality, timeline: flag } }).timelineUsed === false);
  }
  const mismatch = {
    ...complete,
    timeline: { data: [{ type: "try", side: "home", points: 5 }] },
  };
  check("complete that does not add up is withheld", assessQuality(mismatch).timelineUsed === false);

  for (const flag of ["partial", "contaminated", "missing"]) {
    check("lineups " + flag, assessQuality({ ...complete, quality: { ...complete.quality, lineups: flag } }).lineupsUsed === false);
  }
  const both = {
    ...complete,
    lineups: {
      home: [{ player: { id: "pl_1", name: "Will Jordan" } }],
      away: [{ player: { id: "pl_1", name: "Will Jordan" } }],
    },
  };
  check("shared player withheld", assessQuality(both).lineupsUsed === false);
  const duplicate = { ...complete, quality: { timeline: "complete", lineups: "complete", duplicate_of: "mt_better" } };
  check("duplicate withheld", assessQuality(duplicate).timelineUsed === false && assessQuality(duplicate).lineupsUsed === false);

  const disagree = crossCheckMatch(complete, seasonGamesFrom(season), "tm_nz");
  check("score disagreement", disagree.decision === "disagree" && disagree.timelineUsed === false);

  const agreedMatch = {
    ...complete,
    home: { id: "tm_nz", name: "New Zealand", score: 50 },
    away: { id: "tm_au", name: "Australia", score: 19 },
    timeline: { data: [{ type: "try", side: "home", points: 5 }, { type: "penalty_goal", side: "away", points: 3 }] },
  };
  // 5 and 3 do not add to 50-19, so timeline stays withheld even when the score agrees.
  const agreed = crossCheckMatch({
    ...agreedMatch,
    timeline: {
      data: [
        { type: "try", side: "home", points: 50 },
        { type: "penalty_goal", side: "away", points: 19 },
      ],
    },
  }, seasonGamesFrom(season), "tm_nz");
  check("agreeing score", agreed.decision === "agree" && agreed.seasonId === "2026-10-10-australia-eden-park");
  check("agreeing timeline stored", agreed.timelineUsed === true);

  const published = publicMatch(complete, crossCheckMatch(complete, seasonGamesFrom(season), "tm_nz"));
  check("disagreement drops events", published.crossCheck === "disagree" && published.timeline == null && published.lineups == null);

  const fixture = {
    id: "mt_syd",
    date: "2026-10-17",
    status: "scheduled",
    competition: { name: "Bledisloe Cup" },
    home: { id: "tm_au", name: "Australia", score: null },
    away: { id: "tm_nz", name: "New Zealand", score: null },
    quality: { timeline: "none", lineups: "missing", duplicate_of: null },
    kickoff_utc: "2026-10-17T04:45:00Z",
  };
  const fixtureCheck = crossCheckMatch(fixture, seasonGamesFrom({
    tests: [{ id: "2026-10-17-australia-sydney", date: "2026-10-17", opponent: "Australia", status: "upcoming", kind: "test", nzScore: null, oppScore: null }],
  }), "tm_nz");
  check("fixture match", fixtureCheck.decision === "fixture" && fixtureCheck.seasonId === "2026-10-17-australia-sydney");
  check("club match excluded", isAllBlacksTest({
    competition: { name: "Super Rugby Pacific" },
    home: { id: "tm_nz", name: "New Zealand" },
    away: { name: "Crusaders" },
  }, "tm_nz") === false);
  check("wallabies alias", sameSide("Wallabies", "Australia"));

  const calls = [];
  const missing = awaitBuild(buildSnapshot({
    key: "",
    season: { tests: [] },
    client: { get() { calls.push("no"); return fakeResponse(200, {}); } },
  }));
  return Promise.resolve(missing).then((empty) => {
    check("missing key sends nothing", calls.length === 0 && empty.connected === false && empty.matches.length === 0);
    const seen = [];
    const client = {
      get(url) {
        const href = String(url);
        seen.push(href);
        if (href.includes("secret")) return fakeResponse(500, { error: { message: secret } });
        if (href.endsWith("/search?q=New+Zealand")) {
          return fakeResponse(200, { data: [{ type: "team", id: "tm_nz", name: "New Zealand", country: "New Zealand" }, { type: "team", id: "tm_u20", name: "New Zealand U20" }] });
        }
        if (href.endsWith("/teams/tm_nz")) return fakeResponse(200, { id: "tm_nz", name: "New Zealand", type: "national", tag: "NZL", country: "New Zealand" });
        if (href.includes("/fixtures")) return fakeResponse(200, { data: [fixture] });
        if (href.includes("/matches?team=")) return fakeResponse(403, { error: { code: "plan_required", message: "Archive required" } });
        if (href.includes("include=")) return fakeResponse(403, { error: { code: "plan_required", upgrade: "https://rugbyapi.com/pricing" } });
        if (href.endsWith("/matches/mt_syd")) return fakeResponse(200, fixture);
        if (href.includes("/form")) return fakeResponse(403, { error: { code: "plan_required" } });
        if (href.includes("/players/")) return fakeResponse(403, { error: { code: "plan_required" } });
        return fakeResponse(404, { error: { code: "not_found" } });
      },
    };
    return buildSnapshot({
      key: secret,
      season: { tests: [{ id: "2026-10-17-australia-sydney", date: "2026-10-17", opponent: "Australia", status: "upcoming", kind: "test", nzScore: null, oppScore: null }] },
      client,
    }).then((live) => {
      const encoded = JSON.stringify(live);
      check("free key degrades", live.connected === true && live.planLimits.include && live.planLimits.form && live.planLimits.history);
      check("players skipped without an id", live.players.length === 0 && /player id/.test(live.playersNote || ""));
      check("fixture kept", live.matches.some((match) => match.id === "mt_syd" && match.crossCheck === "fixture"));
      check("no timeline stored on free tier", live.matches.every((match) => match.timeline == null));
      check("key absent from snapshot", !encoded.includes(secret) && !encoded.includes("rug_live_"));
      check("bearer not in requests", seen.every((href) => !href.includes(secret)));
      if (failures.length) {
        const error = new Error(failures.join("; "));
        error.failures = failures;
        throw error;
      }
    });
  });
}

function awaitBuild(value) {
  return value;
}

async function main() {
  if (process.argv.includes("--self-check")) {
    await selfCheck();
    console.log("self-check passed");
    return 0;
  }
  const key = (process.env.RUGBYAPI_KEY || "").trim();
  if (!key) {
    let existing = null;
    try {
      existing = readJson(SNAPSHOT_PATH);
    } catch {
      existing = null;
    }
    if (existing && existing.connected) {
      console.log("RUGBYAPI_KEY is not set. Left the existing connected snapshot in place. No request was sent.");
      return 0;
    }
    const snapshot = unavailableSnapshot("RUGBYAPI_KEY is not set. No request was sent. The dashboard keeps data/all-blacks-2026.json.");
    writeSnapshot(snapshot, "");
    console.log(snapshot.reason);
    return 0;
  }
  const season = readJson(SEASON_PATH);
  const snapshot = await buildSnapshot({
    key,
    season,
    requestCap: REQUEST_CAP,
    client: {
      async get(url, token) {
        const response = await fetch(url, {
          headers: {
            Authorization: "Bearer " + token,
            Accept: "application/json",
            "User-Agent": "MatakiteForecast/1.0 (snapshot refresh)",
          },
        });
        const text = await response.text();
        let body = null;
        try {
          body = text ? JSON.parse(text) : null;
        } catch {
          body = { error: { code: "bad_json", message: redact(text.slice(0, 180), token) } };
        }
        if (body && body.error && body.error.message) body.error.message = redact(body.error.message, token);
        return {
          status: response.status,
          body,
          remaining: response.headers.get("x-ratelimit-remaining"),
        };
      },
    },
  });
  writeSnapshot(snapshot, key);
  console.log(snapshot.connected ? "connected" : "not connected");
  console.log(snapshot.reason);
  console.log("requests " + snapshot.requests.length);
  return snapshot.connected || snapshot.reason ? 0 : 1;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isMain) {
  main().then((code) => {
    process.exitCode = code;
  }).catch((error) => {
    console.error(redact(error && error.message, process.env.RUGBYAPI_KEY || ""));
    process.exitCode = 1;
  });
}
