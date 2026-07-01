# ESPN Integration for MATAKITE
## Schema Mapping & Foundry OSDK Integration

**Last Updated:** 2026-07-01  
**Phase:** B (Real Data Integration)

---

## Overview

This document specifies the schema mapping from ESPN rugby API responses to Matakite's internal data model, and defines integration points for Foundry OSDK persistence.

### Key Points

- **No authentication required** — all ESPN rugby endpoints are public
- **Two API tiers:** Core APIs (v2/v3 at `sports.core.api.espn.com`) + Site APIs (user-friendly at `site.api.espn.com`)
- **Rate limiting:** ESPN does not publish official limits; recommended: 1 req/sec to be respectful
- **Standings caveat:** Rugby Union standings return 500 from site.api; use core API instead
- **League IDs:** Rugby uses numeric IDs, not slugs (e.g., `267979` for Gallagher Premiership)

---

## API Endpoints Reference

### Discovery

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /v2/sports/rugby/leagues` | Discover available league IDs | `{ sports: [{ leagues: [] }] }` |
| `GET /v2/sports/rugby/leagues/{id}` | League metadata | `ESPNLeague` |

### Live Data (Site API)

| Endpoint | Purpose | Matakite Use |
|----------|---------|--------------|
| `GET /apis/site/v2/sports/rugby/{league}/scoreboard` | Live scores, schedules | Real-time Match state |
| `GET /apis/site/v2/sports/rugby/{league}/scoreboard?dates=YYYYMMDD` | Scores for specific date | Historical Match lookup |
| `GET /apis/site/v2/sports/rugby/{league}/summary?event={id}` | Full boxscore + stats | Match post-mortem, Calibration |
| `GET /apis/site/v2/sports/rugby/{league}/teams` | All league teams | Team roster, Dossier |
| `GET /apis/site/v2/sports/rugby/{league}/teams/{id}` | Single team metadata | Team profile |
| `GET /apis/site/v2/sports/rugby/{league}/teams/{id}/roster` | Team players | PlayerStatLine, Dossier |
| `GET /apis/site/v2/sports/rugby/{league}/teams/{id}/schedule` | Team matches (season) | Schedule view |
| `GET /apis/site/v2/sports/rugby/{league}/news` | Latest news feed | NewsIngestion → Dossier |

### Core Data (v2 Core API)

| Endpoint | Purpose | Matakite Use |
|----------|---------|--------------|
| `GET /v2/sports/rugby/leagues/{league}/events` | All events in season | Event index, Calendar |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}` | Event details | Match metadata, Prediction |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}/competitions/{id}` | Detailed competition | Match state during game |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}/competitions/{id}/plays` | Play-by-play | Phase events, In-match prediction |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}/competitions/{id}/broadcasts` | Broadcast info | Match broadcast links |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}/competitions/{id}/odds` | Betting odds | Odds monitor (future) |
| `GET /v2/sports/rugby/leagues/{league}/events/{id}/competitions/{id}/officials` | Referee data | RefereeProfile |
| `GET /v2/sports/rugby/leagues/{league}/athletes` | All athletes | Athlete master index |
| `GET /v2/sports/rugby/leagues/{league}/athletes/{id}` | Athlete detail | PlayerCareer |
| `GET /v2/sports/rugby/leagues/{league}/seasons/{year}/athletes` | Season athletes | Seasonal rosters |
| `GET /v2/sports/rugby/leagues/{league}/standings` | League standings | Standings → Matakite |
| `GET /v2/sports/rugby/leagues/{league}/rankings` | Rankings (international) | International rankings |
| `GET /v2/sports/rugby/leagues/{league}/venues` | Stadium list | Venue metadata |
| `GET /v2/sports/rugby/leagues/{league}/positions` | Position master | Position reference |
| `GET /v2/sports/rugby/leagues/{league}/countries` | Country list | Country reference |
| `GET /v2/sports/rugby/leagues/{league}/calendar` | Calendar entries | Event calendar |
| `GET /v2/sports/rugby/leagues/{league}/seasons` | Season list | Season reference |

