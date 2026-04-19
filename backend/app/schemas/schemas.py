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


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
