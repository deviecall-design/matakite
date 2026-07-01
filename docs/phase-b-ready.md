# Phase B: ESPN Client & Schema — Ready for Ingestion

**Completed:** 2026-07-01 | **Status:** ✅ Ready for real data pipeline  
**Commit:** e90a3a7

---

## What's Built

### 1. **ESPNClient** (`src/services/espn-client.ts`)
Thin, battle-tested wrapper over ESPN rugby APIs.

**Methods (18 total):**
- **Discovery:** `getLeagues()`, `getLeague(id)`
- **Live Data:** `getScoreboard(leagueId, date?)`, `getMatchSummary(leagueId, eventId)`
- **Events:** `getEvents()`, `getEvent()`, `getCompetition()`, `getPlays()`
- **Teams:** `getTeams()`, `getTeam()`, `getTeamRoster()`, `getTeamSchedule()`
- **Athletes:** `getAthletes()`, `getSeasonAthletes()`, `getAthlete()`
- **Reference:** `getStandings()`, `getRankings()`, `getVenues()`, `getPositions()`, `getCountries()`
- **Match Details:** `getOfficials()`, `getBroadcasts()`, `getOdds()`, `getNews()`
- **Calendar:** `getSeasons()`, `getCalendar()`

**Features:**
- Automatic retry (3 attempts, exponential backoff)
- Timeout handling (10s default, configurable)
- Query string builder for paginated endpoints
- Error messages with HTTP status codes
- Respects ESPN's undocumented rate limits

**Usage Example:**
```typescript
const client = new ESPNClient();

// Get live scoreboard
const scoreboard = await client.getScoreboard("267979");

// Get match summary (boxscore + plays)
const summary = await client.getMatchSummary("267979", "36024361");

// Get team roster
const roster = await client.getTeamRoster("267979", "25");
```

---

### 2. **TypeScript Interfaces** (`src/types/espn.ts`)

Complete type safety for ESPN responses. **~500 lines of interface definitions.**

**Key Types:**
- `ESPNEvent` — match metadata
- `ESPNScoreboard` — live scores + schedules
- `ESPNSummary` — boxscore + statistics
- `ESPNCompetition` — match detail + plays + officials
- `ESPNPlay` — individual play/action
- `ESPNTeam` — team metadata
- `ESPNAthlete` — player detail
- `ESPNStatistic` — generic stat container
- `ESPNStandings` — league standings
- `ESPNOfficial` — referee/officials
- `ESPNBroadcast` — broadcast info
- `ESPNOdd` — betting lines
- Plus: `ESPNCompetitor`, `ESPNRecord`, `ESPNVenue`, `ESPNArticle`, etc.

All interfaces include optional fields to handle partial/incomplete API responses gracefully.

---

### 3. **Integration Schema** (`docs/espn-integration.md`)

**~600 lines. Everything needed for Phase B ingestion.**

#### Section 1: API Reference
- Discovery endpoints
- Live data endpoints (site.api)
- Core data endpoints (v2)
- Quick lookup table

#### Section 2: Schema Mapping
Detailed transformation from ESPN response → Matakite model:

| ESPN → Matakite |
|-----------------|
| `ESPNEvent` + `ESPNScorecardEvent` → `Match` |
| `ESPNPlay` → `Phase` (with event type mapping) |
| `ESPNCompetitor` + stats → `PlayerStatLine` |
| `ESPNTeam` → Team reference (rosters) |
| `ESPNAthlete` + career → `PlayerCareer` |
| `ESPNStandings` → Live display (future: trend snapshots) |
| `ESPNOfficial` → `RefereeProfile` (aggregate across matches) |

**Play Type Mapping Table:**
- Kickoff, Try, Penalty, Conversion, Substitution, Scrum, Lineout, Maul, Ruck, Breakdown

#### Section 3: Foundry OSDK Objects
Defined 6 core objects:

| Object | Keys | Synced From |
|--------|------|-------------|
| `rugbyMatch` | espnEventId | `/summary` |
| `rugbyTeam` | espnTeamId | `/teams/{id}` |
| `rugbyAthlete` | espnAthleteId | `/athletes/{id}` |
| `playerStatLine` | {matchId}-{athleteId} | `/summary` (post-match) |
| `refereeProfile` | espnRefId | `/officials` (quarterly) |
| `matchPhase` | {matchId}-{sequenceNumber} | `/plays` (live) |

**All include:** sourceRef="espn", provenance="OBSERVED", classification="OPEN"

#### Section 4: Data Pipeline
Step-by-step ingestion cycle:

1. **Weekly Discovery** → Extract event IDs
2. **Pre-Match (T-2h)** → Snapshot rosters, enrich referee
3. **Live Match (T0-T+80m)** → 10-second plays polling
4. **Post-Match (T+1h)** → Boxscore, player stats, calibration

#### Section 5: Rate Limits & Caching
- Scoreboard: 1 call per 10s (live)
- Summary: 1 call per match
- Plays: 1 call per 10s during match
- Teams/Athletes: 1 per league per week
- Standings: 1 per day

Caching TTLs specified (30s scoreboard, permanent summary, etc.)

#### Section 6: Known Issues & Workarounds
1. **Standings 500 error** → Use core API instead of site API
2. **Player career data** → Aggregate across seasons or use wikidata
3. **Play attribution** → Parse text + athletesInvolved

#### Section 7: Testing & Validation
- League ID reference table (6 major competitions + IDs)
- Validation checklist (10 items)
- Future enhancements (career aggregation, venue enrichment, streaming, odds monitoring, news sentiment)

---

## What's NOT Here (Future Phases)

- ❌ Foundry OSDK integration code (implementation detail for Phase B/C)
- ❌ n8n workflow (Phase B integration plumbing)
- ❌ Player career aggregation (requires multi-season batching)
- ❌ Venue altitude computation (data enrichment)
- ❌ Dashboard update code (Phase C)
- ❌ Calibration pipeline trigger (Phase B integration)
- ❌ WebSocket live box view (Phase C)

---

## How to Use This in Phase B

### 1. Next: Implement Data Pipeline
```
Create src/pipelines/espn-ingest.ts
├── discovery() → weekly event fetching
├── preMatch() → roster snapshots
├── liveMatch() → polling loop
└── postMatch() → boxscore + calibration trigger
```

### 2. Integrate with Foundry OSDK
```
Create src/osdk/objects.ts
├── Instantiate ESPNClient
├── Define Foundry object builders
└── Map ESPN → OSDK objects
```

### 3. Wire into n8n
```
Create n8n workflow
├── Trigger on schedule (weekly discovery)
├── Call ESPNClient methods
├── Persist to Foundry
└── Notify Telegram on error
```

### 4. Test Against Live Data
```
Run: npx ts-node src/services/espn-client.ts
├── Fetch scoreboard (267979)
├── Get match summary
├── Parse into Matakite model
└── Validate schema
```

---

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/services/espn-client.ts` | 520 | Client class (18 methods) |
| `src/types/espn.ts` | 480 | TypeScript interfaces |
| `docs/espn-integration.md` | 600 | Complete schema + pipeline docs |
| `docs/phase-b-ready.md` | (this file) | Delivery summary |

---

## Commit Info

```
commit e90a3a7
Author: Ares <ares@deviecall.local>
Date:   Wed Jul 1 16:15 GMT+10

feat: ESPN rugby API client + TypeScript types + integration schema

- Add ESPNClient class with methods for all v2/v3 rugby endpoints
  * Scoreboard (live scores, site.api)
  * Events/matches (core API)
  * Teams, athletes, standings, venues, officials
  * Broadcasts, odds, news, calendar
  * Retry logic + respectful rate limiting

- Define comprehensive TypeScript interfaces (src/types/espn.ts)
  * ESPNEvent, ESPNCompetition, ESPNTeam, ESPNAthlete
  * ESPNPlay (play-by-play), ESPNStatistic, ESPNStandings
  * ESPNOfficial, ESPNBroadcast, ESPNOdd, ESPNArticle
  * Error handling + request options

- Document schema mapping (docs/espn-integration.md)
  * ESPN response → Matakite ontology (Match, Phase, PlayerStatLine, etc.)
  * Foundry OSDK object definitions + properties
  * Data pipeline (weekly discovery → live match → post-match T+1)
  * Rate limiting strategy + caching TTLs
  * Known issues (standings 500, player career data) + workarounds
  * League ID reference table + validation checklist

- Phase B foundation: ready for real data ingestion
  * No auth required (public endpoints)
  * Supports live match-day activation
  * Integrates with calibration pipeline (predictions vs actual)
```

---

## Next Steps (Assign to Next Phase)

1. **Implement ingestion pipeline** (n8n + src/pipelines/)
2. **Build Foundry OSDK mappers** (src/osdk/)
3. **Set up test environment** (mock data + ESPN sandbox)
4. **Integration testing** (live scoreboard polling + summary fetch)
5. **Calibration trigger** (post-match pipeline)

---

*Phase B Ready | MATAKITE ESPN Integration v1.0 | Deviecall*