---

## Schema Mapping

### Match (Event) → ESPNEvent + ESPNScorecardEvent

**ESPN Response Structure:**
```json
{
  "id": "36024361",
  "uid": "s:rugby:e:36024361",
  "date": "2026-08-15T19:00Z",
  "name": "New Zealand vs South Africa",
  "shortName": "NZ v RSA",
  "status": {
    "type": "STATUS_FINAL",
    "displayClock": "80:00",
    "period": 2
  },
  "venue": {
    "id": "52",
    "fullName": "Eden Park",
    "city": "Auckland",
    "capacity": 50000
  },
  "competitions": [
    {
      "id": "36024361001",
      "date": "2026-08-15T19:00Z",
      "status": { "type": "STATUS_FINAL", "period": 2 },
      "competitors": [
        {
          "id": "25",
          "homeAway": "home",
          "displayName": "New Zealand",
          "score": 42,
          "team": { "id": "25", "displayName": "All Blacks", "logo": "..." }
        },
        {
          "id": "2657",
          "homeAway": "away",
          "displayName": "South Africa",
          "score": 37,
          "team": { "id": "2657", "displayName": "Springboks", "logo": "..." }
        }
      ]
    }
  ]
}
```

**Matakite Match Object:**
```typescript
interface Match extends MatakiteRecord {
  opponent: string;           // competitors[1].displayName
  venue: string;              // venue.fullName
  venueAltitudeM?: number;    // computed from venue lat/lon
  kickoff: string;            // event.date (ISO-8601)
  competition: string;        // "Rugby Championship", "Six Nations", etc.
  phase: MatchPhase;          // derived from status.type
  score?: { home: number; away: number }; // competitors[].score
}
```

**Mapping Logic:**
- `status.type` → `MatchPhase`:
  - `STATUS_SCHEDULED` → `"pre-match"`
  - `STATUS_IN_PROGRESS` → `"first-half"` or `"second-half"` (check `period`)
  - `STATUS_END_PERIOD` → `"half-time"`
  - `STATUS_FINAL` → `"full-time"`

---

### Phase (Play-by-Play Event) → ESPNPlay

**ESPN Play Response:**
```json
{
  "id": "3602436101001",
  "sequenceNumber": 1,
  "period": { "number": 1 },
  "clock": { "displayValue": "00:00", "value": 0 },
  "type": { "id": "1", "text": "Kickoff", "displayName": "Kickoff" },
  "text": "New Zealand kickoff",
  "homeTeamEvent": true,
  "scoringPlay": false
}
```

**Matakite Phase Object:**
```typescript
interface Phase extends MatakiteRecord {
  matchId: string;            // parent match ID
  minute: number;             // clock.value / 60
  second?: number;            // clock.value % 60
  eventType: PhaseEventType;  // derived from play.type
  team: "home" | "away";      // homeTeamEvent ? "home" : "away"
  fieldPosition?: string;     // parsed from text (future: AI extraction)
  outcome?: string;           // play.shortText or summary
  notes?: string;
}
```

**EventType Mapping (ESPN play.type → PhaseEventType):**
| ESPN Type | Matakite PhaseEventType |
|-----------|------------------------|
| Kickoff | `"kick"` |
| Try | `"try"` |
| Penalty Goal | `"penalty"` |
| Conversion | `"conversion"` |
| Substitution | `"substitution"` |
| Scrum | `"scrum"` |
| Lineout | `"lineout"` |
| Maul | `"maul"` |
| Ruck | `"ruck"` |
| Breakdown | `"breakdown"` |
| (others) | parse from text or `"unknown"` |

---

### PlayerStatLine → ESPNCompetitor + ESPNPlay

**ESPN Competitor Statistics:**
```json
{
  "id": "2639",
  "displayName": "Beauden Barrett",
  "position": "Fly-half",
  "statistics": [
    { "name": "carries", "value": 8 },
    { "name": "metres", "value": 42 },
    { "name": "tackles", "value": 5 },
    { "name": "passes", "value": 31 }
  ]
}
```

