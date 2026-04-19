from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.models import Tournament, TournamentRegistration, TournamentStatus, UserRole
from app.schemas.schemas import TournamentCreate, TournamentOut

router = APIRouter()


@router.get("/", response_model=List[TournamentOut])
def list_tournaments(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Tournament).order_by(Tournament.created_at.desc()).all()


@router.post("/", response_model=TournamentOut, status_code=201)
def create_tournament(
    payload: TournamentCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    t = Tournament(**payload.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/{tournament_id}", response_model=TournamentOut)
def get_tournament(tournament_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return t


@router.post("/{tournament_id}/register", status_code=201)
def register_team(
    tournament_id: int,
    team_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if t.status != TournamentStatus.REGISTRATION:
        raise HTTPException(status_code=400, detail="Tournament is not open for registration")

    existing = db.query(TournamentRegistration).filter(
        TournamentRegistration.tournament_id == tournament_id,
        TournamentRegistration.team_id == team_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team already registered")

    reg_count = db.query(TournamentRegistration).filter(
        TournamentRegistration.tournament_id == tournament_id
    ).count()
    if reg_count >= t.max_teams:
        raise HTTPException(status_code=400, detail="Tournament is full")

    reg = TournamentRegistration(tournament_id=tournament_id, team_id=team_id)
    db.add(reg)
    db.commit()
    return {"message": "Team registered successfully"}


@router.get("/{tournament_id}/teams")
def tournament_teams(tournament_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    regs = db.query(TournamentRegistration).filter(
        TournamentRegistration.tournament_id == tournament_id
    ).all()
    return [
        {
            "team_id": r.team_id,
            "team_name": r.team.name if r.team else None,
            "seed": r.seed,
            "is_approved": r.is_approved,
            "registered_at": r.registered_at.isoformat(),
        }
        for r in regs
    ]


@router.patch("/{tournament_id}/status")
def update_status(
    tournament_id: int,
    status: TournamentStatus,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN)),
):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    t.status = status
    db.commit()
    return {"message": f"Tournament status updated to {status}"}
