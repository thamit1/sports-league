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
from app.core.security import get_current_user, user_has_any_role
from app.models.models import UserRole, MatchStatus
from app.schemas.schemas import ScoringMatchOut, ScoreSubmit

router = APIRouter()

# Roles that can see/score every match without an explicit match assignment.
_OPEN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.CLUB_ADMIN.value,
    UserRole.CLUB_MANAGER.value,
    UserRole.OFFICIAL.value,
)


def _is_open_role(user) -> bool:
    # Checks user_assignments at global scope (Phase 2), with users.role fallback.
    return user_has_any_role(user, _OPEN_ROLES)


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


# ── Finalize (Phase 4C: status → awaiting_confirmation pending captain sign-off) ──

def _team_has_captain(team_id: int) -> bool:
    row = execute_query(
        "SELECT 1 FROM user_assignments WHERE scope_type = 'team' AND scope_id = ? AND role = 'captain'",
        (team_id,), fetch_one=True,
    )
    return bool(row)


def _user_is_captain_of(user_id: int, team_id: int) -> bool:
    row = execute_query(
        "SELECT 1 FROM user_assignments WHERE user_id = ? AND scope_type = 'team' AND scope_id = ? AND role = 'captain'",
        (user_id, team_id), fetch_one=True,
    )
    return bool(row)