**Matakite PlayerStatLine:**
```typescript
interface PlayerStatLine extends MatakiteRecord {
  playerId: string;           // athlete.id
  matchId: string;
  position: string;           // athlete.position
  minutes: number;            // derived from plays (entry/exit times)
  carries: number;
  metresGained: number;
  tackles: number;
  tacklesWon: number;         // subset of tackles
  rucksWon: number;
  passes: number;
  kicksAttempted: number;
  kicksCompleted: number;
  turnoversWon: number;
  errors: number;
}
```

**Ingestion Logic:**
1. Parse boxscore from `/summary?event={id}` endpoint
2. Extract player list from boxscore
3. Map ESPN statistic names → Matakite fields
4. Count minute entry/exit via play-by-play substitution events
5. Persist to Foundry OSDK as `playerStatLine` objects with `sourceRef: "espn"` and `provenance: "OBSERVED"`

---

### Team → ESPNTeam

**ESPN Team Response:**
```json
{
  "id": "25",
  "displayName": "New Zealand",
  "shortDisplayName": "NZ",
  "abbreviation": "NZ",
  "logo": "https://a.espncdn.com/...",
  "venue": { "id": "52", "fullName": "Eden Park" }
}
```

**Matakite Usage:**
- National teams: directly referenced in Match.opponent
- Club teams: used for rosters via `/teams/{id}/roster`
- Logo URL: cached in Foundry for Dossier generation

---

### Athlete → ESPNAthlete + ESPNAthleteCompact

**ESPN Athlete (Detail):**
```json
{
  "id": "2639",
  "displayName": "Beauden Barrett",
  "firstName": "Beauden",
  "lastName": "Barrett",
  "position": "Fly-half",
  "dateOfBirth": "1991-05-09",
  "height": 184,
  "weight": 92,
  "active": true,
  "links": [
    { "text": "Player Home", "href": "https://..." }
  ]
}
```

**Matakite PlayerCareer:**
```typescript
interface PlayerCareer extends MatakiteRecord {
  playerId: string;           // athlete.id
  name: string;               // athlete.displayName
  position: string;           // athlete.position
  debut: string;              // extracted from plays or external source
  caps: number;               // aggregated from matches
  careerTries: number;        // aggregated from plays
  careerPoints?: number;
  clubs?: string[];           // parsed from career history
  wikiDataRef?: string;       // future: enrich via wikidata
}
```

**Ingestion:**
1. Fetch `/athletes/{id}` for full detail
2. Map ESPN response → PlayerCareer
3. Link to Team via roster endpoint
4. Aggregate stats from `/summary` endpoint across seasons (future)

---

### Standings → ESPNStandings

**ESPN Standings Response:**
```json
{
  "season": 2026,
  "groups": [
    {
      "name": "Pool A",
      "displayName": "Pool A",
      "teams": [
        {
          "team": { "id": "25", "displayName": "New Zealand" },
          "stats": [
            { "name": "wins", "value": 3 },
            { "name": "losses", "value": 0 },
            { "name": "points", "value": 15 }
          ]
        }
      ]
    }
  ]
}
```

**Matakite:** Not currently stored; used for real-time display in dashboard.  
**Future:** Persist as immutable snapshots for trend analysis.

---

### RefereeProfile → ESPNOfficial

**ESPN Official Response:**
```json
{
  "id": "2891",
  "displayName": "Nigel Owens",
  "position": { "id": "1", "displayName": "Referee" }
}
```

**Matakite RefereeProfile:**
```typescript
interface RefereeProfile extends MatakiteRecord {
  refId: string;              // official.id
  name: string;               // official.displayName
  breakdownPenaltyRate: number;   // derived from historical matches
  scrumPenaltyRate: number;
  maulCallTendency: "conservative" | "neutral" | "permissive";
  cardTendency: "strict" | "balanced" | "lenient";
  notes?: string;
}
```

