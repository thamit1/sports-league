"""
Scoring — a focused, mobile-friendly entry point for score keepers.

Score keepers see only matches assigned to them. Admins / managers can score
any match via the existing /api/matches/{id}/score endpoint; this router is
the dedicated, restricted-scope path that the Score Entry UI talks to.
"""
import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import execute_query
from app.core.security import get_current_user
from app.models.models import UserRole, MatchStatus
from app.schemas.schemas import ScoringMatchOut, ScoreSubmit

router = APIRouter()

# Roles that can see/score every match without an assignment row.
_OPEN_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.CLUB_ADMIN.value,
    UserRole.CLUB_MANAGER.value,
    UserRole.OFFICIAL.value,
}


def _is_open_role(user) -> bool:
    return user.role in _OPEN_ROLES


def _user_can_score(user, match_id: int) -> bool:
    if _is_open_role(user):
        return True
    # Score keepers and others need an explicit assignment row
    row = execute_query(
        "SELECT 1 FROM match_assignments WHERE match_id = ? AND user_id = ?",
        (match_id, user.id), fetch_one=True,
    )
    return bool(row)


def _safe_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _row_to_match(m) -> dict:
    return {
        "id": m["id"],
        "sport_id": m["sport_id"],
        "sport_name": m.get("sport_name"),
        "sport_icon": m.get("sport_icon"),
        "team_a_id": m["team_a_id"],
        "team_a_name": m.get("team_a_name"),
        "team_b_id": m["team_b_id"],
        "team_b_name": m.get("team_b_name"),
        "status": m["status"],
        "scheduled_at": m["scheduled_at"],
        "venue": m["venue"],
        "score_a": _safe_json(m["score_a"]),
        "score_b": _safe_json(m["score_b"]),
        "winner_id": m["winner_id"],
    }


# ── Queue: matches this user can score ──────────────────────────────────

@router.get("/queue", response_model=List[ScoringMatchOut])
@router.get("/queue/", response_model=List[ScoringMatchOut])
def my_scoring_queue(
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Return matches the current user is allowed to score.

    - Open roles (super_admin, club_admin, club_manager, official): every match
    - Everyone else (score_keeper, player, viewer): only matches they're assigned to

    Excludes cancelled & completed matches by default; pass ?status=completed
    or ?status=all to override.
    """
    base = """
        SELECT m.*,
               s.name AS sport_name, s.icon AS sport_icon,
               ta.name AS team_a_name, tb.name AS team_b_name
          FROM matches m
          LEFT JOIN sports s ON s.id = m.sport_id
          LEFT JOIN teams  ta ON ta.id = m.team_a_id
          LEFT JOIN teams  tb ON tb.id = m.team_b_id
    """
    where = []
    params: list = []
    if not _is_open_role(current_user):
        base += " JOIN match_assignments a ON a.match_id = m.id AND a.user_id = ? "
        params.append(current_user.id)

    if status == "all":
        pass
    elif status:
        where.append("m.status = ?")
        params.append(status)
    else:
        where.append("m.status NOT IN ('cancelled', 'completed')")

    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY (m.status = 'in_progress') DESC, m.scheduled_at ASC, m.id DESC"

    rows = execute_query(base, tuple(params), fetch_all=True) or []
    return [_row_to_match(r) for r in rows]


# ── Single match (focused entry payload) ───────────────────────────────

@router.get("/matches/{match_id}", response_model=ScoringMatchOut)
def get_scoring_match(match_id: int, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    row = execute_query(
        """SELECT m.*,
                  s.name AS sport_name, s.icon AS sport_icon,
                  ta.name AS team_a_name, tb.name AS team_b_name
             FROM matches m
             LEFT JOIN sports s ON s.id = m.sport_id
             LEFT JOIN teams ta ON ta.id = m.team_a_id
             LEFT JOIN teams tb ON tb.id = m.team_b_id
            WHERE m.id = ?""",
        (match_id,), fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Match not found")
    return _row_to_match(row)


# ── Submit / update score (auto-flips status to in_progress) ────────────

@router.patch("/matches/{match_id}/score", response_model=ScoringMatchOut)
def submit_score(match_id: int, payload: ScoreSubmit, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    existing = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing["status"] == MatchStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Match is cancelled")

    # Auto-flip to in_progress if it's still scheduled and we have a score
    new_status = existing["status"]
    if new_status == MatchStatus.SCHEDULED.value:
        new_status = MatchStatus.IN_PROGRESS.value

    sa = json.dumps(payload.score_a) if payload.score_a is not None else None
    sb = json.dumps(payload.score_b) if payload.score_b is not None else None

    execute_query(
        """UPDATE matches SET
              score_a = ?, score_b = ?, winner_id = ?, status = ?,
              started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
              updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (sa, sb, payload.winner_id, new_status, match_id),
    )
    return get_scoring_match(match_id, current_user)


# ── Finalize (sets status = completed, eligible for rating recalc) ──────

@router.post("/matches/{match_id}/finalize", response_model=ScoringMatchOut)
def finalize_match(match_id: int, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    existing = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing["status"] == MatchStatus.COMPLETED.value:
        return get_scoring_match(match_id, current_user)
    if existing["score_a"] is None or existing["score_b"] is None:
        raise HTTPException(status_code=400, detail="Cannot finalize without a score for both teams")

    execute_query(
        """UPDATE matches SET
              status = 'completed',
              ended_at = CURRENT_TIMESTAMP,
              updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (match_id,),
    )
    return get_scoring_match(match_id, current_user)
