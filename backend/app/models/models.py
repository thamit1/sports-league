from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import enum
import json


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPER_ADMIN   = "super_admin"
    CLUB_ADMIN    = "club_admin"
    CLUB_MANAGER  = "club_manager"
    PLAYER        = "player"
    OFFICIAL      = "official"
    SCORE_KEEPER  = "score_keeper"
    VIEWER        = "viewer"

class MatchStatus(str, enum.Enum):
    SCHEDULED            = "scheduled"
    IN_PROGRESS          = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"   # finalized by score keeper, waiting on captain sign-off
    DISPUTED             = "disputed"                  # a captain rejected the score; admin must resolve
    COMPLETED            = "completed"
    CANCELLED            = "cancelled"
    POSTPONED            = "postponed"

class TournamentStatus(str, enum.Enum):
    DRAFT        = "draft"
    REGISTRATION = "registration"
    IN_PROGRESS  = "in_progress"
    COMPLETED    = "completed"

class MembershipStatus(str, enum.Enum):
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    SUSPENDED = "suspended"

class BracketType(str, enum.Enum):
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    ROUND_ROBIN        = "round_robin"
    SWISS              = "swiss"

class MatchType(str, enum.Enum):
    SINGLES = "singles"
    DOUBLES = "doubles"

class SeasonResetType(str, enum.Enum):
    NONE = "none"
    SOFT = "soft"
    HARD = "hard"

class RatingVisibility(str, enum.Enum):
    PUBLIC        = "public"
    CLUB_MEMBERS  = "club_members"
    ADMINS_ONLY   = "admins_only"

class RatingJobStatus(str, enum.Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"

class RankingScope(str, enum.Enum):
    GLOBAL    = "global"
    CLUB      = "club"
    AGE_GROUP = "age_group"
    DIVISION  = "division"

class LeagueStatus(str, enum.Enum):
    DRAFT        = "draft"
    REGISTRATION = "registration"
    IN_PROGRESS  = "in_progress"
    COMPLETED    = "completed"
    CANCELLED    = "cancelled"


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class User:
    id: int
    email: str
    phone: Optional[str]
    password_hash: str
    first_name: str
    last_name: str
    role: str = "viewer"
    club_id: Optional[int] = None
    global_player_id: Optional[str] = None
    avatar_url: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    password_reset_required: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    roles: List[str] = field(default_factory=list)   # global-scope roles via user_assignments

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return asdict(self)


@dataclass
class Club:
    id: int
    name: str
    code: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#1a56db"
    secondary_color: str = "#ffffff"
    city: Optional[str] = None
    country: str = "India"
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class PlayerMembership:
    id: int
    player_id: int
    club_id: int
    jersey_no: Optional[str] = None
    position: Optional[str] = None
    status: str = "active"
    joined_at: Optional[str] = None
    left_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Sport:
    id: int
    name: str
    category: Optional[str] = None
    max_team_size: int = 1
    min_team_size: int = 1
    scoring_config: Optional[Dict] = None
    is_active: bool = True
    icon: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        if self.scoring_config and isinstance(self.scoring_config, str):
            data['scoring_config'] = json.loads(self.scoring_config)
        return data


@dataclass
class Team:
    id: int
    name: str
    club_id: int
    sport_id: int
    captain_id: Optional[int] = None
    age_group: Optional[str] = None
    division: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class TeamMember:
    id: int
    team_id: int
    player_id: int
    jersey_no: Optional[str] = None
    position: Optional[str] = None
    is_active: bool = True
    joined_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Tournament:
    id: int
    name: str
    sport_id: int
    organizer_id: int
    bracket_type: str = "single_elimination"
    status: str = "draft"
    max_teams: int = 16
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    prize_pool: float = 0
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class TournamentRegistration:
    id: int
    tournament_id: int
    team_id: int
    seed: Optional[int] = None
    registered_at: Optional[str] = None
    is_approved: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class Match:
    id: int
    sport_id: int
    team_a_id: int
    team_b_id: int
    tournament_id: Optional[int] = None
    official_id: Optional[int] = None
    status: str = "scheduled"
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    venue: Optional[str] = None
    score_a: Optional[Dict] = None
    score_b: Optional[Dict] = None
    winner_id: Optional[int] = None
    round_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        if self.score_a and isinstance(self.score_a, str):
            data['score_a'] = json.loads(self.score_a)
        if self.score_b and isinstance(self.score_b, str):
            data['score_b'] = json.loads(self.score_b)
        return data


@dataclass
class SportRatingConfig:
    id: int
    sport_id: int
    provisional_threshold: int = 5
    season_reset_type: str = "none"
    season_reset_factor: float = 0.3
    visibility: str = "club_members"
    k_factor_provisional: float = 32.0
    k_factor_established: float = 16.0
    k_factor_elite: float = 8.0
    starting_rating: float = 50.0
    max_rating_change_per_match: float = 15.0
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class PlayerRating:
    id: int
    player_id: int
    sport_id: int
    match_type: str
    rating: float = 50.0
    peak_rating: float = 50.0
    matches_played: int = 0
    matches_won: int = 0
    matches_drawn: int = 0
    matches_lost: int = 0
    is_provisional: bool = True
    is_active: bool = True
    last_match_at: Optional[str] = None
    last_calculated_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class RatingHistory:
    id: int
    player_id: int
    sport_id: int
    match_id: int
    match_type: str
    rating_before: float
    rating_after: float
    rating_delta: float
    expected_score: float
    actual_score: float
    opponent_rating_at_time: float
    k_factor_used: float
    match_played_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class PlayerRanking:
    id: int
    player_id: int
    sport_id: int
    match_type: str
    scope: str
    scope_value: Optional[str]
    rank: int
    rating: float
    total_ranked: int
    calculated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class RecalculationJob:
    id: int
    triggered_by_id: Optional[int] = None
    sport_id: Optional[int] = None
    status: str = "pending"
    matches_processed: int = 0
    players_updated: int = 0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class League:
    id: int
    name: str
    organizer_id: int                # Club hosting the league
    status: str = "draft"
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    venue: Optional[str] = None
    max_teams_per_sport: int = 16
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class LeagueSport:
    """One row per (league, sport). Backed by a tournament for matches/registration."""
    id: int
    league_id: int
    sport_id: int
    tournament_id: int
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class MatchEvent:
    id: int
    match_id: int
    event_type: str
    team_id: Optional[int] = None
    player_id: Optional[int] = None
    event_data: Optional[Dict] = None
    minute: Optional[int] = None
    created_at: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        if self.event_data and isinstance(self.event_data, str):
            data['event_data'] = json.loads(self.event_data)
        return data
