from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import enum
import json


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPER_ADMIN  = "super_admin"
    CLUB_ADMIN   = "club_admin"
    CLUB_MANAGER = "club_manager"
    PLAYER       = "player"
    OFFICIAL     = "official"
    VIEWER       = "viewer"

class MatchStatus(str, enum.Enum):
    SCHEDULED   = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    CANCELLED   = "cancelled"
    POSTPONED   = "postponed"

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
