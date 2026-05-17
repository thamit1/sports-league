from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.database import execute_query
from app.core.security import get_current_user
from app.models.models import Sport
from app.schemas.schemas import SportOut
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
