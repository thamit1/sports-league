from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime, date
from app.models.models import UserRole, MatchStatus, TournamentStatus, BracketType, MembershipStatus


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    club_id: Optional[int] = None
    role: UserRole = UserRole.VIEWER

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class PlayerCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    club_id: Optional[int] = None
    role: UserRole = UserRole.VIEWER

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ─── User / Player ────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    role: UserRole
    club_id: Optional[int]
    global_player_id: Optional[str]
    avatar_url: Optional[str]
    gender: Optional[str]
    is_active: bool
    is_verified: bool
    password_reset_required: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

class UserAdminUpdate(BaseModel):
    role: Optional[UserRole] = None
    temporary_password: Optional[str] = None
    password_reset_required: Optional[bool] = None
    is_active: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    new_password: str
    old_password: Optional[str] = None


# ─── Club ─────────────────────────────────────────────────────────────────────

class ClubCreate(BaseModel):
    name: str
    code: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: str = "#1a56db"
    secondary_color: str = "#ffffff"
    city: Optional[str] = None
    country: str = "India"

class ClubUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

class ClubOut(BaseModel):
    id: int
    name: str
    short_name: Optional[str]
    code: str
    description: Optional[str]
    logo_url: Optional[str]
    primary_color: str
    secondary_color: str
    city: Optional[str]
    country: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Sport ────────────────────────────────────────────────────────────────────

class SportCreate(BaseModel):
    name: str
    category: Optional[str] = None
    max_team_size: int = 1
    min_team_size: int = 1
    icon: Optional[str] = None

class SportUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    max_team_size: Optional[int] = None
    min_team_size: Optional[int] = None
    icon: Optional[str] = None

class SportOut(BaseModel):
    id: int
    name: str
    category: Optional[str]
    max_team_size: int
    min_team_size: int
    scoring_config: Optional[Any]
    is_active: bool
    icon: Optional[str]

    class Config:
        from_attributes = True


# ─── Team ─────────────────────────────────────────────────────────────────────

class TeamCreate(BaseModel):
    name: str
    club_id: int
    sport_id: int
    captain_id: Optional[int] = None
    age_group: Optional[str] = None
    division: Optional[str] = None

class TeamOut(BaseModel):
    id: int
    name: str
    club_id: int
    sport_id: int
    captain_id: Optional[int]
    age_group: Optional[str]
    division: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    sport_id: Optional[int] = None
    club_id: Optional[int] = None
    captain_id: Optional[int] = None
    age_group: Optional[str] = None
    division: Optional[str] = None
    logo_url: Optional[str] = None

class TeamMemberAdd(BaseModel):
    player_id: int
    jersey_no: Optional[str] = None
    position: Optional[str] = None


# ─── Tournament ───────────────────────────────────────────────────────────────

class TournamentCreate(BaseModel):
    name: str
    sport_id: int
    organizer_id: int
    bracket_type: BracketType = BracketType.SINGLE_ELIMINATION
    max_teams: int = 16
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    prize_pool: float = 0

class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    sport_id: Optional[int] = None
    organizer_id: Optional[int] = None
    bracket_type: Optional[BracketType] = None
    max_teams: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    prize_pool: Optional[float] = None
    status: Optional[TournamentStatus] = None

class TournamentOut(BaseModel):
    id: int
    name: str
    sport_id: int
    organizer_id: int
    bracket_type: BracketType
    status: TournamentStatus
    max_teams: int
    start_date: Optional[date]
    end_date: Optional[date]
    venue: Optional[str]
    description: Optional[str]
    prize_pool: float
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Match ────────────────────────────────────────────────────────────────────

class MatchCreate(BaseModel):
    sport_id: int
    team_a_id: int
    team_b_id: int
    tournament_id: Optional[int] = None
    official_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    venue: Optional[str] = None
    round_number: Optional[int] = None

class MatchUpdate(BaseModel):
    sport_id: Optional[int] = None
    team_a_id: Optional[int] = None
    team_b_id: Optional[int] = None
    tournament_id: Optional[int] = None
    official_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    venue: Optional[str] = None
    round_number: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[MatchStatus] = None

class MatchScoreUpdate(BaseModel):
    score_a: Any
    score_b: Any
    winner_id: Optional[int] = None
    status: Optional[MatchStatus] = None

class MatchEventCreate(BaseModel):
    team_id: Optional[int] = None
    player_id: Optional[int] = None
    event_type: str
    event_data: Optional[Any] = None
    minute: Optional[int] = None

class MatchOut(BaseModel):
    id: int
    sport_id: int
    tournament_id: Optional[int]
    team_a_id: int
    team_b_id: int
    official_id: Optional[int]
    status: MatchStatus
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    venue: Optional[str]
    score_a: Optional[Any]
    score_b: Optional[Any]
    winner_id: Optional[int]
    round_number: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Ratings ──────────────────────────────────────────────────────────────────

class SportRatingConfigCreate(BaseModel):
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

class SportRatingConfigUpdate(BaseModel):
    provisional_threshold: Optional[int] = None
    season_reset_type: Optional[str] = None
    season_reset_factor: Optional[float] = None
    visibility: Optional[str] = None
    k_factor_provisional: Optional[float] = None
    k_factor_established: Optional[float] = None
    k_factor_elite: Optional[float] = None
    starting_rating: Optional[float] = None
    max_rating_change_per_match: Optional[float] = None
    is_active: Optional[bool] = None

class SportRatingConfigOut(BaseModel):
    id: int
    sport_id: int
    sport_name: Optional[str] = None
    provisional_threshold: int
    season_reset_type: str
    season_reset_factor: float
    visibility: str
    k_factor_provisional: float
    k_factor_established: float
    k_factor_elite: float
    starting_rating: float
    max_rating_change_per_match: float
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PlayerRatingOut(BaseModel):
    player_id: int
    player_name: Optional[str] = None
    sport_id: int
    sport_name: Optional[str] = None
    sport_icon: Optional[str] = None
    match_type: str
    rating: float
    peak_rating: float
    matches_played: int
    matches_won: int
    matches_drawn: int
    matches_lost: int
    is_provisional: bool
    global_rank: Optional[int] = None
    total_ranked: Optional[int] = None
    last_match_at: Optional[str] = None

    class Config:
        from_attributes = True


class RatingHistoryOut(BaseModel):
    id: int
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
    opponent_label: Optional[str] = None

    class Config:
        from_attributes = True


class LeaderboardEntryOut(BaseModel):
    rank: int
    player_id: int
    player_name: Optional[str] = None
    rating: float
    peak_rating: float
    matches_played: int
    is_provisional: bool
    trend: Optional[float] = None


class LeaderboardOut(BaseModel):
    sport_id: int
    sport_name: Optional[str] = None
    match_type: str
    scope: str
    scope_value: Optional[str] = None
    total_ranked: int
    entries: List[LeaderboardEntryOut]
    generated_at: datetime


class RecalculationJobOut(BaseModel):
    id: int
    triggered_by_id: Optional[int] = None
    triggered_by_name: Optional[str] = None
    sport_id: Optional[int] = None
    sport_name: Optional[str] = None
    status: str
    matches_processed: int
    players_updated: int
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class RecalculationRequest(BaseModel):
    sport_id: Optional[int] = None


class SeasonResetRequest(BaseModel):
    confirm: bool


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