**Ingestion:**
1. Store ESPN official.id in initial load
2. Aggregate penalty + card rates from historical matches (phase-level data + plays)
3. Update RefereeProfile model quarterly
4. Link to Match via competition.officials[0]

---

## Foundry OSDK Integration Points

### Object Types

Define these as Foundry OSDK Objects:

| Object | Namespace | Primary Key | Synced From | Frequency |
|--------|-----------|-------------|-------------|-----------|
| `rugbyMatch` | `matakite.rugby` | `espnEventId` | `/summary?event={id}` | Event-based |
| `rugbyTeam` | `matakite.rugby` | `espnTeamId` | `/teams/{id}` | Weekly |
| `rugbyAthlete` | `matakite.rugby` | `espnAthleteId` | `/athletes/{id}` | Weekly |
| `playerStatLine` | `matakite.stats` | `{matchId}-{athleteId}` | `/summary?event={id}` | Post-match T+1 |
| `refereeProfile` | `matakite.rugby` | `espnRefId` | `/events/{}/competitions/{}/officials` | Quarterly |
| `matchPhase` | `matakite.match-state` | `{matchId}-{sequenceNumber}` | `/plays` (real-time) | Live |

### Properties

**rugbyMatch:**
```
espnEventId: String (PK)
espnLeagueId: String
homeTeam: Link<rugbyTeam>
awayTeam: Link<rugbyTeam>
venue: String
kickoff: DateTime
competitionName: String
phase: Enum(pre-match, first-half, half-time, second-half, full-time)
homeScore: Int
awayScore: Int
homeTeamScorers: Array<Link<rugbyAthlete>>
awayTeamScorers: Array<Link<rugbyAthlete>>
referee: Link<refereeProfile>
broadcasts: Array<String>
odds: Map<String, Decimal>
sourceRef: String = "espn"
provenance: Enum(OWN, OBSERVED, MODELLED) = OBSERVED
classification: Enum(PROTECTED, INTERNAL, OPEN) = OPEN
createdAt: DateTime
updatedAt: DateTime
```

**playerStatLine:**
```
id: String (PK) = "{matchId}-{athleteId}"
match: Link<rugbyMatch>
athlete: Link<rugbyAthlete>
position: String
minutes: Int
carries: Int
metresGained: Int
tackles: Int
tacklesWon: Int
rucksWon: Int
passes: Int
kicksAttempted: Int
kicksCompleted: Int
turnoversWon: Int
errors: Int
sourceRef: String = "espn"
provenance: Enum = OBSERVED
```

**rugbyAthlete:**
```
espnAthleteId: String (PK)
displayName: String
position: String
dateOfBirth: Date
height: Int
weight: Int
currentTeam: Link<rugbyTeam>
careerMatches: Int
careerTries: Int
wikiDataId: String (future)
sourceRef: String = "espn"
lastUpdated: DateTime
```

### Data Pipeline (Phase B Ingestion)

**Event Cycle:**

```
1. Schedule Discovery (Weekly)
   POST /v2/sports/rugby/leagues/{league}/events
   → Extract {eventId} + {competitionId}
   → Queue for ingest

2. Pre-Match (T-2 hours)
   GET /apis/site/v2/sports/rugby/{league}/scoreboard
   → Update Match phase to "pre-match"
   → Snapshot Team rosters if not cached
   → Enrich RefereeProfile

3. Live Match (T0 to T+80 min)
   GET /v2/sports/rugby/leagues/{league}/events/{eventId}/competitions/{competitionId}/plays
   → Every 10 seconds (respect rate limits)
   → Create matchPhase objects per play
   → Update Match score in real-time

4. Post-Match (T+1 hour)
   GET /apis/site/v2/sports/rugby/{league}/summary?event={eventId}
   → Fetch complete boxscore
   → Create playerStatLine objects
   → Trigger Calibration pipeline (match predictions vs actual)
   → Enrich RefereeProfile with actual penalty/card rates
```

