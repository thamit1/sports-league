import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles, hash_password
from app.models.models import User, PlayerMembership, UserRole, MembershipStatus
from app.schemas.schemas import PlayerCreate

router = APIRouter()


@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def list_players(
    club_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    query = "SELECT * FROM users WHERE is_active = 1"
    params = []

    if current_user.role == UserRole.VIEWER.value:
        query += " AND id = ?"
        params.append(current_user.id)

    if club_id:
        query += " AND club_id = ?"
        params.append(club_id)

    if search:
        term = f"%{search}%"
        query += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR global_player_id LIKE ?)"
        params.extend([term, term, term, term])

    query += f" LIMIT {limit} OFFSET {skip}"

    players_rows = execute_query(query, tuple(params), fetch_all=True)

    return [
        {
            "id": p['id'],
            "email": p['email'],
            "phone": p['phone'],
            "first_name": p['first_name'],
            "last_name": p['last_name'],
            "full_name": f"{p['first_name'] or ''} {p['last_name'] or ''}".strip(),
            "role": (p['role'] or '').lower(),
            "club_id": p['club_id'],
            "global_player_id": p['global_player_id'],
            "avatar_url": p['avatar_url'],
            "date_of_birth": p['date_of_birth'],
            "gender": p['gender'],
            "is_active": p['is_active'],
            "is_verified": p['is_verified'],
            "created_at": p['created_at'],
        }
        for p in players_rows
    ]


@router.post("", response_model=dict)
@router.post("/", response_model=dict)
def create_player(
    payload: PlayerCreate,
    current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    existing = execute_query(
        "SELECT id FROM users WHERE email = ?",
        (payload.email,),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    player_id = execute_query(
        """INSERT INTO users
           (email, password_hash, first_name, last_name, phone, role, club_id, global_player_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload.email,
            hash_password(payload.password),
            payload.first_name,
            payload.last_name,
            payload.phone,
            payload.role.value,
            payload.club_id,
            f"SLMS-{uuid.uuid4().hex[:8].upper()}",
        ),
        return_lastid=True
    )

    player_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (player_id,),
        fetch_one=True
    )

    return {
        "id": player_row['id'],
        "email": player_row['email'],
        "phone": player_row['phone'],
        "first_name": player_row['first_name'],
        "last_name": player_row['last_name'],
        "full_name": f"{player_row['first_name'] or ''} {player_row['last_name'] or ''}".strip(),
        "role": (player_row['role'] or '').lower(),
        "club_id": player_row['club_id'],
        "global_player_id": player_row['global_player_id'],
        "avatar_url": player_row['avatar_url'],
        "date_of_birth": player_row['date_of_birth'],
        "gender": player_row['gender'],
        "is_active": player_row['is_active'],
        "is_verified": player_row['is_verified'],
        "created_at": player_row['created_at'],
    }


@router.get("/{player_id}", response_model=dict)
def get_player(player_id: int, current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.VIEWER.value and current_user.id != player_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    player_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (player_id,),
        fetch_one=True
    )
    if not player_row:
        raise HTTPException(status_code=404, detail="Player not found")

    return {
        "id": player_row['id'],
        "email": player_row['email'],
        "phone": player_row['phone'],
        "first_name": player_row['first_name'],
        "last_name": player_row['last_name'],
        "full_name": f"{player_row['first_name'] or ''} {player_row['last_name'] or ''}".strip(),
        "role": (player_row['role'] or '').lower(),
        "club_id": player_row['club_id'],
        "global_player_id": player_row['global_player_id'],
        "avatar_url": player_row['avatar_url'],
        "date_of_birth": player_row['date_of_birth'],
        "gender": player_row['gender'],
        "is_active": player_row['is_active'],
        "is_verified": player_row['is_verified'],
        "password_reset_required": bool(player_row.get('password_reset_required', 0)),
        "created_at": player_row['created_at'],
    }


@router.patch("/{player_id}", response_model=dict)
def update_player(
    player_id: int,
    payload,
    current_user: User = Depends(get_current_user),
):
    if current_user.id != player_id and current_user.role not in (
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    existing = execute_query(
        "SELECT id FROM users WHERE id = ?",
        (player_id,),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Player not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [player_id]
        execute_query(
            f"UPDATE users SET {fields} WHERE id = ?",
            tuple(values)
        )

    player_row = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (player_id,),
        fetch_one=True
    )

    return {
        "id": player_row['id'],
        "email": player_row['email'],
        "phone": player_row['phone'],
        "first_name": player_row['first_name'],
        "last_name": player_row['last_name'],
        "full_name": f"{player_row['first_name'] or ''} {player_row['last_name'] or ''}".strip(),
        "role": (player_row['role'] or '').lower(),
        "club_id": player_row['club_id'],
        "global_player_id": player_row['global_player_id'],
        "avatar_url": player_row['avatar_url'],
        "date_of_birth": player_row['date_of_birth'],
        "gender": player_row['gender'],
        "is_active": player_row['is_active'],
        "is_verified": player_row['is_verified'],
        "created_at": player_row['created_at'],
    }


@router.get("/{player_id}/clubs")
def player_clubs(player_id: int, _=Depends(get_current_user)):
    memberships_rows = execute_query(
        "SELECT pm.*, c.name as club_name FROM player_memberships pm LEFT JOIN clubs c ON pm.club_id = c.id WHERE pm.player_id = ?",
        (player_id,),
        fetch_all=True
    )

    return [
        {
            "club_id": m['club_id'],
            "club_name": m['club_name'],
            "jersey_no": m['jersey_no'],
            "position": m['position'],
            "status": m['status'],
            "joined_at": m['joined_at'],
        }
        for m in memberships_rows
    ]
