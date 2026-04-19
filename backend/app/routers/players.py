from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.models import User, PlayerMembership, UserRole, MembershipStatus
from app.schemas.schemas import UserOut, UserUpdate

router = APIRouter()


@router.get("/", response_model=List[UserOut])
def list_players(
    club_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(User).filter(User.is_active == True)
    if club_id:
        q = q.filter(User.club_id == club_id)
    if search:
        term = f"%{search}%"
        q = q.filter(
            (User.first_name.ilike(term)) |
            (User.last_name.ilike(term)) |
            (User.email.ilike(term)) |
            (User.global_player_id.ilike(term))
        )
    return q.offset(skip).limit(limit).all()


@router.get("/{player_id}", response_model=UserOut)
def get_player(player_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    player = db.query(User).filter(User.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.patch("/{player_id}", response_model=UserOut)
def update_player(
    player_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != player_id and current_user.role not in (
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER
    ):
        raise HTTPException(status_code=403, detail="Not allowed")
    player = db.query(User).filter(User.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(player, field, value)
    db.commit()
    db.refresh(player)
    return player


@router.get("/{player_id}/clubs")
def player_clubs(player_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    memberships = (
        db.query(PlayerMembership)
        .filter(PlayerMembership.player_id == player_id)
        .all()
    )
    return [
        {
            "club_id": m.club_id,
            "club_name": m.club.name if m.club else None,
            "jersey_no": m.jersey_no,
            "position": m.position,
            "status": m.status,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in memberships
    ]
