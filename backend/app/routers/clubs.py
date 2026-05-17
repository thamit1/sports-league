from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import Club, UserRole
from app.schemas.schemas import ClubCreate, ClubUpdate, ClubOut
import json

router = APIRouter()


@router.get("/", response_model=List[ClubOut])
def list_clubs(_=Depends(get_current_user)):
    clubs_rows = execute_query(
        "SELECT * FROM clubs WHERE is_active = 1",
        fetch_all=True
    )
    return [Club(
        id=c['id'],
        name=c['name'],
        code=c['code'],
        short_name=c['short_name'],
        description=c['description'],
        logo_url=c['logo_url'],
        primary_color=c['primary_color'],
        secondary_color=c['secondary_color'],
        city=c['city'],
        country=c['country'],
        is_active=c['is_active'],
        created_at=c['created_at'],
        updated_at=c['updated_at'],
    ) for c in clubs_rows]


@router.post("/", response_model=ClubOut, status_code=201)
def create_club(
    payload: ClubCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    existing = execute_query(
        "SELECT id FROM clubs WHERE code = ?",
        (payload.code,),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Club code already exists")

    club_data = payload.model_dump()
    club_id = execute_query(
        """INSERT INTO clubs (name, code, short_name, description, logo_url, primary_color, secondary_color, city, country, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            club_data.get('name'),
            club_data.get('code'),
            club_data.get('short_name'),
            club_data.get('description'),
            club_data.get('logo_url'),
            club_data.get('primary_color', '#1a56db'),
            club_data.get('secondary_color', '#ffffff'),
            club_data.get('city'),
            club_data.get('country', 'India'),
            club_data.get('is_active', True),
        ),
        return_lastid=True
    )

    club_row = execute_query(
        "SELECT * FROM clubs WHERE id = ?",
        (club_id,),
        fetch_one=True
    )

    return Club(
        id=club_row['id'],
        name=club_row['name'],
        code=club_row['code'],
        short_name=club_row['short_name'],
        description=club_row['description'],
        logo_url=club_row['logo_url'],
        primary_color=club_row['primary_color'],
        secondary_color=club_row['secondary_color'],
        city=club_row['city'],
        country=club_row['country'],
        is_active=club_row['is_active'],
        created_at=club_row['created_at'],
        updated_at=club_row['updated_at'],
    )


@router.get("/{club_id}", response_model=ClubOut)
def get_club(club_id: int, _=Depends(get_current_user)):
    club_row = execute_query(
        "SELECT * FROM clubs WHERE id = ?",
        (club_id,),
        fetch_one=True
    )
    if not club_row:
        raise HTTPException(status_code=404, detail="Club not found")

    return Club(
        id=club_row['id'],
        name=club_row['name'],
        code=club_row['code'],
        short_name=club_row['short_name'],
        description=club_row['description'],
        logo_url=club_row['logo_url'],
        primary_color=club_row['primary_color'],
        secondary_color=club_row['secondary_color'],
        city=club_row['city'],
        country=club_row['country'],
        is_active=club_row['is_active'],
        created_at=club_row['created_at'],
        updated_at=club_row['updated_at'],
    )


@router.patch("/{club_id}", response_model=ClubOut)
def update_club(
    club_id: int,
    payload: ClubUpdate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    existing = execute_query(
        "SELECT * FROM clubs WHERE id = ?",
        (club_id,),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Club not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [club_id]
        execute_query(
            f"UPDATE clubs SET {fields} WHERE id = ?",
            tuple(values)
        )

    club_row = execute_query(
        "SELECT * FROM clubs WHERE id = ?",
        (club_id,),
        fetch_one=True
    )

    return Club(
        id=club_row['id'],
        name=club_row['name'],
        code=club_row['code'],
        short_name=club_row['short_name'],
        description=club_row['description'],
        logo_url=club_row['logo_url'],
        primary_color=club_row['primary_color'],
        secondary_color=club_row['secondary_color'],
        city=club_row['city'],
        country=club_row['country'],
        is_active=club_row['is_active'],
        created_at=club_row['created_at'],
        updated_at=club_row['updated_at'],
    )


@router.delete("/{club_id}", status_code=204)
def deactivate_club(
    club_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    existing = execute_query(
        "SELECT id FROM clubs WHERE id = ?",
        (club_id,),
        fetch_one=True
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Club not found")

    execute_query(
        "UPDATE clubs SET is_active = 0 WHERE id = ?",
        (club_id,)
    )
