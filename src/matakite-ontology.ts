/**
 * MATAKITE Ontology — Operation Kāhu
 * Core data objects with provenance tagging.
 * Every record tagged: OWN | OBSERVED | MODELLED
 */

export type Provenance = "OWN" | "OBSERVED" | "MODELLED";
export type Classification = "PROTECTED" | "INTERNAL" | "OPEN";

// ─── Base Interface ────────────────────────────────────────────────────────

export interface MatakiteRecord {
  id: string;
  provenance: Provenance;
  classification: Classification;
  createdAt: string;       // ISO-8601
  updatedAt: string;
  sourceRef?: string;      // citation / feed name
}

// ─── Match ─────────────────────────────────────────────────────────────────

export interface Match extends MatakiteRecord {
  opponent: string;
  venue: string;
  venueAltitudeM?: number;
  kickoff: string;          // ISO-8601
  competition: string;
  phase: MatchPhase;
  score?: { home: number; away: number };
}

export type MatchPhase =
  | "pre-match"
  | "first-half"
  | "half-time"
  | "second-half"
  | "full-time";

// ─── Phase (in-match event) ────────────────────────────────────────────────

export interface Phase extends MatakiteRecord {
  matchId: string;
  minute: number;
  second?: number;
  eventType: PhaseEventType;
  team: "home" | "away";
  fieldPosition?: string;    // e.g. "opp-22", "own-10"
  outcome?: string;
  notes?: string;
}

export type PhaseEventType =
  | "scrum"
  | "lineout"
  | "breakdown"
  | "kick"
  | "try"
  | "penalty"
  | "conversion"
  | "substitution"
  | "maul"
  | "ruck";

// ─── Prediction ────────────────────────────────────────────────────────────

export interface Prediction extends MatakiteRecord {
  matchId: string;
  type: "pre-match" | "in-match";
  minute?: number;          // null for pre-match
  winProbHome: number;      // 0–1
  winProbAway: number;      // 0–1
  confidenceBand: number;   // ±band width (e.g. 0.06 = ±6%)
  scoreProjection?: {
    home: { median: number; p25: number; p75: number };
    away: { median: number; p25: number; p75: number };
  };
  battlegrounds?: Battlegrounds;
  theCall?: TheCall;
  model: PredictionModel;
}

export interface Battlegrounds {
  scrum: number;            // win-prob 0–1
  lineout: number;
  breakdown: number;
  territory: number;
  aerial: number;
}

export interface TheCall {
  action: string;
  expectedPointsValue: number;
  windowClosesMinute: number;
  confidence: number;
}

export type PredictionModel = "opta-xp" | "mirofish-swarm" | "ensemble-bayesian";

// ─── Calibration Record ────────────────────────────────────────────────────

export interface CalibrationRecord extends MatakiteRecord {
  matchId: string;
  predictionId: string;
  forecastedProbability: number;
  actualOutcome: 0 | 1;    // 0 = did not occur, 1 = occurred
  brierScore: number;       // (forecast - actual)^2
  logLoss?: number;
  notes?: string;
}

// ─── PIR (Priority Intelligence Requirement) ──────────────────────────────

export interface PIR extends MatakiteRecord {
  opponent: string;
  question: string;
  priority: 1 | 2 | 3;     // 1 = highest
  status: "open" | "answered" | "partial";
  answer?: string;
  feedsRequired: FeedType[];
}

// ─── Feed Register ─────────────────────────────────────────────────────────

export interface FeedEntry extends MatakiteRecord {
  name: string;
  discipline: FeedDiscipline;
  latency: "live" | "post" | "daily" | "event-based" | "ongoing" | "weekly";
  powers: string[];
  active: boolean;
  apiEndpoint?: string;     // null for OWN feeds (internal)
  licenseRef?: string;
}

export type FeedDiscipline =
  | "OSINT"
  | "IMINT"
  | "MASINT"
  | "Telemetry"
  | "HUMINT"
  | "Derived";

export type FeedType =
  | "opta"
  | "broadcast-video"
  | "broadcast-tracking"
  | "gps-imu"
  | "biometrics"
  | "drone"
  | "weather"
  | "squad-news"
  | "referee"
  | "rankings"
  | "coaching-dna"
  | "scouting"
  | "mirofish";

// ─── Dossier ───────────────────────────────────────────────────────────────

export interface Dossier extends MatakiteRecord {
  matchId: string;
  opponent: string;
  generatedAt: string;
  pirs: PIR[];
  keyPlayers: KeyPlayer[];
  attackShape: string;
  defenceWeakness: string;
  setpieceProfile: string;
  refereeProfile?: string;
  weatherPlan?: string;
}

export interface KeyPlayer {
  name: string;
  position: string;
  expectedPointsImpact: number;   // +/- xP if neutralised
  tendency: string;
  vulnerability?: string;
}

// ─── Scenario Tree ─────────────────────────────────────────────────────────

export interface ScenarioTree extends MatakiteRecord {
  matchId: string;
  predictionId: string;
  scenarios: Scenario[];
}

export interface Scenario {
  label: string;
  probability: number;
  lever: string;            // "the thing that swings it"
  winProbHome: number;
}

// ─── SourceFeed ────────────────────────────────────────────────────────────

export interface SourceFeed extends MatakiteRecord {
  name: string;
  discipline: FeedDiscipline;
  licenceStatus: "open" | "licensed" | "own";
  provenanceDefault: Provenance;
  refreshCadence: "live" | "daily" | "weekly" | "event-based" | "ongoing";
  apiEndpoint?: string;
  licenceRef?: string;
  active: boolean;
}

// ─── IngestionRun ──────────────────────────────────────────────────────────

export interface IngestionRun extends MatakiteRecord {
  feedId: string;
  startedAt: string;
  completedAt?: string;
  recordCount: number;
  status: "running" | "complete" | "failed";
  checksum?: string;
  notes?: string;
}

// ─── PlayerCareer ──────────────────────────────────────────────────────────

export interface PlayerCareer extends MatakiteRecord {
  playerId: string;
  name: string;
  position: string;
  debut: string;
  caps: number;
  careerTries: number;
  careerPoints?: number;
  clubs?: string[];
  wikiDataRef?: string;     // CC0 source — no ToS friction
}

// ─── PlayerStatLine ────────────────────────────────────────────────────────

export interface PlayerStatLine extends MatakiteRecord {
  playerId: string;
  matchId: string;
  position: string;
  minutes: number;
  carries: number;
  metresGained: number;
  tackles: number;
  tacklesWon: number;
  rucksWon: number;
  passes: number;
  kicksAttempted: number;
  kicksCompleted: number;
  turnoversWon: number;
  errors: number;
}

// ─── RefereeProfile ────────────────────────────────────────────────────────

export interface RefereeProfile extends MatakiteRecord {
  refId: string;
  name: string;
  breakdownPenaltyRate: number;   // per match
  scrumPenaltyRate: number;
  maulCallTendency: "conservative" | "neutral" | "permissive";
  cardTendency: "strict" | "balanced" | "lenient";
  notes?: string;
}

// ─── BiometricReading ──────────────────────────────────────────────────────
// OWN data — NZ Privacy Act 2020 + player consent required on every record.
// Classification: always PROTECTED. Never sits in an open zone.

export interface BiometricReading extends MatakiteRecord {
  playerId: string;
  recordedAt: string;
  heartRateVariability: number;
  sleepScore: number;       // 0–100
  wellnessScore: number;    // 0–100
  readiness: "low" | "moderate" | "high";
  consentRef: string;       // reference to signed consent document
  restricted: true;
}
