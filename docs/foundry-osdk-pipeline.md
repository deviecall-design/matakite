# Foundry OSDK Pipeline
## ESPN → Matakite → Foundry Data Architecture

**Phase:** B  
**Last Updated:** 2026-07-01

---

## Overview

This document defines the data architecture for persisting ESPN rugby data into Palantir Foundry via the OSDK (Object SDK). It covers:

- Object type definitions
- Transform pipeline (ingest → normalise → persist)
- Polling strategy + data freshness SLAs
- Error handling + retry policy
- Query patterns for downstream consumers

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ESPN API                                                    │
│  sports.core.api.espn.com  +  site.api.espn.com             │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP/JSON (no auth, public endpoints)
                │
┌───────────────▼─────────────────────────────────────────────┐
│  ESPNClient  (src/services/espn-client.ts)                  │
│  18 methods · retry/backoff · typed responses               │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│  ESPNIntegration  (src/services/espn-integration.ts)        │
│  Schema mapping · state transforms · dashboard shapes       │
└──────────┬───────────────────────┬──────────────────────────┘
           │                       │
           ▼                       ▼
┌──────────────────┐   ┌───────────────────────────────────────┐
│  fusion_server   │   │  Foundry OSDK Pipeline                │
│  WebSocket :8080 │   │  (src/pipelines/foundry-ingest.ts)    │
│  REST :3940      │   │  ESPNIngestPipeline class             │
│  Dashboard HTML  │   │  Object writers + batch upserts       │
└──────────────────┘   └───────────────┬───────────────────────┘
                                       │ OSDK writes
                               ┌───────▼──────────┐
                               │  Palantir Foundry │
                               │  6 Object Types   │
                               └──────────────────┘
