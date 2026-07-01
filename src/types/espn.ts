/**
 * ESPN API Type Definitions
 * TypeScript interfaces for ESPN rugby data from v2 and v3 cores + site.api endpoints
 * Maps ESPN response shapes to Matakite internal model
 */

// ────────────────────────────────────────────────────────────────────────
// ESPN Response Envelope
// ────────────────────────────────────────────────────────────────────────

export interface ESPNListResponse<T> {
  pageIndex: number;
  pageSize: number;
  pageCount: number;
  count: number;
  items: T[];
}

export interface ESPNPaginatedResponse<T> {
  page: number;
  pageSize: number;
  pageCount: number;
  count: number;
  items: T[];
}

// ────────────────────────────────────────────────────────────────────────
// League & Season Data
// ────────────────────────────────────────────────────────────────────────

export interface ESPNLeague {
  id: string;
  uid: string;
  name: string;
  abbreviation: string;
  shortName: string;
  slug: string;
  isTournament: boolean;
  links?: ESPNLink[];
}

export interface ESPNSeason {
  year: number;
  startDate: string;      // ISO-8601
  endDate: string;        // ISO-8601
  displayName: string;
  slug: string;
}

export interface ESPNCalendar {
  label: string;
  value: number;
  entryId: string;
  startDate: string;
  endDate: string;
}

// ────────────────────────────────────────────────────────────────────────
// Event / Match
// ────────────────────────────────────────────────────────────────────────

export interface ESPNEvent {
  id: string;
  uid: string;
  date: string;           // ISO-8601
  name: string;
  shortName: string;
  status: ESPNEventStatus;
  venue?: ESPNVenue;
  competitions: ESPNCompetition[];
  links?: ESPNLink[];
}

export interface ESPNEventStatus {
  type: ESPNEventStatusType;
  displayClock?: string;
  period?: number;
  clock?: number;
}

export enum ESPNEventStatusType {
  STATUS_SCHEDULED = "STATUS_SCHEDULED",
  STATUS_IN_PROGRESS = "STATUS_IN_PROGRESS",
  STATUS_END_PERIOD = "STATUS_END_PERIOD",
  STATUS_FINAL = "STATUS_FINAL",
  STATUS_CANCELLED = "STATUS_CANCELLED",
  STATUS_DELAYED = "STATUS_DELAYED",
}

export interface ESPNCompetition {
  id: string;
  uid: string;
  date: string;
  displayName: string;
  status: ESPNEventStatus;
  competitors: ESPNCompetitor[];
  broadcasts?: ESPNBroadcast[];
  plays?: ESPNPlay[];
  notes?: Array<{ headline: string; description: string }>;
  odds?: ESPNOdd[];
  officials?: ESPNOfficial[];
}

export interface ESPNCompetitor {
  id: string;
  uid: string;
  type: "team" | "athlete";
  homeAway: "home" | "away";
  displayName: string;
  shortName?: string;
  abbreviation?: string;
  statistics?: ESPNStatistic[];
  score?: number;
  records?: ESPNRecord[];
  leaders?: Array<{ name: string; displayName: string; value: number }>;
  team?: ESPNTeamCompact;
  athlete?: ESPNAthleteCompact;
}

export interface ESPNTeamCompact {
  id: string;
  displayName: string;
  abbreviation: string;
  logo?: string;
  links?: ESPNLink[];
}

export interface ESPNAthleteCompact {
  id: string;
  displayName: string;
  position: string;
  links?: ESPNLink[];
}

export interface ESPNStatistic {
  name: string;
  displayName: string;
  shortDisplayName: string;
  description?: string;
  value?: number;
  displayValue?: string;
  precision?: number;
}

export interface ESPNRecord {
  name: string;
  displayName: string;
  abbreviation: string;
  type: string;
  summary: string;
  value: number;
}

// ────────────────────────────────────────────────────────────────────────
// Play / Action
// ────────────────────────────────────────────────────────────────────────