def _maybe_complete_match(match: dict) -> str:
    """
    Check whether both sides have confirmed and advance match.status accordingly.
    Returns the new status (which may be unchanged).
    """
    confs = execute_query(
        "SELECT team_side, action FROM match_confirmations WHERE match_id = ?",
        (match['id'],), fetch_all=True,
    ) or []
    has_a = any(c['team_side'] == 'a' and c['action'] == 'confirmed' for c in confs)
    has_b = any(c['team_side'] == 'b' and c['action'] == 'confirmed' for c in confs)
    has_dispute = any(c['action'] == 'disputed' for c in confs)

    # If a side has no captain at all, treat it as auto-confirmed (admin can still override)
    if not has_a and not _team_has_captain(match['team_a_id']):
        has_a = True
    if not has_b and not _team_has_captain(match['team_b_id']):
        has_b = True

    if has_dispute:
        new_status = MatchStatus.DISPUTED.value
    elif has_a and has_b:
        new_status = MatchStatus.COMPLETED.value
    else:
        new_status = MatchStatus.AWAITING_CONFIRMATION.value

    if new_status != match['status']:
        ended_at_clause = ", ended_at = CURRENT_TIMESTAMP" if new_status == MatchStatus.COMPLETED.value else ""
        execute_query(
            f"UPDATE matches SET status = ?{ended_at_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, match['id']),
        )
    return new_status


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

    # Step 1 — mark as awaiting_confirmation
    execute_query(
        """UPDATE matches SET
              status = 'awaiting_confirmation',
              ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
              updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (match_id,),
    )
    # Step 2 — if either side has no captain, the auto-confirm logic in
    # _maybe_complete_match may immediately resolve to 'completed'.
    refreshed = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    _maybe_complete_match(refreshed)
    return get_scoring_match(match_id, current_user)


# ── Captain confirm / dispute ──────────────────────────────────────────

@router.post("/matches/{match_id}/confirm", response_model=ScoringMatchOut)
def confirm_match(match_id: int, current_user=Depends(get_current_user)):
    return _record_confirmation(match_id, current_user, action="confirmed", notes=None)


@router.post("/matches/{match_id}/dispute", response_model=ScoringMatchOut)
def dispute_match(match_id: int, payload: dict = None, current_user=Depends(get_current_user)):
    notes = (payload or {}).get("notes") if isinstance(payload, dict) else None
    return _record_confirmation(match_id, current_user, action="disputed", notes=notes)


def _record_confirmation(match_id: int, current_user, action: str, notes):
    match = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match['status'] not in (MatchStatus.AWAITING_CONFIRMATION.value, MatchStatus.DISPUTED.value):
        raise HTTPException(status_code=400, detail=f"Match status '{match['status']}' is not awaiting confirmation")

    # Which side is the user a captain for?
    on_a = _user_is_captain_of(current_user.id, match['team_a_id'])
    on_b = _user_is_captain_of(current_user.id, match['team_b_id'])
    if not on_a and not on_b:
        raise HTTPException(status_code=403, detail="Only team captains can confirm or dispute this match")
    if on_a and on_b:
        raise HTTPException(status_code=400, detail="You are captain of both teams; cannot confirm")

    team_side = 'a' if on_a else 'b'
    execute_query(
        """INSERT INTO match_confirmations (match_id, user_id, team_side, action, notes, submitted_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(match_id, user_id) DO UPDATE SET
                team_side = excluded.team_side,
                action = excluded.action,
                notes = excluded.notes,
                submitted_at = CURRENT_TIMESTAMP""",
        (match_id, current_user.id, team_side, action, notes),
    )
    refreshed = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    _maybe_complete_match(refreshed)
    return get_scoring_match(match_id, current_user)


# ── Match events (Phase 6.1b: player-attributed scoring) ───────────────

@router.get("/matches/{match_id}/events")
def list_scoring_events(match_id: int, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    rows = execute_query(
        """SELECT e.*,
                  (u.first_name || ' ' || u.last_name) AS player_name,
                  t.name AS team_name
             FROM match_events e
             LEFT JOIN users u ON u.id = e.player_id
             LEFT JOIN teams t ON t.id = e.team_id
            WHERE e.match_id = ?
            ORDER BY e.id DESC""",
        (match_id,), fetch_all=True,
    ) or []
    for r in rows:
        if r.get('event_data') and isinstance(r['event_data'], str):
            try:
                r['event_data'] = json.loads(r['event_data'])
            except Exception:
                pass
    return rows


@router.post("/matches/{match_id}/events", status_code=201)
def add_scoring_event(match_id: int, payload: dict, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    match = execute_query("SELECT team_a_id, team_b_id FROM matches WHERE id = ?",
                          (match_id,), fetch_one=True)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    side = payload.get('team_side')
    if side == 'a':
        team_id = match['team_a_id']
    elif side == 'b':
        team_id = match['team_b_id']
    else:
        raise HTTPException(status_code=400, detail="team_side must be 'a' or 'b'")

    event_type = payload.get('event_type')
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type required")

    player_id = payload.get('player_id')
    value = payload.get('value')
    minute = payload.get('minute')
    extra  = payload.get('extra') or {}

    # event_data merges {value, ...extra} — extra carries sport-specific fields
    # (e.g. bowler_id for cricket).
    data = {}
    if value is not None:
        data['value'] = value
    if isinstance(extra, dict):
        data.update({k: v for k, v in extra.items() if v is not None})

    eid = execute_query(
        """INSERT INTO match_events (match_id, team_id, player_id, event_type, event_data, minute, created_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (match_id, team_id, player_id, event_type,
         json.dumps(data) if data else None,
         minute),
        return_lastid=True,
    )
    return {"id": eid, "match_id": match_id, "team_id": team_id, "team_side": side,
            "player_id": player_id, "event_type": event_type, "value": value, "extra": extra}


@router.delete("/matches/{match_id}/events/{event_id}", status_code=204)
def delete_scoring_event(match_id: int, event_id: int, current_user=Depends(get_current_user)):
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    existing = execute_query(
        "SELECT id FROM match_events WHERE id = ? AND match_id = ?",
        (event_id, match_id), fetch_one=True,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    execute_query("DELETE FROM match_events WHERE id = ?", (event_id,))


@router.get("/matches/{match_id}/roster")
def list_match_rosters(match_id: int, current_user=Depends(get_current_user)):
    """Returns rosters for both teams in one call — for the kiosk's player selectors."""
    if not _user_can_score(current_user, match_id):
        raise HTTPException(status_code=403, detail="Not assigned to this match")
    match = execute_query("SELECT team_a_id, team_b_id FROM matches WHERE id = ?",
                          (match_id,), fetch_one=True)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    def _roster(team_id):
        return execute_query(
            """SELECT tm.player_id AS id, (u.first_name || ' ' || u.last_name) AS name,
                      tm.jersey_no, tm.position
                 FROM team_members tm
                 LEFT JOIN users u ON u.id = tm.player_id
                WHERE tm.team_id = ? AND tm.is_active = 1
                ORDER BY u.first_name""",
            (team_id,), fetch_all=True,
        ) or []
    return {"a": _roster(match['team_a_id']), "b": _roster(match['team_b_id'])}


@router.get("/matches/{match_id}/confirmations")
def list_confirmations(match_id: int, _=Depends(get_current_user)):
    return execute_query(
        """SELECT c.*, (u.first_name || ' ' || u.last_name) AS user_name
             FROM match_confirmations c
             LEFT JOIN users u ON u.id = c.user_id
            WHERE c.match_id = ?
            ORDER BY c.submitted_at""",
        (match_id,), fetch_all=True,
    ) or []