```

---

## Foundry Object Types

### 1. `rugbyMatch`
**Primary dataset for game records.**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `espnEventId` | String (PK) | `event.id` | |
| `espnLeagueId` | String | Config | |
| `homeTeamId` | String | `competitor.id (home)` | |
| `awayTeamId` | String | `competitor.id (away)` | |
| `homeTeamName` | String | `competitor.displayName` | |
| `awayTeamName` | String | `competitor.displayName` | |
| `venueId` | String | `event.venue.id` | |
| `venueName` | String | `event.venue.fullName` | |
| `kickoff` | DateTime | `event.date` | UTC |
| `competitionName` | String | Derived from league | |
| `phase` | Enum | Derived from status | pre-match/first-half/half-time/second-half/full-time |
| `homeScore` | Integer | `competitor.score` | null until final |
| `awayScore` | Integer | `competitor.score` | null until final |
| `refereeId` | String | `officials[0].id` | |
| `broadcastRegions` | Array\<String\> | `broadcasts[].region` | |
| `homeWinProbability` | Decimal | ESPN odds → derived | null if no odds |
| `sourceRef` | String | `"espn"` | |
| `provenance` | Enum | `"OBSERVED"` | |
| `classification` | Enum | `"OPEN"` | |
| `createdAt` | DateTime | Ingest time | |
| `updatedAt` | DateTime | Ingest time | |

**Update frequency:** Created at discovery (T-7d), updated every 30s during live, immutable after full-time.

---

### 2. `rugbyTeam`
**Master team registry.**

| Field | Type | Source |
|-------|------|--------|
| `espnTeamId` | String (PK) | `team.id` |
| `displayName` | String | `team.displayName` |
| `shortName` | String | `team.shortDisplayName` |
| `abbreviation` | String | `team.abbreviation` |
| `logoUrl` | String | `team.logo` |
| `color` | String | `team.color` |
| `venueId` | String | `team.venue.id` |
| `espnLeagueId` | String | Config |
| `sourceRef` | String | `"espn"` |
| `lastUpdated` | DateTime | |

**Update frequency:** Weekly sync.

---

### 3. `rugbyAthlete`
**Player registry with career stubs.**

| Field | Type | Source |
|-------|------|--------|
| `espnAthleteId` | String (PK) | `athlete.id` |
| `displayName` | String | `athlete.displayName` |
| `firstName` | String | `athlete.firstName` |
| `lastName` | String | `athlete.lastName` |
| `position` | String | `athlete.position` |
| `dateOfBirth` | Date | `athlete.dateOfBirth` |
| `height` | Integer | `athlete.height` (cm) |
| `weight` | Integer | `athlete.weight` (kg) |
| `currentTeamId` | String | `athlete.team.id` |
| `jersey` | Integer | `athlete.jersey` |
| `active` | Boolean | `athlete.active` |
| `sourceRef` | String | `"espn"` |
| `lastUpdated` | DateTime | |

**Update frequency:** Weekly sync per league.

---

### 4. `playerStatLine`
**Per-match per-player statistics. Immutable after post-match.**

| Field | Type | Source |
|-------|------|--------|
| `id` | String (PK) | `{matchId}-{athleteId}` |
| `matchId` | String | FK → rugbyMatch |
| `athleteId` | String | FK → rugbyAthlete |
| `teamId` | String | FK → rugbyTeam |
| `position` | String | From boxscore |
| `minutesPlayed` | Integer | From substitution plays |
| `carries` | Integer | `statistics[carries]` |
| `metresGained` | Integer | `statistics[metres]` |
| `tackles` | Integer | `statistics[tackles]` |
| `tacklesWon` | Integer | Subset of tackles |
| `passes` | Integer | `statistics[passes]` |
| `kicksAttempted` | Integer | `statistics[kicksAttempted]` |
| `kicksCompleted` | Integer | `statistics[kicksCompleted]` |
| `turnoversWon` | Integer | `statistics[turnoversWon]` |
| `errors` | Integer | `statistics[errors]` |
| `triesScored` | Integer | Derived from plays |
| `conversionsMade` | Integer | Derived from plays |
| `penaltiesKicked` | Integer | Derived from plays |
| `sourceRef` | String | `"espn"` |
| `provenance` | Enum | `"OBSERVED"` |
| `createdAt` | DateTime | T+1 ingest |

**Update frequency:** Created once per match at T+1 hour post-final. Immutable.

---

### 5. `refereeProfile`
**Referee behavioral model. Updated quarterly.**

| Field | Type | Source |
|-------|------|--------|
| `espnRefId` | String (PK) | `official.id` |
| `displayName` | String | `official.displayName` |
| `breakdownPenaltyRate` | Decimal | Derived from historical plays |
| `scrumPenaltyRate` | Decimal | Derived from historical plays |
| `maulCallTendency` | Enum | Derived: conservative/neutral/permissive |
| `cardTendency` | Enum | Derived: strict/balanced/lenient |
| `matchesRefereed` | Integer | Count from plays |
| `lastUpdated` | DateTime | |

**Update frequency:** Quarterly (compute from playerStatLine + play aggregates).

---

### 6. `matchPhase`
**Live play-by-play events. Append-only during match.**

| Field | Type | Source |
|-------|------|--------|
| `id` | String (PK) | `{matchId}-{play.sequenceNumber}` |
| `matchId` | String | FK → rugbyMatch |
| `sequenceNumber` | Integer | `play.sequenceNumber` |
| `periodNumber` | Integer | `play.period.number` |
| `clockSeconds` | Integer | `play.clock.value` |
| `playTypeId` | String | `play.type.id` |
| `playTypeText` | String | `play.type.text` |
| `playText` | String | `play.text` |
| `homeTeamEvent` | Boolean | `play.homeTeamEvent` |
| `scoringPlay` | Boolean | `play.scoringPlay` |
| `athleteId` | String | `play.athletesInvolved[0].id` |
| `ingestedAt` | DateTime | |

**Update frequency:** Every 10 seconds during live match. Append-only.

---

## Ingest Pipeline

### Phase B Pipeline (`src/pipelines/foundry-ingest.ts`)

```typescript
export class ESPNIngestPipeline {

  // ── Weekly Discovery ──────────────────────────────────────────
  async runDiscovery(leagueId: string): Promise<void> {
    // 1. GET /v2/sports/rugby/leagues/{league}/events
    // 2. For each event: upsert rugbyMatch (initial state)
    // 3. GET /v2/sports/rugby/leagues/{league}/athletes
    // 4. For each athlete: upsert rugbyAthlete
    // 5. GET /apis/site/v2/sports/rugby/{league}/teams
    // 6. For each team: upsert rugbyTeam
  }

