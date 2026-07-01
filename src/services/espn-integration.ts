/**
 * ESPN Integration Bridge
 * Translates ESPN API responses into Matakite internal model objects.
 * Feeds live data into:
 *  1. The fusion server (via REST /api/espn/* endpoints)
 *  2. Foundry OSDK (via object writes)
 *  3. Dashboard (via WebSocket broadcast state shape)
 *
 * This is the single transformation layer between ESPN's opinionated
 * response shapes and what the rest of the Matakite stack consumes.
 */

import { ESPNClient } from "./espn-client.js";
import type {
  ESPNEvent,
  ESPNScorecardEvent,
  ESPNScoreboard,
  ESPNSummary,
  ESPNPlay,
  ESPNAthlete,
  ESPNTeam,
  ESPNStandings,
  ESPNOfficial,
  ESPNOdd,
  ESPNStatistic,
  ESPNEventStatusType,
} from "../types/espn.js";
import type {
  Match,
  Phase,
  PhaseEventType,
  MatchPhase,
  PlayerStatLine,
  PlayerCareer,
  RefereeProfile,
  FeedEntry,
  MatakiteRecord,
} from "../matakite-ontology.js";

// ────────────────────────────────────────────────────────────────────────
// Dashboard State Shape (what fusion_server broadcasts via WebSocket)
// ────────────────────────────────────────────────────────────────────────

export interface DashboardMatchState {
  id: string;
  home: string;
  homeAbbr: string;
  homeLogo?: string;
  away: string;
  awayAbbr: string;
  awayLogo?: string;
  venue: string;
  kickoff: string;
  minute: number;
  phase: MatchPhase;
  score: { home: number; away: number };
  status: string;
  period: number;
  league: string;
}

export interface DashboardPredictionState {
  win_prob_home: number;
  win_prob_away: number;
  confidence: number;
  brier_season: number;
  hit_rate: number;
  calibration_error: number;
  // Enriched from ESPN odds when available
  odds_home?: number;
  odds_away?: number;
  spread?: number;
}

export interface DashboardBattlegrounds {
  scrum: number;
  lineout: number;
  breakdown: number;
  territory: number;
  aerial: number;
}

export interface DashboardTheCall {
  action: string;
  expected_points: number;
  window_closes: string;
  confidence: number;
}

export interface DashboardStandingsEntry {
  rank: number;
  team: string;
  teamId: string;
  logo?: string;
  played: number;
  wins: number;
  losses: number;
  draws: number;
  points: number;
  pointsFor: number;
  pointsAgainst: number;
  diff: number;
}

export interface DashboardAthleteProfile {
  id: string;
  displayName: string;
  position: string;
  age?: number;
  height?: number;
  weight?: number;
  team?: string;
  teamId?: string;
  jersey?: number;
  carries?: number;
  metresGained?: number;
  tackles?: number;
  passes?: number;
}

export interface DashboardFeedStatus {
  name: string;
  source: string;
  latency: string;
  status: "live" | "cached" | "error" | "stub";
  lastFetched?: string;
  recordCount?: number;
}

export interface DashboardState {
  match: DashboardMatchState;
  prediction: DashboardPredictionState;
  battlegrounds: DashboardBattlegrounds;
  the_call: DashboardTheCall;
  standings?: DashboardStandingsEntry[];
  roster?: DashboardAthleteProfile[];
  feeds: Record<string, DashboardFeedStatus>;
  meta: {
    provenance: string[];
    classification: string;
    version: string;
    espnLeagueId: string;
    lastRefreshed: string;
  };
}

// ────────────────────────────────────────────────────────────────────────
// ESPN Integration Class
// ────────────────────────────────────────────────────────────────────────

export class ESPNIntegration {
  private client: ESPNClient;
  private leagueId: string;

  constructor(leagueId: string, clientConfig = {}) {
    this.client = new ESPNClient(clientConfig);
    this.leagueId = leagueId;
  }

  // ──────────────────────────────────────────────────────────────────
  // Match State → Dashboard
  // ──────────────────────────────────────────────────────────────────

  /**
   * Fetch live scoreboard and return the first/most relevant match
   * as a dashboard-ready match state object.
   */
  async getLiveMatchState(date?: string): Promise<DashboardMatchState | null> {
    try {
      const scoreboard = await this.client.getScoreboard(this.leagueId, date);
      if (!scoreboard.events?.length) return null;

      // Prefer in-progress, else fall back to next scheduled
      const event =
        scoreboard.events.find((e) =>
          e.status?.type?.includes("IN_PROGRESS")
        ) || scoreboard.events[0];

      return this.scoreboardEventToMatchState(event);
    } catch (err) {
      console.error("[ESPN] getLiveMatchState error:", err);
      return null;
    }
  }

