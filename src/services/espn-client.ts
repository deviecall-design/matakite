/**
 * ESPNClient
 * Thin wrapper for ESPN rugby API endpoints
 * Supports v2/v3 core APIs and site.api.espn.com public endpoints
 *
 * No auth required — all endpoints public.
 * Rate limiting: respectful (~1 req/sec recommended to avoid throttling)
 */

import type {
  ESPNEvent,
  ESPNScoreboard,
  ESPNSummary,
  ESPNTeam,
  ESPNAthlete,
  ESPNStandings,
  ESPNRanking,
  ESPNVenue,
  ESPNLeague,
  ESPNRequestOptions,
  ESPNListResponse,
  ESPNPlay,
  ESPNCompetition,
  ESPNOfficial,
  ESPNBroadcast,
  ESPNOdd,
  ESPNArticle,
} from "../types/espn.js";

// ────────────────────────────────────────────────────────────────────────
// Configuration
// ────────────────────────────────────────────────────────────────────────

export interface ESPNClientConfig {
  baseUrl?: string;
  siteApiUrl?: string;
  timeout?: number;
  retryAttempts?: number;
  retryDelayMs?: number;
}

// ────────────────────────────────────────────────────────────────────────
// ESPNClient Class
// ────────────────────────────────────────────────────────────────────────

export class ESPNClient {
  private baseUrl: string;
  private siteApiUrl: string;
  private timeout: number;
  private retryAttempts: number;
  private retryDelayMs: number;

  constructor(config: ESPNClientConfig = {}) {
    this.baseUrl = config.baseUrl || "https://sports.core.api.espn.com";
    this.siteApiUrl = config.siteApiUrl || "https://site.api.espn.com";
    this.timeout = config.timeout || 10000;
    this.retryAttempts = config.retryAttempts || 3;
    this.retryDelayMs = config.retryDelayMs || 500;
  }

  // ────────────────────────────────────────────────────────────────────
  // Internal Fetch with Retry & Error Handling
  // ────────────────────────────────────────────────────────────────────