  // ── Pre-Match (T-2h before kickoff) ──────────────────────────
  async runPreMatch(eventId: string): Promise<void> {
    // 1. GET /apis/site/v2/sports/rugby/{league}/teams/{homeTeamId}/roster
    // 2. GET /apis/site/v2/sports/rugby/{league}/teams/{awayTeamId}/roster
    // 3. GET .../events/{eventId}/competitions/{compId}/officials
    // 4. Upsert referee via refereeProfile
    // 5. Update rugbyMatch.phase = "pre-match"
  }

  // ── Live Match (T0 → T+80m, every 10s) ────────────────────────
  async runLiveMatch(eventId: string, competitionId: string): Promise<void> {
    // 1. GET .../events/{eventId}/competitions/{compId}/plays
    // 2. For new plays since last cursor: insert matchPhase records
    // 3. Update rugbyMatch.score + phase from latest status
    // Polling loop exits when status = FINAL
  }

  // ── Post-Match (T+1h after final whistle) ────────────────────
  async runPostMatch(eventId: string): Promise<void> {
    // 1. GET /apis/site/v2/sports/rugby/{league}/summary?event={eventId}
    // 2. Extract boxscore statistics per competitor
    // 3. Insert playerStatLine records (once, immutable)
    // 4. Update rugbyMatch.phase = "full-time" + final scores
    // 5. Trigger calibration pipeline (prediction vs actual)
  }

  // ── Standings Snapshot (Daily) ────────────────────────────────
  async runStandingsSnapshot(leagueId: string): Promise<void> {
    // 1. GET /v2/sports/rugby/leagues/{league}/standings
    // 2. Persist as timestamped snapshot (trend analysis)
  }

}
```

---

## Data Freshness SLAs

| Object | Target Freshness | Ingest Trigger | Polling Interval |
|--------|-----------------|----------------|-----------------|
| rugbyMatch (pre-match) | T-7d | Weekly discovery | — |
| rugbyMatch (live score) | ≤30s | Match start | 30s |
| rugbyMatch (final) | T+1h | Post-match | — |
| rugbyTeam | ≤24h | Weekly | — |
| rugbyAthlete | ≤24h | Weekly | — |
| playerStatLine | T+1h post-match | Post-match trigger | — |
| matchPhase | ≤10s | Live match | 10s |
| refereeProfile | ≤90d | Quarterly | — |

---

## Polling Strategy

### Decision Tree

```
Kickoff detected (scoreboard phase = "pre-match")
    → Pre-match pipeline runs (T-2h)
    → Every 30s: poll scoreboard for phase transition

Phase = "first-half" or "second-half"
    → Switch to plays polling (10s interval)
    → Maintain scoreboard polling in parallel (30s)

Phase = "half-time"
    → Pause plays polling (no new plays)
    → Keep scoreboard polling (30s)

Phase = "full-time"
    → Stop all polling for this match
    → Queue post-match pipeline (T+1h delay)
    → Clear from active poll set
```

### Live Match Cursor

Track last seen `sequenceNumber` per match to avoid reprocessing plays:

```typescript
interface PollCursor {
  matchId: string;
  competitionId: string;
  lastSequenceNumber: number;
  pollingIntervalMs: number;
  phase: MatchPhase;
  startedAt: string;
}
```

---

## Error Handling

### ESPN API Errors

| HTTP Status | Action |
|-------------|--------|
| 200 | Process normally |
| 404 | Log + skip (match may not exist yet) |
| 429 | Back off 60s, then retry |
| 500 | Log + retry after 30s (ESPN server issue) |
| Timeout | Retry with exponential backoff (500ms, 1s, 2s) |

### Foundry OSDK Errors

| Error Type | Action |
|------------|--------|
| Conflict (409) | Upsert — overwrite stale record |
| Rate limit | Batch writes, max 50 objects/call |
| Auth expired | Refresh token, retry once |
| Network | Retry 3× with backoff, then dead letter queue |

### Dead Letter Queue

Failed ingest records go to `data/espn-dlq.jsonl` for manual review:

```jsonl
{"ts": "2026-07-01T10:00:00Z", "type": "playerStatLine", "matchId": "X", "error": "..."}
```

---

## Query Patterns

### Next Upcoming Match

```typescript
// rugbyMatch where phase = "pre-match" AND kickoff > NOW
// ORDER BY kickoff ASC LIMIT 1
const nextMatch = await foundry.objects
  .rugbyMatch
  .filter({ phase: "pre-match" })
  .orderBy("kickoff", "asc")
  .first();
