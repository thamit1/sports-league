from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import Team, TeamMember, UserRole
from app.schemas.schemas import TeamCreate, TeamOut, TeamMemberAdd, TeamUpdate

router = APIRouter()


@router.get("", response_model=List[dict])
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


@router.post("", response_model=dict, status_code=201)
@router.post("/", response_model=dict, status_code=201)
def create_team(
    payload: TeamCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    team_data = payload.model_dump()
    team_id = execute_query(
        """INSERT INTO teams (name, club_id, sport_id, captain_id, age_group, division, logo_url, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)""",
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


@router.patch("/{team_id}", response_model=dict)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    existing = execute_query("SELECT * FROM teams WHERE id = ?", (team_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Team not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [team_id]
        execute_query(f"UPDATE teams SET {fields} WHERE id = ?", tuple(values))

    row = execute_query("SELECT * FROM teams WHERE id = ?", (team_id,), fetch_one=True)
    return {
        "id": row['id'], "name": row['name'], "club_id": row['club_id'], "sport_id": row['sport_id'],
        "captain_id": row['captain_id'], "age_group": row['age_group'], "division": row['division'],
        "logo_url": row['logo_url'], "is_active": row['is_active'], "created_at": row['created_at'],
    }


@router.delete("/{team_id}", status_code=204)
def deactivate_team(
    team_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query("SELECT id FROM teams WHERE id = ?", (team_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Team not found")
    execute_query("UPDATE teams SET is_active = 0 WHERE id = ?", (team_id,))


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


@router.get("/{team_id}/captains")
def list_captains(team_id: int, _=Depends(get_current_user)):
    team = execute_query("SELECT id FROM teams WHERE id = ?", (team_id,), fetch_one=True)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return execute_query(
        """SELECT a.id, a.user_id, a.granted_at, a.granted_by,
                  (u.first_name || ' ' || u.last_name) AS user_name,
                  u.email
             FROM user_assignments a
             LEFT JOIN users u ON u.id = a.user_id
            WHERE a.scope_type = 'team' AND a.scope_id = ? AND a.role = 'captain'
            ORDER BY a.granted_at""",
        (team_id,), fetch_all=True,
    ) or []


@router.post("/{team_id}/captains", status_code=201)
def add_captain(
    team_id: int,
    payload: dict,
    current_user=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    team = execute_query("SELECT id FROM teams WHERE id = ?", (team_id,), fetch_one=True)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    user = execute_query("SELECT id FROM users WHERE id = ? AND is_active = 1", (user_id,), fetch_one=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = execute_query(
        "SELECT id FROM user_assignments WHERE user_id = ? AND scope_type = 'team' AND scope_id = ? AND role = 'captain'",
        (user_id, team_id), fetch_one=True,
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a captain of this team")
    execute_query(
        """INSERT INTO user_assignments (user_id, scope_type, scope_id, role, granted_by, granted_at)
           VALUES (?, 'team', ?, 'captain', ?, CURRENT_TIMESTAMP)""",
        (user_id, team_id, current_user.id),
    )
    return {"message": "Captain assigned"}


@router.delete("/{team_id}/captains/{user_id}", status_code=204)
def remove_captain(
    team_id: int,
    user_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    existing = execute_query(
        "SELECT id FROM user_assignments WHERE user_id = ? AND scope_type = 'team' AND scope_id = ? AND role = 'captain'",
        (user_id, team_id), fetch_one=True,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Not a captain of this team")
    execute_query("DELETE FROM user_assignments WHERE id = ?", (existing['id'],))


@router.get("/captain/mine")
@router.get("/captain/mine/")
def my_captain_teams(current_user=Depends(get_current_user)):
    """Teams the current user is a captain of, with light sport/club info for the dashboard."""
    rows = execute_query(
        """SELECT t.*, s.name AS sport_name, s.icon AS sport_icon,
                  c.name AS club_name, c.short_name AS club_short_name
             FROM user_assignments a
             JOIN teams t ON t.id = a.scope_id
             LEFT JOIN sports s ON s.id = t.sport_id
             LEFT JOIN clubs c ON c.id = t.club_id
            WHERE a.user_id = ? AND a.scope_type = 'team' AND a.role = 'captain'
              AND t.is_active = 1
            ORDER BY t.name""",
        (current_user.id,), fetch_all=True,
    ) or []
    return rows


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
