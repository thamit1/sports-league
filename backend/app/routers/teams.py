from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import Team, TeamMember, UserRole
from app.schemas.schemas import TeamCreate, TeamOut, TeamMemberAdd

router = APIRouter()


@router.get("/", response_model=List[dict])
def list_teams(_=Depends(get_current_user)):
    teams_rows = execute_query(
        "SELECT * FROM teams WHERE is_active = 1",
        fetch_all=True
    )
    return [
        {
            "id": t['id'],
            "name": t['name'],
            "club_id": t['club_id'],
            "sport_id": t['sport_id'],
            "captain_id": t['captain_id'],
            "age_group": t['age_group'],
            "division": t['division'],
            "logo_url": t['logo_url'],
            "is_active": t['is_active'],
            "created_at": t['created_at'],
        }
        for t in teams_rows
    ]


@router.post("/", response_model=dict, status_code=201)
def create_team(
    payload: TeamCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    team_data = payload.model_dump()
    team_id = execute_query(
        """INSERT INTO teams (name, club_id, sport_id, captain_id, age_group, division, logo_url, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            team_data.get('name'),
            team_data.get('club_id'),
            team_data.get('sport_id'),
            team_data.get('captain_id'),
            team_data.get('age_group'),
            team_data.get('division'),
            team_data.get('logo_url'),
        ),
        return_lastid=True
    )

    team_row = execute_query(
        "SELECT * FROM teams WHERE id = ?",
        (team_id,),
        fetch_one=True
    )

    return {
        "id": team_row['id'],
        "name": team_row['name'],
        "club_id": team_row['club_id'],
        "sport_id": team_row['sport_id'],
        "captain_id": team_row['captain_id'],
        "age_group": team_row['age_group'],
        "division": team_row['division'],
        "logo_url": team_row['logo_url'],
        "is_active": team_row['is_active'],
        "created_at": team_row['created_at'],
    }


@router.get("/{team_id}", response_model=dict)
def get_team(team_id: int, _=Depends(get_current_user)):
    team_row = execute_query(
        "SELECT * FROM teams WHERE id = ?",
        (team_id,),
        fetch_one=True
    )
    if not team_row:
        raise HTTPException(status_code=404, detail="Team not found")

    return {
        "id": team_row['id'],
        "name": team_row['name'],
        "club_id": team_row['club_id'],
        "sport_id": team_row['sport_id'],
        "captain_id": team_row['captain_id'],
        "age_group": team_row['age_group'],
        "division": team_row['division'],
        "logo_url": team_row['logo_url'],
        "is_active": team_row['is_active'],
        "created_at": team_row['created_at'],
    }


@router.post("/{team_id}/members", status_code=201)
def add_member(
    team_id: int,
    payload: TeamMemberAdd,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    team = execute_query(
        "SELECT id FROM teams WHERE id = ?",
        (team_id,),
        fetch_one=True
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    existing = execute_query(
        "SELECT id FROM team_members WHERE team_id = ? AND player_id = ? AND is_active = 1",
        (team_id, payload.player_id),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Player already in team")

    member_data = payload.model_dump()
    execute_query(
        """INSERT INTO team_members (team_id, player_id, jersey_no, position, is_active)
           VALUES (?, ?, ?, ?, 1)""",
        (
            team_id,
            member_data.get('player_id'),
            member_data.get('jersey_no'),
            member_data.get('position'),
        )
    )
    return {"message": "Player added to team"}


@router.get("/{team_id}/members")
def list_members(team_id: int, _=Depends(get_current_user)):
    members_rows = execute_query(
        """SELECT tm.*, u.first_name, u.last_name FROM team_members tm
           LEFT JOIN users u ON tm.player_id = u.id
           WHERE tm.team_id = ? AND tm.is_active = 1""",
        (team_id,),
        fetch_all=True
    )

    return [
        {
            "id": m['id'],
            "player_id": m['player_id'],
            "player_name": f"{m['first_name']} {m['last_name']}" if m['first_name'] else None,
            "jersey_no": m['jersey_no'],
            "position": m['position'],
            "joined_at": m['joined_at'],
        }
        for m in members_rows
    ]


@router.delete("/{team_id}/members/{player_id}", status_code=204)
def remove_member(
    team_id: int,
    player_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    member = execute_query(
        "SELECT id FROM team_members WHERE team_id = ? AND player_id = ? AND is_active = 1",
        (team_id, player_id),
        fetch_one=True
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    execute_query(
        "UPDATE team_members SET is_active = 0 WHERE team_id = ? AND player_id = ?",
        (team_id, player_id)
    )