  private async fetch<T>(
    url: string,
    options?: RequestInit & { timeout?: number }
  ): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(
          () => controller.abort(),
          options?.timeout || this.timeout
        );

        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          const error = await response.text();
          throw new Error(
            `ESPN API error ${response.status}: ${error || response.statusText}`
          );
        }

        return (await response.json()) as T;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        // Don't retry on 4xx errors (client fault)
        if (error instanceof Error && error.message.includes("4")) {
          throw lastError;
        }

        // Backoff before retry
        if (attempt < this.retryAttempts - 1) {
          await this.delay(this.retryDelayMs * (attempt + 1));
        }
      }
    }

    throw lastError || new Error("ESPN API request failed after retries");
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private buildQueryString(params: ESPNRequestOptions): string {
    if (!params || Object.keys(params).length === 0) return "";

    const filtered = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => {
        if (Array.isArray(v)) {
          return v.map((item) => `${encodeURIComponent(k)}=${encodeURIComponent(item)}`).join("&");
        }
        return `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`;
      })
      .join("&");

    return filtered ? `?${filtered}` : "";
  }

  // ────────────────────────────────────────────────────────────────────
  // Leagues
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get all rugby leagues (discover league IDs)
   * Core API v2: GET /v2/sports/rugby/leagues
   */
  async getLeagues(): Promise<ESPNLeague[]> {
    const url = `${this.baseUrl}/v2/sports/rugby/leagues`;
    const response = await this.fetch<{ sports: Array<{ leagues: ESPNLeague[] }> }>(url);
    return response.sports[0]?.leagues || [];
  }

  /**
   * Get a specific league by ID or slug
   */
  async getLeague(leagueId: string): Promise<ESPNLeague> {
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}`;
    return this.fetch<ESPNLeague>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Scoreboard (Site API — user-friendly format)
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get live scoreboard for a league
   * Site API: GET /apis/site/v2/sports/rugby/{league}/scoreboard
   *
   * @param leagueId - Numeric league ID (e.g., 267979 for Premiership)
   * @param date - Optional: YYYYMMDD format to filter by date
   */
  async getScoreboard(leagueId: string, date?: string): Promise<ESPNScoreboard> {
    let url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/scoreboard`;
    if (date) {
      url += `?dates=${date}`;
    }
    return this.fetch<ESPNScoreboard>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Events / Games
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get events for a league and season
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events
   */
  async getEvents(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNEvent>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events${qs}`;
    return this.fetch<ESPNListResponse<ESPNEvent>>(url);
  }

  /**
   * Get a specific event/match
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{eventId}
   */
  async getEvent(leagueId: string, eventId: string): Promise<ESPNEvent> {
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}`;
    return this.fetch<ESPNEvent>(url);
  }

  /**
   * Get match summary with boxscore
   * Site API: GET /apis/site/v2/sports/rugby/{league}/summary?event={eventId}
   */
  async getMatchSummary(leagueId: string, eventId: string): Promise<ESPNSummary> {
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/summary?event=${eventId}`;
    return this.fetch<ESPNSummary>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Competitions (within an event)
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get a specific competition within an event
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{event}/competitions/{competition}
   */
  async getCompetition(
    leagueId: string,
    eventId: string,
    competitionId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNCompetition> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}/competitions/${competitionId}${qs}`;
    return this.fetch<ESPNCompetition>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Plays / Actions
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get plays/actions from a competition
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{event}/competitions/{competition}/plays
   */
  async getPlays(
    leagueId: string,
    eventId: string,
    competitionId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNPlay>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}/competitions/${competitionId}/plays${qs}`;
    return this.fetch<ESPNListResponse<ESPNPlay>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Teams
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get all teams for a league
   * Site API: GET /apis/site/v2/sports/rugby/{league}/teams
   */
  async getTeams(leagueId: string, options?: ESPNRequestOptions): Promise<ESPNTeam[]> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/teams${qs}`;
    const response = await this.fetch<{ teams: ESPNTeam[] }>(url);
    return response.teams || [];
  }

  /**
   * Get a specific team
   * Site API: GET /apis/site/v2/sports/rugby/{league}/teams/{teamId}
   */
  async getTeam(leagueId: string, teamId: string): Promise<ESPNTeam> {
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/teams/${teamId}`;
    return this.fetch<ESPNTeam>(url);
  }

  /**
   * Get team roster
   * Site API: GET /apis/site/v2/sports/rugby/{league}/teams/{teamId}/roster
   */
  async getTeamRoster(leagueId: string, teamId: string): Promise<ESPNAthlete[]> {
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/teams/${teamId}/roster`;
    const response = await this.fetch<{ roster: ESPNAthlete[] }>(url);
    return response.roster || [];
  }

  /**
   * Get team schedule
   * Site API: GET /apis/site/v2/sports/rugby/{league}/teams/{teamId}/schedule
   */
  async getTeamSchedule(leagueId: string, teamId: string): Promise<ESPNEvent[]> {
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/teams/${teamId}/schedule`;
    const response = await this.fetch<{ schedule: ESPNEvent[] }>(url);
    return response.schedule || [];
  }

  // ────────────────────────────────────────────────────────────────────
  // Athletes / Players
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get all athletes across all seasons
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/athletes
   */
  async getAthletes(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNAthlete>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/athletes${qs}`;
    return this.fetch<ESPNListResponse<ESPNAthlete>>(url);
  }

  /**
   * Get athletes for a specific season
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/seasons/{season}/athletes
   */
  async getSeasonAthletes(
    leagueId: string,
    season: number,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNAthlete>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/seasons/${season}/athletes${qs}`;
    return this.fetch<ESPNListResponse<ESPNAthlete>>(url);
  }

  /**
   * Get a specific athlete
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/athletes/{athleteId}
   */
  async getAthlete(leagueId: string, athleteId: string): Promise<ESPNAthlete> {
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/athletes/${athleteId}`;
    return this.fetch<ESPNAthlete>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Standings / Rankings
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get standings for a league/season
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/standings
   *
   * Note: Site API standings returns 500 for rugby union. Use core API instead.
   */
  async getStandings(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNStandings> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/standings${qs}`;
    return this.fetch<ESPNStandings>(url);
  }

  /**
   * Get rankings for a league
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/rankings
   */
  async getRankings(leagueId: string, options?: ESPNRequestOptions): Promise<ESPNRanking[]> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/rankings${qs}`;
    const response = await this.fetch<{ rankings: ESPNRanking[] }>(url);
    return response.rankings || [];
  }

  // ────────────────────────────────────────────────────────────────────
  // Venues
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get venues for a league
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/venues
   */
  async getVenues(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNVenue>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/venues${qs}`;
    return this.fetch<ESPNListResponse<ESPNVenue>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Officials / Referees
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get officials for a competition
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{event}/competitions/{competition}/officials
   */
  async getOfficials(
    leagueId: string,
    eventId: string,
    competitionId: string
  ): Promise<ESPNListResponse<ESPNOfficial>> {
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}/competitions/${competitionId}/officials`;
    return this.fetch<ESPNListResponse<ESPNOfficial>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Broadcasts
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get broadcast information for a competition
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{event}/competitions/{competition}/broadcasts
   */
  async getBroadcasts(
    leagueId: string,
    eventId: string,
    competitionId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNBroadcast>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}/competitions/${competitionId}/broadcasts${qs}`;
    return this.fetch<ESPNListResponse<ESPNBroadcast>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Odds & Betting
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get odds for a competition
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/events/{event}/competitions/{competition}/odds
   */
  async getOdds(
    leagueId: string,
    eventId: string,
    competitionId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<ESPNOdd>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/events/${eventId}/competitions/${competitionId}/odds${qs}`;
    return this.fetch<ESPNListResponse<ESPNOdd>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // News
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get news for a league
   * Site API: GET /apis/site/v2/sports/rugby/{league}/news
   */
  async getNews(leagueId: string, options?: ESPNRequestOptions): Promise<ESPNArticle[]> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.siteApiUrl}/apis/site/v2/sports/rugby/${leagueId}/news${qs}`;
    const response = await this.fetch<{ articles: ESPNArticle[] }>(url);
    return response.articles || [];
  }

  // ────────────────────────────────────────────────────────────────────
  // Seasons & Calendar
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get seasons for a league
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/seasons
   */
  async getSeasons(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<any>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/seasons${qs}`;
    return this.fetch<ESPNListResponse<any>>(url);
  }

  /**
   * Get calendar for a league
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/calendar
   */
  async getCalendar(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<any>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/calendar${qs}`;
    return this.fetch<ESPNListResponse<any>>(url);
  }

  // ────────────────────────────────────────────────────────────────────
  // Other (Venues, Positions, Countries, etc.)
  // ────────────────────────────────────────────────────────────────────

  /**
   * Get positions available in rugby
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/positions
   */
  async getPositions(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<any>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/positions${qs}`;
    return this.fetch<ESPNListResponse<any>>(url);
  }

  /**
   * Get countries for a league
   * Core API v2: GET /v2/sports/rugby/leagues/{league}/countries
   */
  async getCountries(
    leagueId: string,
    options?: ESPNRequestOptions
  ): Promise<ESPNListResponse<any>> {
    const qs = this.buildQueryString(options || {});
    const url = `${this.baseUrl}/v2/sports/rugby/leagues/${leagueId}/countries${qs}`;
    return this.fetch<ESPNListResponse<any>>(url);
  }
}

export default ESPNClient;
