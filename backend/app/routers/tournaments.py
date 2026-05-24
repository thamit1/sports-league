from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import TournamentStatus, BracketType, UserRole
from app.schemas.schemas import TournamentCreate, TournamentOut, TournamentUpdate

router = APIRouter()


@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def list_tournaments(_=Depends(get_current_user)):
    tournaments_rows = execute_query(
        "SELECT * FROM tournaments ORDER BY created_at DESC",
        fetch_all=True
    )
    return [
        {
            "id": t['id'],
            "name": t['name'],
            "sport_id": t['sport_id'],
            "organizer_id": t['organizer_id'],
            "bracket_type": t['bracket_type'],
            "status": t['status'],
            "max_teams": t['max_teams'],
            "start_date": t['start_date'],
            "end_date": t['end_date'],
            "venue": t['venue'],
            "description": t['description'],
            "prize_pool": t['prize_pool'],
            "created_at": t['created_at'],
        }
        for t in tournaments_rows
    ]


@router.post("", response_model=dict, status_code=201)
@router.post("/", response_model=dict, status_code=201)
def create_tournament(
    payload: TournamentCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    tournament_data = payload.model_dump()
    tournament_id = execute_query(
        """INSERT INTO tournaments
           (name, sport_id, organizer_id, bracket_type, status, max_teams, start_date, end_date, venue, description, prize_pool, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (
            tournament_data.get('name'),
            tournament_data.get('sport_id'),
            tournament_data.get('organizer_id'),
            tournament_data.get('bracket_type', 'single_elimination'),
            tournament_data.get('status', 'draft'),
            tournament_data.get('max_teams', 16),
            tournament_data.get('start_date'),
            tournament_data.get('end_date'),
            tournament_data.get('venue'),
            tournament_data.get('description'),
            tournament_data.get('prize_pool', 0),
        ),
        return_lastid=True
    )

    tournament_row = execute_query(
        "SELECT * FROM tournaments WHERE id = ?",
        (tournament_id,),
        fetch_one=True
    )

    return {
        "id": tournament_row['id'],
        "name": tournament_row['name'],
        "sport_id": tournament_row['sport_id'],
        "organizer_id": tournament_row['organizer_id'],
        "bracket_type": tournament_row['bracket_type'],
        "status": tournament_row['status'],
        "max_teams": tournament_row['max_teams'],
        "start_date": tournament_row['start_date'],
        "end_date": tournament_row['end_date'],
        "venue": tournament_row['venue'],
        "description": tournament_row['description'],
        "prize_pool": tournament_row['prize_pool'],
        "created_at": tournament_row['created_at'],
    }


@router.get("/{tournament_id}", response_model=dict)
def get_tournament(tournament_id: int, _=Depends(get_current_user)):
    tournament_row = execute_query(
        "SELECT * FROM tournaments WHERE id = ?",
        (tournament_id,),
        fetch_one=True
    )
    if not tournament_row:
        raise HTTPException(status_code=404, detail="Tournament not found")

    return {
        "id": tournament_row['id'],
        "name": tournament_row['name'],
        "sport_id": tournament_row['sport_id'],
        "organizer_id": tournament_row['organizer_id'],
        "bracket_type": tournament_row['bracket_type'],
        "status": tournament_row['status'],
        "max_teams": tournament_row['max_teams'],
        "start_date": tournament_row['start_date'],
        "end_date": tournament_row['end_date'],
        "venue": tournament_row['venue'],
        "description": tournament_row['description'],
        "prize_pool": tournament_row['prize_pool'],
        "created_at": tournament_row['created_at'],
    }


@router.post("/{tournament_id}/register", status_code=201)
def register_team(
    tournament_id: int,
    team_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    tournament_row = execute_query(
        "SELECT * FROM tournaments WHERE id = ?",
        (tournament_id,),
        fetch_one=True
    )
    if not tournament_row:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if tournament_row['status'] != TournamentStatus.REGISTRATION.value:
        raise HTTPException(status_code=400, detail="Tournament is not open for registration")

    existing = execute_query(
        "SELECT id FROM tournament_registrations WHERE tournament_id = ? AND team_id = ?",
        (tournament_id, team_id),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Team already registered")

    reg_count = execute_query(
        "SELECT COUNT(*) as count FROM tournament_registrations WHERE tournament_id = ?",
        (tournament_id,),
        fetch_one=True
    )
    if reg_count['count'] >= tournament_row['max_teams']:
        raise HTTPException(status_code=400, detail="Tournament is full")

    execute_query(
        "INSERT INTO tournament_registrations (tournament_id, team_id) VALUES (?, ?)",
        (tournament_id, team_id)
    )
    return {"message": "Team registered successfully"}


@router.get("/{tournament_id}/teams")
def tournament_teams(tournament_id: int, _=Depends(get_current_user)):
    registrations_rows = execute_query(
        """SELECT tr.*, t.name as team_name FROM tournament_registrations tr
           LEFT JOIN teams t ON tr.team_id = t.id
           WHERE tr.tournament_id = ?""",
        (tournament_id,),
        fetch_all=True
    )

    return [
        {
            "team_id": r['team_id'],
            "team_name": r['team_name'],
            "seed": r['seed'],
            "is_approved": r['is_approved'],
            "registered_at": r['registered_at'],
        }
        for r in registrations_rows
    ]


@router.patch("/{tournament_id}", response_model=dict)
def update_tournament(
    tournament_id: int,
    payload: TournamentUpdate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Tournament not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        if isinstance(updates.get("status"), TournamentStatus):
            updates["status"] = updates["status"].value
        if isinstance(updates.get("bracket_type"), BracketType):
            updates["bracket_type"] = updates["bracket_type"].value
        for k in ("start_date", "end_date"):
            if updates.get(k) is not None and not isinstance(updates[k], str):
                updates[k] = updates[k].isoformat()
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [tournament_id]
        execute_query(f"UPDATE tournaments SET {fields} WHERE id = ?", tuple(values))

    row = execute_query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch_one=True)
    return {
        "id": row['id'], "name": row['name'], "sport_id": row['sport_id'],
        "organizer_id": row['organizer_id'], "bracket_type": row['bracket_type'],
        "status": row['status'], "max_teams": row['max_teams'],
        "start_date": row['start_date'], "end_date": row['end_date'],
        "venue": row['venue'], "description": row['description'],
        "prize_pool": row['prize_pool'], "created_at": row['created_at'],
    }


@router.delete("/{tournament_id}", status_code=204)
def cancel_tournament(
    tournament_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query("SELECT id FROM tournaments WHERE id = ?", (tournament_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Tournament not found")
    execute_query("UPDATE tournaments SET status = 'cancelled' WHERE id = ?", (tournament_id,))


@router.delete("/{tournament_id}/teams/{team_id}", status_code=204)
def unregister_team(
    tournament_id: int,
    team_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    existing = execute_query(
        "SELECT id FROM tournament_registrations WHERE tournament_id = ? AND team_id = ?",
        (tournament_id, team_id),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Team is not registered")
    execute_query(
        "DELETE FROM tournament_registrations WHERE tournament_id = ? AND team_id = ?",
        (tournament_id, team_id)
    )


@router.patch("/{tournament_id}/status")
def update_status(
    tournament_id: int,
    status: TournamentStatus,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query(
        "SELECT id FROM tournaments WHERE id = ?",
        (tournament_id,),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Tournament not found")

    execute_query(
        "UPDATE tournaments SET status = ? WHERE id = ?",
        (status.value, tournament_id)
    )
    return {"message": f"Tournament status updated to {status.value}"}
