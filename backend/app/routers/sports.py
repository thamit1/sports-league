from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Sport
from app.schemas.schemas import SportOut

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


@router.get("/", response_model=List[SportOut])
def list_sports(db: Session = Depends(get_db), _=Depends(get_current_user)):
    sports = db.query(Sport).filter(Sport.is_active == True).all()
    if not sports:
        # Seed on first call
        sports = [Sport(**s) for s in DEFAULT_SPORTS]
        db.add_all(sports)
        db.commit()
        for s in sports:
            db.refresh(s)
    return sports


@router.get("/{sport_id}", response_model=SportOut)
def get_sport(sport_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    from fastapi import HTTPException
    sport = db.query(Sport).filter(Sport.id == sport_id).first()
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")
    return sport