export interface ESPNPlay {
  id: string;
  sequenceNumber: number;
  period?: {
    number: number;
    displayString?: string;
  };
  clock?: {
    displayValue: string;
    value: number;
  };
  type: ESPNPlayType;
  text: string;
  shortText?: string;
  awayTeamEvent?: boolean;
  homeTeamEvent?: boolean;
  participants?: ESPNPlayParticipant[];
  shotResult?: {
    position?: string;
    distance?: number;
    displayValue?: string;
  };
  statementId?: string;
  scoringPlay?: boolean;
  athletesInvolved?: ESPNAthleteCompact[];
}

export interface ESPNPlayType {
  id: string;
  text: string;
  displayName: string;
  abbreviation?: string;
}

export interface ESPNPlayParticipant {
  id: string;
  displayName: string;
  position?: string;
  statistics?: ESPNStatistic[];
}

// ────────────────────────────────────────────────────────────────────────
// Team
// ────────────────────────────────────────────────────────────────────────

export interface ESPNTeam {
  id: string;
  uid: string;
  slug: string;
  abbreviation: string;
  displayName: string;
  shortDisplayName: string;
  name: string;
  color?: string;
  alternateColor?: string;
  logo: string;
  venue?: ESPNVenue;
  links?: ESPNLink[];
  record?: ESPNRecord[];
  statistics?: ESPNStatistic[];
}

export interface ESPNTeamRoster {
  team: ESPNTeam;
  athletes: ESPNAthlete[];
}

export interface ESPNTeamSchedule {
  team: ESPNTeam;
  events: ESPNEvent[];
}

// ────────────────────────────────────────────────────────────────────────
// Athlete / Player
// ────────────────────────────────────────────────────────────────────────

export interface ESPNAthlete {
  id: string;
  uid: string;
  displayName: string;
  shortDisplayName: string;
  firstName?: string;
  lastName?: string;
  weight?: number;
  height?: number;
  age?: number;
  dateOfBirth?: string;
  position: string;
  slug?: string;
  jersey?: number;
  active?: boolean;
  links?: ESPNLink[];
  statistics?: ESPNStatistic[];
  team?: ESPNTeamCompact;
}

// ────────────────────────────────────────────────────────────────────────
// Standings / Rankings
// ────────────────────────────────────────────────────────────────────────

export interface ESPNStandings {
  season: number;
  seasonType?: number;
  week?: number;
  groups: ESPNStandingsGroup[];
}

export interface ESPNStandingsGroup {
  name: string;
  abbreviation?: string;
  displayName: string;
  entryId?: string;
  groupId: string;
  teams: ESPNTeamStanding[];
}

export interface ESPNTeamStanding {
  team: ESPNTeam;
  displaySeed?: string;
  stats: ESPNStatistic[];
}

export interface ESPNRanking {
  rank: number;
  previousRank?: number;
  team: ESPNTeam;
  pointsFor?: number;
  pointsAgainst?: number;
  pointDifferential?: number;
}

// ────────────────────────────────────────────────────────────────────────
// Venue
// ────────────────────────────────────────────────────────────────────────

export interface ESPNVenue {
  id: string;
  fullName: string;
  shortName?: string;
  city?: string;
  state?: string;
  country?: string;
  capacity?: number;
  grass?: boolean;
  indoor?: boolean;
  links?: ESPNLink[];
}

// ────────────────────────────────────────────────────────────────────────
// Broadcasts
// ────────────────────────────────────────────────────────────────────────

export interface ESPNBroadcast {
  language: string;
  region: string;
  displayName: string;
  links?: ESPNLink[];
}

// ────────────────────────────────────────────────────────────────────────
// Odds & Betting
// ────────────────────────────────────────────────────────────────────────