  /**
   * Translate a scoreboard event into dashboard match state
   */
  scoreboardEventToMatchState(event: ESPNScorecardEvent): DashboardMatchState {
    const comp = event.competitions?.[0];
    const home = comp?.competitors?.find((c) => c.homeAway === "home");
    const away = comp?.competitors?.find((c) => c.homeAway === "away");

    return {
      id: event.id,
      home: home?.displayName ?? "Home",
      homeAbbr: home?.abbreviation ?? "HOM",
      homeLogo: home?.logo ?? home?.team?.logo,
      away: away?.displayName ?? "Away",
      awayAbbr: away?.abbreviation ?? "AWY",
      awayLogo: away?.logo ?? away?.team?.logo,
      venue: "TBC",                              // Enriched separately
      kickoff: event.date,
      minute: this.clockToMinute(comp?.status?.displayClock),
      phase: this.statusTypeToPhase(comp?.status?.type ?? "", comp?.status?.period ?? 0),
      score: {
        home: Number(home?.score ?? 0),
        away: Number(away?.score ?? 0),
      },
      status: comp?.status?.type ?? "UNKNOWN",
      period: comp?.status?.period ?? 0,
      league: this.leagueId,
    };
  }

  /**
   * Get detailed match state from core event endpoint
   */
  async getMatchState(eventId: string): Promise<DashboardMatchState | null> {
    try {
      const event = await this.client.getEvent(this.leagueId, eventId);
      const comp = event.competitions?.[0];
      const home = comp?.competitors?.find((c) => c.homeAway === "home");
      const away = comp?.competitors?.find((c) => c.homeAway === "away");

      return {
        id: event.id,
        home: home?.displayName ?? "Home",
        homeAbbr: home?.abbreviation ?? "HOM",
        away: away?.displayName ?? "Away",
        awayAbbr: away?.abbreviation ?? "AWY",
        venue: event.venue?.fullName ?? "TBC",
        kickoff: event.date,
        minute: this.clockToMinute(event.status?.displayClock),
        phase: this.statusTypeToPhase(
          event.status?.type?.toString() ?? "",
          event.status?.period ?? 0
        ),
        score: {
          home: Number(home?.score ?? 0),
          away: Number(away?.score ?? 0),
        },
        status: event.status?.type?.toString() ?? "UNKNOWN",
        period: event.status?.period ?? 0,
        league: this.leagueId,
      };
    } catch (err) {
      console.error("[ESPN] getMatchState error:", err);
      return null;
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Standings → Dashboard
  // ──────────────────────────────────────────────────────────────────

  /**
   * Fetch league standings and return dashboard-ready rows.
   * Uses core API (site API returns 500 for rugby union).
   */
  async getStandingsState(): Promise<DashboardStandingsEntry[]> {
    try {
      const standings = await this.client.getStandings(this.leagueId);
      const entries: DashboardStandingsEntry[] = [];
      let rank = 1;

      for (const group of standings.groups ?? []) {
        for (const ts of group.teams ?? []) {
          const stats = this.statsMap(ts.stats ?? []);
          entries.push({
            rank: rank++,
            team: ts.team.displayName,
            teamId: ts.team.id,
            logo: ts.team.logo,
            played: stats["gamesPlayed"] ?? stats["played"] ?? 0,
            wins: stats["wins"] ?? stats["won"] ?? 0,
            losses: stats["losses"] ?? stats["lost"] ?? 0,
            draws: stats["ties"] ?? stats["drawn"] ?? 0,
            points: stats["points"] ?? 0,
            pointsFor: stats["pointsFor"] ?? stats["scored"] ?? 0,
            pointsAgainst: stats["pointsAgainst"] ?? stats["conceded"] ?? 0,
            diff: (stats["pointsFor"] ?? 0) - (stats["pointsAgainst"] ?? 0),
          });
        }
      }

      return entries;
    } catch (err) {
      console.error("[ESPN] getStandingsState error:", err);
      return [];
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Roster / Athlete Profiles → Dashboard Dossier
  // ──────────────────────────────────────────────────────────────────

  /**
   * Fetch team roster and return athlete profiles for dossier display.
   */
  async getTeamRosterState(teamId: string): Promise<DashboardAthleteProfile[]> {
    try {
      const roster = await this.client.getTeamRoster(this.leagueId, teamId);
      return roster.map((a) => this.athleteToProfile(a));
    } catch (err) {
      console.error("[ESPN] getTeamRosterState error:", err);
      return [];
    }
  }

  /**
   * Fetch top performers for a match from summary endpoint
   */
  async getMatchLeaders(eventId: string): Promise<DashboardAthleteProfile[]> {
    try {
      const summary = await this.client.getMatchSummary(this.leagueId, eventId);
      const profiles: DashboardAthleteProfile[] = [];

      for (const comp of summary.competitions ?? []) {
        for (const competitor of comp.competitors ?? []) {
          if (competitor.leaders) {
            for (const leader of competitor.leaders) {
              profiles.push({
                id: String(leader.value),
                displayName: leader.displayName,
                position: competitor.abbreviation,
              });
            }
          }
        }
      }

      return profiles;
    } catch (err) {
      console.error("[ESPN] getMatchLeaders error:", err);
      return [];
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Odds → Prediction State Enrichment
  // ──────────────────────────────────────────────────────────────────

  /**
   * Enrich prediction state with ESPN odds data.
   * Merges with existing model prediction (ESPN odds supplement, not replace).
   */
  async enrichWithOdds(
    eventId: string,
    competitionId: string,
    existing: DashboardPredictionState
  ): Promise<DashboardPredictionState> {
    try {
      const oddsResponse = await this.client.getOdds(
        this.leagueId,
        eventId,
        competitionId
      );

      const first = oddsResponse.items?.[0];
      if (!first) return existing;

      return {
        ...existing,
        odds_home: first.spread?.home?.value,
        odds_away: first.spread?.away?.value,
        spread: first.overUnder,
      };
    } catch {
      // Odds endpoint often returns 404 for rugby — fail silently
      return existing;
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Full Dashboard State Assembly
  // ──────────────────────────────────────────────────────────────────

  /**
   * Build a complete dashboard state snapshot for a specific match.
   * Merges: live score + standings + roster of both teams.
   * Falls back gracefully on any partial failure.
   */
  async buildDashboardState(
    eventId: string,
    competitionId: string,
    existingPrediction: DashboardPredictionState,
    existingBattlegrounds: DashboardBattlegrounds,
    existingCall: DashboardTheCall
  ): Promise<DashboardState> {
    const [matchState, standings] = await Promise.allSettled([
      this.getMatchState(eventId),
      this.getStandingsState(),
    ]);

    const match =
      matchState.status === "fulfilled" && matchState.value
        ? matchState.value
        : this.defaultMatchState();

    const standingsList =
      standings.status === "fulfilled" ? standings.value : [];

    // Try to enrich odds
    const prediction = await this.enrichWithOdds(
      eventId,
      competitionId,
      existingPrediction
    );

    return {
      match,
      prediction,
      battlegrounds: existingBattlegrounds,
      the_call: existingCall,
      standings: standingsList,
      feeds: {
        espn: {
          name: "ESPN Core API",
          source: "espn",
          latency: "live",
          status: "live",
          lastFetched: new Date().toISOString(),
        },
        opta: {
          name: "Opta/Stats Perform",
          source: "opta",
          latency: "live",
          status: "stub",
        },
        gps: {
          name: "GPS/IMU Telemetry",
          source: "own",
          latency: "live",
          status: "stub",
        },
        mirofish: {
          name: "MiroFish Swarm",
          source: "modelled",
          latency: "event-based",
          status: "stub",
        },
      },
      meta: {
        provenance: ["OWN", "OBSERVED", "MODELLED"],
        classification: "INTERNAL",
        version: "v0.2",
        espnLeagueId: this.leagueId,
        lastRefreshed: new Date().toISOString(),
      },
    };
  }

  // ──────────────────────────────────────────────────────────────────
  // Matakite Ontology Transforms
  // ──────────────────────────────────────────────────────────────────

  /**
   * Map ESPN scoreboard event → Matakite Match
   */
  espnEventToMatch(
    event: ESPNScorecardEvent,
    competition: string
  ): Omit<Match, keyof MatakiteRecord> {
    const comp = event.competitions?.[0];
    const home = comp?.competitors?.find((c) => c.homeAway === "home");
    const away = comp?.competitors?.find((c) => c.homeAway === "away");

    return {
      opponent: away?.displayName ?? "Unknown",
      venue: "TBC",
      kickoff: event.date,
      competition,
      phase: this.statusTypeToPhase(
        comp?.status?.type ?? "",
        comp?.status?.period ?? 0
      ),
      score: {
        home: Number(home?.score ?? 0),
        away: Number(away?.score ?? 0),
      },
    };
  }

  /**
   * Map ESPN play → Matakite Phase
   */
  espnPlayToPhase(
    play: ESPNPlay,
    matchId: string
  ): Omit<Phase, keyof MatakiteRecord> {
    const clockSecs = play.clock?.value ?? 0;
    const isHome = play.homeTeamEvent ?? false;

    return {
      matchId,
      minute: Math.floor(clockSecs / 60),
      second: clockSecs % 60,
      eventType: this.playTypeToPhaseEvent(play.type?.text ?? ""),
      team: isHome ? "home" : "away",
      outcome: play.shortText ?? play.text,
      notes: play.scoringPlay ? "Scoring play" : undefined,
    };
  }

  /**
   * Map ESPN athlete → Matakite PlayerCareer stub
   * (Caps/career stats require multi-season aggregation)
   */
  espnAthleteToCareer(
    athlete: ESPNAthlete
  ): Omit<PlayerCareer, keyof MatakiteRecord> {
    return {
      playerId: athlete.id,
      name: athlete.displayName,
      position: athlete.position,
      debut: "unknown",          // Not available from ESPN directly
      caps: 0,                   // Aggregate from matches
      careerTries: 0,            // Aggregate from plays
      careerPoints: 0,
      clubs: athlete.team ? [athlete.team.displayName] : [],
    };
  }

  /**
   * Map ESPN official → Matakite RefereeProfile stub
   * (Penalty/card rates built from historical match data)
   */
  espnOfficialToRefProfile(
    official: ESPNOfficial
  ): Omit<RefereeProfile, keyof MatakiteRecord> {
    return {
      refId: official.id,
      name: official.displayName,
      breakdownPenaltyRate: 0,   // Computed from historical matches
      scrumPenaltyRate: 0,
      maulCallTendency: "neutral",
      cardTendency: "balanced",
    };
  }

  // ──────────────────────────────────────────────────────────────────
  // Helpers
  // ──────────────────────────────────────────────────────────────────

  private statusTypeToPhase(status: string, period: number): MatchPhase {
    if (status.includes("FINAL")) return "full-time";
    if (status.includes("END_PERIOD") || status.includes("HALFTIME"))
      return "half-time";
    if (status.includes("IN_PROGRESS")) {
      return period <= 1 ? "first-half" : "second-half";
    }
    return "pre-match";
  }

  private clockToMinute(clock?: string): number {
    if (!clock) return 0;
    const parts = clock.split(":");
    if (parts.length === 2) return parseInt(parts[0], 10);
    return 0;
  }

  private playTypeToPhaseEvent(typeText: string): PhaseEventType {
    const t = typeText.toLowerCase();
    if (t.includes("try")) return "try";
    if (t.includes("penalty")) return "penalty";
    if (t.includes("conversion")) return "conversion";
    if (t.includes("scrum")) return "scrum";
    if (t.includes("lineout")) return "lineout";
    if (t.includes("maul")) return "maul";
    if (t.includes("ruck")) return "ruck";
    if (t.includes("breakdown")) return "breakdown";
    if (t.includes("substitut") || t.includes("replace")) return "substitution";
    if (t.includes("kick")) return "kick";
    return "kick"; // default
  }

  private statsMap(stats: ESPNStatistic[]): Record<string, number> {
    const out: Record<string, number> = {};
    for (const s of stats) {
      const key = s.name ?? s.displayName?.toLowerCase().replace(/\s/g, "");
      if (key) out[key] = s.value ?? parseFloat(s.displayValue ?? "0") ?? 0;
    }
    return out;
  }

  private athleteToProfile(a: ESPNAthlete): DashboardAthleteProfile {
    const stats = this.statsMap(a.statistics ?? []);
    return {
      id: a.id,
      displayName: a.displayName,
      position: a.position,
      age: a.age,
      height: a.height,
      weight: a.weight,
      team: a.team?.displayName,
      teamId: a.team?.id,
      jersey: a.jersey,
      carries: stats["carries"],
      metresGained: stats["metres"] ?? stats["meters"],
      tackles: stats["tackles"],
      passes: stats["passes"],
    };
  }

  private defaultMatchState(): DashboardMatchState {
    return {
      id: "unknown",
      home: "Home Team",
      homeAbbr: "HOM",
      away: "Away Team",
      awayAbbr: "AWY",
      venue: "TBC",
      kickoff: new Date().toISOString(),
      minute: 0,
      phase: "pre-match",
      score: { home: 0, away: 0 },
      status: "STATUS_SCHEDULED",
      period: 0,
      league: this.leagueId,
    };
  }
}

export default ESPNIntegration;