```

### Latest Standings

```typescript
// rugbyTeam with current stats
const standings = await foundry.objects
  .rugbyTeam
  .filter({ espnLeagueId: LEAGUE_ID })
  .orderBy("points", "desc")
  .all();
```

### Player Performance (Last 5 Matches)

```typescript
// playerStatLine for athlete, recent
const recent = await foundry.objects
  .playerStatLine
  .filter({ athleteId: "2639" })
  .orderBy("createdAt", "desc")
  .limit(5)
  .all();
```

### Live Plays for Active Match

```typescript
// matchPhase for current match, ordered by sequence
const plays = await foundry.objects
  .matchPhase
  .filter({ matchId: activeMatchId })
  .orderBy("sequenceNumber", "asc")
  .all();
```

### Referee History

```typescript
// matchPhase where play involves referee penalties
// Aggregate by refereeProfile to compute penalty rates
const refStats = await foundry.queries
  .refereeBreakdownRate({ refId: "2891" })
  .execute();
```

---

## Foundry Configuration

### Ontology Setup

1. Create Ontology in Foundry workspace: `matakite.rugby`
2. Register Object Types (6 types above)
3. Define Link Types:
   - `rugbyMatch.homeTeam → rugbyTeam`
   - `rugbyMatch.awayTeam → rugbyTeam`
   - `rugbyMatch.referee → refereeProfile`
   - `playerStatLine.match → rugbyMatch`
   - `playerStatLine.athlete → rugbyAthlete`
   - `matchPhase.match → rugbyMatch`

### OSDK Client Init

```typescript
// src/osdk/client.ts
import { createClient } from '@osdk/client';
import { $ontologyRid } from './ontology.js';

export const foundry = createClient(
  process.env.FOUNDRY_URL!,       // e.g. https://company.palantircloud.com
  process.env.FOUNDRY_CLIENT_ID!,
  process.env.FOUNDRY_TOKEN!,
  $ontologyRid
);
```

### Environment Variables

```bash
# .env (never commit)
FOUNDRY_URL=https://company.palantircloud.com
FOUNDRY_CLIENT_ID=your-client-id
FOUNDRY_TOKEN=your-token
MATAKITE_LEAGUE_ID=242041          # Super Rugby Pacific
```

---

## What's Ephemeral vs Persisted

| Data | Ephemeral | Persisted |
|------|-----------|-----------|
| Scoreboard (live score) | ✓ WS state | ✓ rugbyMatch.score (update) |
| Play-by-play | ✓ WS broadcast | ✓ matchPhase (append) |
| Win probability (model) | ✓ WS state | ✗ (recalculated) |
| The Call | ✓ WS state | ✗ (recalculated) |
| Final score | ✗ | ✓ rugbyMatch (immutable after FINAL) |
| Player stats | ✗ | ✓ playerStatLine (immutable) |
| Standings | ✓ WS state | ✓ snapshot + current |
| Team rosters | ✓ cache 24h | ✓ rugbyAthlete |
| Odds | ✓ WS enrichment | ✗ (not persisted) |
| News | ✗ | ✗ (future: newsItem object) |

---

## Future Enhancements

1. **Actions** — Use Foundry Actions to trigger "Confirm Prediction" workflows
2. **Transforms** — Pipeline transforms for Brier score computation (match prediction vs actual)
3. **Notifications** — Foundry-triggered alerts when win prob crosses thresholds
4. **Worksheets** — Analyst worksheet over playerStatLine for selection modelling
5. **AIP** — AI assistant queries against the ontology for natural language insights

---

*Matakite Foundry OSDK Pipeline v1.0 | Operation Kāhu | Deviecall*