---

## Rate Limiting & Caching Strategy

### Recommended Limits

- **Scoreboard:** 1 call per 10 seconds (live)
- **Summary:** 1 call per match (post-match)
- **Plays:** 1 call per 10 seconds during match (10× per match per season)
- **Teams/Athletes:** 1 call per league per week
- **Standings:** 1 call per day

### Caching

| Endpoint | TTL | Cache Key |
|----------|-----|-----------|
| `/leagues` | 1 week | `espn:leagues` |
| `/teams` | 1 day | `espn:teams:{leagueId}` |
| `/athletes` | 1 day | `espn:athletes:{leagueId}:{season}` |
| `/standings` | 6 hours | `espn:standings:{leagueId}:{season}` |
| `/scoreboard` | 30 seconds | `espn:scoreboard:{leagueId}:{date}` |
| `/summary` | permanent | `espn:summary:{eventId}` |
| `/positions` | 1 year | `espn:positions:{leagueId}` |

---

## Known Issues & Workarounds

### 1. Rugby Union Standings → 500 Error (Site API)

**Problem:**
```
GET /apis/site/v2/sports/rugby/{league}/standings
→ 500 Internal Server Error
```

**Workaround:**
Use core API instead:
```
GET /v2/sports/rugby/leagues/{league}/standings
```

**Status:** ESPN issue (documented in docs/api-reference)

### 2. Limited Player Career Data

**Problem:** ESPN core API does not expose career-level stats (caps, career tries, etc.). These must be:
- Aggregated from individual `/summary` endpoints across seasons
- Or sourced from external feeds (Opta, wikidata)

**Workaround:**
1. Cache `/summary` results post-match
2. Aggregate in async batch job (post-season)
3. Enrich with wikidata where available (CC0 licensed)

### 3. Play-by-Play Attribution

**Problem:** ESPN play events do not always include athlete ID for try-scorers.

**Solution:**
Parse play.text and play.athletesInvolved to link scorers.

---

## Testing & Validation

### League IDs (Common Rugby Competitions)

| League | ID | Endpoint |
|--------|----|---------| 
| Rugby World Cup 2023 | `164205` | `/v2/sports/rugby/leagues/164205` |
| Six Nations | `180659` | `/v2/sports/rugby/leagues/180659` |
| Gallagher Premiership | `267979` | `/v2/sports/rugby/leagues/267979` |
| Top 14 | `268247` | `/v2/sports/rugby/leagues/268247` |
| Super Rugby Pacific | `242041` | `/v2/sports/rugby/leagues/242041` |
| Major League Rugby | `289262` | `/v2/sports/rugby/leagues/289262` |

### Validation Checklist

- [ ] Scoreboard returns live scores without 500 errors
- [ ] Summary endpoint includes play-by-play + boxscore
- [ ] Athlete IDs resolve across seasons
- [ ] Standings endpoint (core API) returns valid JSON
- [ ] Rate limiting respected (monitor response headers for rate limit info)
- [ ] Timestamps are ISO-8601 compliant
- [ ] Team/venue IDs persist across requests

---

## Future Enhancements (Phase C+)

1. **Predictive Enrichment:** Model RefereeProfile from historical data (not ESPN)
2. **Player Career Aggregation:** Fetch multi-season stats, compute career totals
3. **Venue Enrichment:** Geocode venue → altitude for altitude model factors
4. **Streaming:** WebSocket subscription to live plays (not ESPN native; requires wrapper)
5. **Odds Monitoring:** Track opening/closing lines for prediction calibration
6. **News Sentiment:** Ingest news feed → extract team injury/form signals

---

## References

- ESPN API Docs: `docs/api-reference/docs/sports/rugby.md`
- Matakite Ontology: `src/matakite-ontology.ts`
- ESPNClient: `src/services/espn-client.ts`
- Foundry OSDK docs: https://www.palantir.com/docs/foundry/

---

*MATAKITE ESPN Integration v1.0 | Operation Kāhu | Deviecall*