export interface ESPNOdd {
  provider?: {
    name?: string;
    id?: string;
    priority?: number;
  };
  displayName?: string;
  links?: ESPNLink[];
  details?: string;
  overUnder?: number;
  spread?: {
    away?: {
      value: number;
      displayValue: string;
    };
    home?: {
      value: number;
      displayValue: string;
    };
  };
}

// ────────────────────────────────────────────────────────────────────────
// Officials / Referee
// ────────────────────────────────────────────────────────────────────────

export interface ESPNOfficial {
  id: string;
  uid: string;
  displayName: string;
  firstName?: string;
  lastName?: string;
  position?: {
    id?: string;
    displayName?: string;
  };
  links?: ESPNLink[];
}

// ────────────────────────────────────────────────────────────────────────
// News & Media
// ────────────────────────────────────────────────────────────────────────

export interface ESPNArticle {
  id?: string;
  headline: string;
  description?: string;
  links: ESPNLink[];
  pubDate?: string;
  byline?: string;
  images?: Array<{
    url?: string;
    caption?: string;
    width?: number;
    height?: number;
  }>;
}

// ────────────────────────────────────────────────────────────────────────
// Site API (Scoreboard, Summary)
// ────────────────────────────────────────────────────────────────────────

export interface ESPNScoreboard {
  events: ESPNScorecardEvent[];
  leagues: ESPNLeague[];
}

export interface ESPNScorecardEvent {
  id: string;
  uid: string;
  date: string;
  name: string;
  shortName: string;
  status: {
    type: string;
    displayClock?: string;
    period?: number;
  };
  competitions: Array<{
    id: string;
    uid: string;
    date: string;
    displayName: string;
    status: {
      type: string;
      displayClock?: string;
      period?: number;
    };
    competitors: Array<{
      id: string;
      uid: string;
      type: string;
      homeAway: "home" | "away";
      displayName: string;
      abbreviation: string;
      score: number;
      logo: string;
      team?: {
        id: string;
        displayName: string;
        abbreviation: string;
        logo: string;
      };
      records?: Array<{ displayName: string; value: number }>;
    }>;
    broadcasts?: Array<{
      language: string;
      region: string;
      displayName: string;
    }>;
  }>;
  links?: ESPNLink[];
}

export interface ESPNSummary {
  id: string;
  uid: string;
  status: string;
  season: number;
  week: number;
  competitions: Array<{
    id: string;
    date: string;
    displayName: string;
    notes: Array<{ headline: string; description: string }>;
    status: {
      type: string;
      displayClock: string;
      period: number;
    };
    competitors: Array<{
      id: string;
      displayName: string;
      abbreviation: string;
      score: number;
      logo: string;
      records?: Array<{ displayName: string; value: number }>;
      statistics?: Array<{ displayName: string; value: number }>;
      leaders?: Array<{ displayName: string; value: number }>;
    }>;
    boxscore?: {
      teams: Array<{
        team: ESPNTeam;
        statistics: Array<{
          displayName: string;
          abbreviation: string;
          displayValue: string;
        }>;
      }>;
    };
  }>;
}

// ────────────────────────────────────────────────────────────────────────
// Generic Link
// ────────────────────────────────────────────────────────────────────────

export interface ESPNLink {
  text: string;
  short?: string;
  href: string;
  isExternal?: boolean;
  isPremium?: boolean;
  rel?: string[];
}

// ────────────────────────────────────────────────────────────────────────
// API Request Options
// ────────────────────────────────────────────────────────────────────────

export interface ESPNRequestOptions {
  page?: number;
  limit?: number;
  lang?: string;
  region?: string;
  utcOffset?: number;
  dates?: string[];
  season?: number;
  seasontype?: string;
  weeks?: number[];
  sort?: string;
  [key: string]: any;
}

// ────────────────────────────────────────────────────────────────────────
// Error Response
// ────────────────────────────────────────────────────────────────────────

export interface ESPNErrorResponse {
  code: number;
  message?: string;
  description?: string;
  detail?: string;
}
