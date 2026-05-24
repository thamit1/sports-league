from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import MatchStatus, UserRole
from app.schemas.schemas import MatchCreate, MatchOut, MatchScoreUpdate, MatchEventCreate, MatchUpdate
import json

router = APIRouter()


def _safe_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def list_matches(
    tournament_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    sport_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    _=Depends(get_current_user),
):
    query = "SELECT * FROM matches WHERE 1=1"
    params = []

    if tournament_id:
        query += " AND tournament_id = ?"
        params.append(tournament_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if sport_id:
        query += " AND sport_id = ?"
        params.append(sport_id)

    query += f" ORDER BY scheduled_at DESC LIMIT {limit} OFFSET {skip}"

    matches_rows = execute_query(query, tuple(params), fetch_all=True)

    return [
        {
            "id": m['id'],
            "sport_id": m['sport_id'],
            "tournament_id": m['tournament_id'],
            "team_a_id": m['team_a_id'],
            "team_b_id": m['team_b_id'],
            "official_id": m['official_id'],
            "status": m['status'],
            "scheduled_at": m['scheduled_at'],
            "started_at": m['started_at'],
            "ended_at": m['ended_at'],
            "venue": m['venue'],
            "score_a": _safe_json(m['score_a']),
            "score_b": _safe_json(m['score_b']),
            "winner_id": m['winner_id'],
            "round_number": m['round_number'],
            "notes": m['notes'],
            "created_at": m['created_at'],
            "updated_at": m['updated_at'],
        }
        for m in matches_rows
    ]


@router.post("", response_model=dict, status_code=201)
@router.post("/", response_model=dict, status_code=201)
def create_match(
    payload: MatchCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    if payload.team_a_id == payload.team_b_id:
        raise HTTPException(status_code=400, detail="Teams must be different")

    match_data = payload.model_dump()
    match_id = execute_query(
        """INSERT INTO matches
           (sport_id, tournament_id, team_a_id, team_b_id, official_id, status, scheduled_at, venue, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (
            match_data.get('sport_id'),
            match_data.get('tournament_id'),
            match_data.get('team_a_id'),
            match_data.get('team_b_id'),
            match_data.get('official_id'),
            match_data.get('status', 'scheduled'),
            match_data.get('scheduled_at'),
            match_data.get('venue'),
            match_data.get('notes'),
        ),
        return_lastid=True
    )

    match_row = execute_query(
        "SELECT * FROM matches WHERE id = ?",
        (match_id,),
        fetch_one=True
    )

    return {
        "id": match_row['id'],
        "sport_id": match_row['sport_id'],
        "tournament_id": match_row['tournament_id'],
        "team_a_id": match_row['team_a_id'],
        "team_b_id": match_row['team_b_id'],
        "official_id": match_row['official_id'],
        "status": match_row['status'],
        "scheduled_at": match_row['scheduled_at'],
        "started_at": match_row['started_at'],
        "ended_at": match_row['ended_at'],
        "venue": match_row['venue'],
        "score_a": _safe_json(match_row['score_a']),
        "score_b": _safe_json(match_row['score_b']),
        "winner_id": match_row['winner_id'],
        "round_number": match_row['round_number'],
        "notes": match_row['notes'],
        "created_at": match_row['created_at'],
        "updated_at": match_row['updated_at'],
    }


@router.get("/{match_id}", response_model=dict)
def get_match(match_id: int, _=Depends(get_current_user)):
    match_row = execute_query(
        "SELECT * FROM matches WHERE id = ?",
        (match_id,),
        fetch_one=True
    )
    if not match_row:
        raise HTTPException(status_code=404, detail="Match not found")

    return {
        "id": match_row['id'],
        "sport_id": match_row['sport_id'],
        "tournament_id": match_row['tournament_id'],
        "team_a_id": match_row['team_a_id'],
        "team_b_id": match_row['team_b_id'],
        "official_id": match_row['official_id'],
        "status": match_row['status'],
        "scheduled_at": match_row['scheduled_at'],
        "started_at": match_row['started_at'],
        "ended_at": match_row['ended_at'],
        "venue": match_row['venue'],
        "score_a": _safe_json(match_row['score_a']),
        "score_b": _safe_json(match_row['score_b']),
        "winner_id": match_row['winner_id'],
        "round_number": match_row['round_number'],
        "notes": match_row['notes'],
        "created_at": match_row['created_at'],
        "updated_at": match_row['updated_at'],
    }


@router.patch("/{match_id}", response_model=dict)
def update_match(
    match_id: int,
    payload: MatchUpdate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    existing = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")

    updates = payload.model_dump(exclude_none=True)
    if "team_a_id" in updates and "team_b_id" in updates and updates["team_a_id"] == updates["team_b_id"]:
        raise HTTPException(status_code=400, detail="Teams must be different")
    if updates:
        if isinstance(updates.get("status"), MatchStatus):
            updates["status"] = updates["status"].value
        if isinstance(updates.get("scheduled_at"), datetime):
            updates["scheduled_at"] = updates["scheduled_at"].isoformat()
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [match_id]
        execute_query(f"UPDATE matches SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", tuple(values))

    row = execute_query("SELECT * FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    return {
        "id": row['id'], "sport_id": row['sport_id'], "tournament_id": row['tournament_id'],
        "team_a_id": row['team_a_id'], "team_b_id": row['team_b_id'], "official_id": row['official_id'],
        "status": row['status'], "scheduled_at": row['scheduled_at'], "started_at": row['started_at'],
        "ended_at": row['ended_at'], "venue": row['venue'],
        "score_a": _safe_json(row['score_a']), "score_b": _safe_json(row['score_b']),
        "winner_id": row['winner_id'], "round_number": row['round_number'], "notes": row['notes'],
        "created_at": row['created_at'], "updated_at": row['updated_at'],
    }


@router.delete("/{match_id}", status_code=204)
def delete_match(
    match_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query("SELECT id FROM matches WHERE id = ?", (match_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    execute_query("UPDATE matches SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (match_id,))


@router.patch("/{match_id}/score")
def update_score(
    match_id: int,
    payload: MatchScoreUpdate,
    _=Depends(require_roles(
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN,
        UserRole.CLUB_MANAGER, UserRole.OFFICIAL
    )),
):
    existing = execute_query(
        "SELECT * FROM matches WHERE id = ?",
        (match_id,),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")

    updates = {}
    if payload.score_a:
        updates['score_a'] = json.dumps(payload.score_a)
    if payload.score_b:
        updates['score_b'] = json.dumps(payload.score_b)
    if payload.winner_id:
        updates['winner_id'] = payload.winner_id
    if payload.status:
        updates['status'] = payload.status
        if payload.status == MatchStatus.IN_PROGRESS.value and not existing['started_at']:
            updates['started_at'] = datetime.utcnow().isoformat()
        if payload.status == MatchStatus.COMPLETED.value and not existing['ended_at']:
            updates['ended_at'] = datetime.utcnow().isoformat()

    updates['updated_at'] = datetime.utcnow().isoformat()

    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [match_id]
        execute_query(
            f"UPDATE matches SET {fields} WHERE id = ?",
            tuple(values)
        )

    return {"message": "Score updated", "match_id": match_id}


@router.post("/{match_id}/events", status_code=201)
def add_event(
    match_id: int,
    payload: MatchEventCreate,
    _=Depends(require_roles(
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN,
        UserRole.CLUB_MANAGER, UserRole.OFFICIAL
    )),
):
    match = execute_query(
        "SELECT id FROM matches WHERE id = ?",
        (match_id,),
        fetch_one=True
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    event_data = payload.model_dump()
    event_id = execute_query(
        """INSERT INTO match_events
           (match_id, team_id, player_id, event_type, event_data, minute)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            match_id,
            event_data.get('team_id'),
            event_data.get('player_id'),
            event_data.get('event_type'),
            json.dumps(event_data.get('event_data')) if event_data.get('event_data') else None,
            event_data.get('minute'),
        ),
        return_lastid=True
    )

    return {"message": "Event recorded", "event_id": event_id}


@router.get("/{match_id}/events")
def get_events(match_id: int, _=Depends(get_current_user)):
    events_rows = execute_query(
        "SELECT * FROM match_events WHERE match_id = ? ORDER BY created_at",
        (match_id,),
        fetch_all=True
    )

    return [
        {
            "id": e['id'],
            "event_type": e['event_type'],
            "event_data": json.loads(e['event_data']) if e['event_data'] else None,
            "team_id": e['team_id'],
            "player_id": e['player_id'],
            "minute": e['minute'],
            "created_at": e['created_at'],
        }
        for e in events_rows
    ]
