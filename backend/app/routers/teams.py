from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.models import Team, TeamMember, UserRole
from app.schemas.schemas import TeamCreate, TeamOut, TeamMemberAdd

router = APIRouter()


@router.get("/", response_model=List[TeamOut])
def list_teams(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Team).filter(Team.is_active == True).all()


@router.post("/", response_model=TeamOut, status_code=201)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    team = Team(**payload.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("/{team_id}/members", status_code=201)
def add_member(
    team_id: int,
    payload: TeamMemberAdd,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.player_id == payload.player_id,
        TeamMember.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Player already in team")
    member = TeamMember(team_id=team_id, **payload.model_dump())
    db.add(member)
    db.commit()
    return {"message": "Player added to team"}


@router.get("/{team_id}/members")
def list_members(team_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    members = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.is_active == True
    ).all()
    return [
        {
            "id": m.id,
            "player_id": m.player_id,
            "player_name": m.player.full_name if m.player else None,
            "jersey_no": m.jersey_no,
            "position": m.position,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in members
    ]


@router.delete("/{team_id}/members/{player_id}", status_code=204)
def remove_member(
    team_id: int,
    player_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.player_id == player_id,
        TeamMember.is_active == True,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.is_active = False
    db.commit()
