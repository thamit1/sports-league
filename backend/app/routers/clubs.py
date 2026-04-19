from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.models import Club, UserRole
from app.schemas.schemas import ClubCreate, ClubUpdate, ClubOut

router = APIRouter()


@router.get("/", response_model=List[ClubOut])
def list_clubs(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Club).filter(Club.is_active == True).all()


@router.post("/", response_model=ClubOut, status_code=201)
def create_club(
    payload: ClubCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    if db.query(Club).filter(Club.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Club code already exists")
    club = Club(**payload.model_dump())
    db.add(club)
    db.commit()
    db.refresh(club)
    return club


@router.get("/{club_id}", response_model=ClubOut)
def get_club(club_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.patch("/{club_id}", response_model=ClubOut)
def update_club(
    club_id: int,
    payload: ClubUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(club, field, value)
    db.commit()
    db.refresh(club)
    return club


@router.delete("/{club_id}", status_code=204)
def deactivate_club(
    club_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN)),
):
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    club.is_active = False
    db.commit()
