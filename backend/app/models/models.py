from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    ForeignKey, Enum, Float, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


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


# ─── Club ─────────────────────────────────────────────────────────────────────

class Club(Base):
    __tablename__ = "clubs"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), nullable=False)
    short_name      = Column(String(20))
    code            = Column(String(10), unique=True, nullable=False)
    description     = Column(Text)
    logo_url        = Column(String(500))
    primary_color   = Column(String(7), default="#1a56db")
    secondary_color = Column(String(7), default="#ffffff")
    city            = Column(String(100))
    country         = Column(String(100), default="India")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users       = relationship("User", back_populates="club")
    teams       = relationship("Team", back_populates="club")
    memberships = relationship("PlayerMembership", back_populates="club")


# ─── User ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(255), unique=True, nullable=False, index=True)
    phone            = Column(String(20), unique=True, index=True)
    password_hash    = Column(String(255), nullable=False)
    first_name       = Column(String(100), nullable=False)
    last_name        = Column(String(100), nullable=False)
    role             = Column(Enum(UserRole), default=UserRole.VIEWER)
    club_id          = Column(Integer, ForeignKey("clubs.id"), nullable=True)
    global_player_id = Column(String(20), unique=True, index=True)
    avatar_url       = Column(String(500))
    date_of_birth    = Column(Date)
    gender           = Column(String(10))
    is_active        = Column(Boolean, default=True)
    is_verified      = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    club        = relationship("Club", back_populates="users")
    memberships = relationship("PlayerMembership", back_populates="player")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# ─── Player Membership (multi-club) ───────────────────────────────────────────

class PlayerMembership(Base):
    __tablename__ = "player_memberships"

    id         = Column(Integer, primary_key=True, index=True)
    player_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    club_id    = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    jersey_no  = Column(String(10))
    position   = Column(String(50))
    status     = Column(Enum(MembershipStatus), default=MembershipStatus.ACTIVE)
    joined_at  = Column(DateTime, default=datetime.utcnow)
    left_at    = Column(DateTime, nullable=True)

    player = relationship("User", back_populates="memberships")
    club   = relationship("Club", back_populates="memberships")


# ─── Sport ────────────────────────────────────────────────────────────────────

class Sport(Base):
    __tablename__ = "sports"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), unique=True, nullable=False)
    category        = Column(String(50))        # team, racket, precision, aquatic, other
    max_team_size   = Column(Integer, default=1)
    min_team_size   = Column(Integer, default=1)
    scoring_config  = Column(JSON)              # sport-specific scoring rules
    is_active       = Column(Boolean, default=True)
    icon            = Column(String(50))

    teams       = relationship("Team", back_populates="sport")
    matches     = relationship("Match", back_populates="sport")
    tournaments = relationship("Tournament", back_populates="sport")


# ─── Team ─────────────────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), nullable=False)
    club_id    = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    sport_id   = Column(Integer, ForeignKey("sports.id"), nullable=False)
    captain_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    age_group  = Column(String(20))             # U12, U16, Open, Senior, etc.
    division   = Column(String(50))
    logo_url   = Column(String(500))
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    club    = relationship("Club", back_populates="teams")
    sport   = relationship("Sport", back_populates="teams")
    captain = relationship("User", foreign_keys=[captain_id])
    members = relationship("TeamMember", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    id         = Column(Integer, primary_key=True, index=True)
    team_id    = Column(Integer, ForeignKey("teams.id"), nullable=False)
    player_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    jersey_no  = Column(String(10))
    position   = Column(String(50))
    is_active  = Column(Boolean, default=True)
    joined_at  = Column(DateTime, default=datetime.utcnow)

    team   = relationship("Team", back_populates="members")
    player = relationship("User")


# ─── Tournament ───────────────────────────────────────────────────────────────

class Tournament(Base):
    __tablename__ = "tournaments"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), nullable=False)
    sport_id       = Column(Integer, ForeignKey("sports.id"), nullable=False)
    organizer_id   = Column(Integer, ForeignKey("clubs.id"), nullable=False)
    bracket_type   = Column(Enum(BracketType), default=BracketType.SINGLE_ELIMINATION)
    status         = Column(Enum(TournamentStatus), default=TournamentStatus.DRAFT)
    max_teams      = Column(Integer, default=16)
    start_date     = Column(Date)
    end_date       = Column(Date)
    venue          = Column(String(200))
    description    = Column(Text)
    prize_pool     = Column(Float, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow)

    sport         = relationship("Sport", back_populates="tournaments")
    organizer     = relationship("Club")
    registrations = relationship("TournamentRegistration", back_populates="tournament")
    matches       = relationship("Match", back_populates="tournament")


class TournamentRegistration(Base):
    __tablename__ = "tournament_registrations"

    id            = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    team_id       = Column(Integer, ForeignKey("teams.id"), nullable=False)
    seed          = Column(Integer)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_approved   = Column(Boolean, default=False)

    tournament = relationship("Tournament", back_populates="registrations")
    team       = relationship("Team")


# ─── Match ────────────────────────────────────────────────────────────────────

class Match(Base):
    __tablename__ = "matches"

    id            = Column(Integer, primary_key=True, index=True)
    sport_id      = Column(Integer, ForeignKey("sports.id"), nullable=False)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)
    team_a_id     = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_b_id     = Column(Integer, ForeignKey("teams.id"), nullable=False)
    official_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    status        = Column(Enum(MatchStatus), default=MatchStatus.SCHEDULED)
    scheduled_at  = Column(DateTime)
    started_at    = Column(DateTime)
    ended_at      = Column(DateTime)
    venue         = Column(String(200))
    score_a       = Column(JSON)      # flexible: {"sets": [6,4,7], "points": 25} etc.
    score_b       = Column(JSON)
    winner_id     = Column(Integer, ForeignKey("teams.id"), nullable=True)
    round_number  = Column(Integer)
    notes         = Column(Text)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sport      = relationship("Sport", back_populates="matches")
    tournament = relationship("Tournament", back_populates="matches")
    team_a     = relationship("Team", foreign_keys=[team_a_id])
    team_b     = relationship("Team", foreign_keys=[team_b_id])
    winner     = relationship("Team", foreign_keys=[winner_id])
    official   = relationship("User", foreign_keys=[official_id])
    events     = relationship("MatchEvent", back_populates="match")


class MatchEvent(Base):
    """Generic event log for any sport: goals, wickets, fouls, points, etc."""
    __tablename__ = "match_events"

    id          = Column(Integer, primary_key=True, index=True)
    match_id    = Column(Integer, ForeignKey("matches.id"), nullable=False)
    team_id     = Column(Integer, ForeignKey("teams.id"), nullable=True)
    player_id   = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type  = Column(String(50))   # goal, wicket, point, foul, card, set, frame
    event_data  = Column(JSON)         # sport-specific payload
    minute      = Column(Integer)      # or set number, over, frame, etc.
    created_at  = Column(DateTime, default=datetime.utcnow)

    match  = relationship("Match", back_populates="events")
    team   = relationship("Team")
    player = relationship("User")
