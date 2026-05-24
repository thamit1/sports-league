from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import Sport, UserRole
from app.schemas.schemas import SportOut, SportCreate, SportUpdate
import json

router = APIRouter()

# Default sports to seed on first run
DEFAULT_SPORTS = [
    {"name": "Football",     "category": "team",      "max_team_size": 11, "min_team_size": 7,  "icon": "⚽"},
    {"name": "Cricket",      "category": "team",      "max_team_size": 11, "min_team_size": 11, "icon": "🏏"},
    {"name": "Basketball",   "category": "team",      "max_team_size": 5,  "min_team_size": 5,  "icon": "🏀"},
    {"name": "Volleyball",   "category": "team",      "max_team_size": 6,  "min_team_size": 6,  "icon": "🏐"},
    {"name": "Tennis",       "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🎾"},
    {"name": "Badminton",    "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏸"},
    {"name": "Table Tennis", "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏓"},
    {"name": "Pickleball",   "category": "racket",    "max_team_size": 2,  "min_team_size": 1,  "icon": "🏓"},
    {"name": "Snooker",      "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎱"},
    {"name": "Billiards",    "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎱"},
    {"name": "Darts",        "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🎯"},
    {"name": "Archery",      "category": "precision", "max_team_size": 1,  "min_team_size": 1,  "icon": "🏹"},
    {"name": "Chess",        "category": "other",     "max_team_size": 1,  "min_team_size": 1,  "icon": "♟️"},
    {"name": "Carrom",       "category": "other",     "max_team_size": 2,  "min_team_size": 1,  "icon": "🎯"},
    {"name": "Swimming",     "category": "aquatic",   "max_team_size": 1,  "min_team_size": 1,  "icon": "🏊"},
    {"name": "Rowing",       "category": "aquatic",   "max_team_size": 8,  "min_team_size": 1,  "icon": "🚣"},
    {"name": "Foosball",     "category": "other",     "max_team_size": 2,  "min_team_size": 1,  "icon": "⚽"},
    {"name": "Tug of War",   "category": "team",      "max_team_size": 8,  "min_team_size": 4,  "icon": "💪"},
]


@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def list_sports(_=Depends(get_current_user)):
    sports_rows = execute_query(
        "SELECT * FROM sports WHERE is_active = 1",
        fetch_all=True
    )

    if not sports_rows:
        # Seed on first call
        for sport in DEFAULT_SPORTS:
            execute_query(
                """INSERT INTO sports (name, category, max_team_size, min_team_size, icon, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (
                    sport['name'],
                    sport['category'],
                    sport['max_team_size'],
                    sport['min_team_size'],
                    sport['icon'],
                )
            )
        sports_rows = execute_query(
            "SELECT * FROM sports WHERE is_active = 1",
            fetch_all=True
        )

    return [
        {
            "id": s['id'],
            "name": s['name'],
            "category": s['category'],
            "max_team_size": s['max_team_size'],
            "min_team_size": s['min_team_size'],
            "scoring_config": json.loads(s['scoring_config']) if s['scoring_config'] else None,
            "is_active": s['is_active'],
            "icon": s['icon'],
        }
        for s in sports_rows
    ]


@router.post("", response_model=dict, status_code=201)
@router.post("/", response_model=dict, status_code=201)
def create_sport(
    payload: SportCreate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    existing = execute_query(
        "SELECT id FROM sports WHERE name = ?",
        (payload.name,),
        fetch_one=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="Sport with this name already exists")

    sport_id = execute_query(
        """INSERT INTO sports (name, category, max_team_size, min_team_size, icon, is_active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (payload.name, payload.category, payload.max_team_size, payload.min_team_size, payload.icon),
        return_lastid=True
    )
    row = execute_query("SELECT * FROM sports WHERE id = ?", (sport_id,), fetch_one=True)
    return {
        "id": row['id'],
        "name": row['name'],
        "category": row['category'],
        "max_team_size": row['max_team_size'],
        "min_team_size": row['min_team_size'],
        "scoring_config": json.loads(row['scoring_config']) if row['scoring_config'] else None,
        "is_active": row['is_active'],
        "icon": row['icon'],
    }


@router.patch("/{sport_id}", response_model=dict)
def update_sport(
    sport_id: int,
    payload: SportUpdate,
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    existing = execute_query("SELECT * FROM sports WHERE id = ?", (sport_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Sport not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [sport_id]
        execute_query(f"UPDATE sports SET {fields} WHERE id = ?", tuple(values))

    row = execute_query("SELECT * FROM sports WHERE id = ?", (sport_id,), fetch_one=True)
    return {
        "id": row['id'], "name": row['name'], "category": row['category'],
        "max_team_size": row['max_team_size'], "min_team_size": row['min_team_size'],
        "scoring_config": json.loads(row['scoring_config']) if row['scoring_config'] else None,
        "is_active": row['is_active'], "icon": row['icon'],
    }


@router.delete("/{sport_id}", status_code=204)
def deactivate_sport(
    sport_id: int,
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    existing = execute_query("SELECT id FROM sports WHERE id = ?", (sport_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Sport not found")
    execute_query("UPDATE sports SET is_active = 0 WHERE id = ?", (sport_id,))


@router.get("/{sport_id}", response_model=dict)
def get_sport(sport_id: int, _=Depends(get_current_user)):
    sport_row = execute_query(
        "SELECT * FROM sports WHERE id = ?",
        (sport_id,),
        fetch_one=True
    )
    if not sport_row:
        raise HTTPException(status_code=404, detail="Sport not found")

    return {
        "id": sport_row['id'],
        "name": sport_row['name'],
        "category": sport_row['category'],
        "max_team_size": sport_row['max_team_size'],
        "min_team_size": sport_row['min_team_size'],
        "scoring_config": json.loads(sport_row['scoring_config']) if sport_row['scoring_config'] else None,
        "is_active": sport_row['is_active'],
        "icon": sport_row['icon'],
    }
