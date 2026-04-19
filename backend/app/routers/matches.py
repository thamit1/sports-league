from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.models import Match, MatchEvent, MatchStatus, UserRole
from app.schemas.schemas import MatchCreate, MatchOut, MatchScoreUpdate, MatchEventCreate

router = APIRouter()


@router.get("/", response_model=List[MatchOut])
def list_matches(
    tournament_id: Optional[int] = Query(None),
    status: Optional[MatchStatus] = Query(None),
    sport_id: Optional[int] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Match)
    if tournament_id:
        q = q.filter(Match.tournament_id == tournament_id)
    if status:
        q = q.filter(Match.status == status)
    if sport_id:
        q = q.filter(Match.sport_id == sport_id)
    return q.order_by(Match.scheduled_at.desc()).offset(skip).limit(limit).all()


@router.post("/", response_model=MatchOut, status_code=201)
def create_match(
    payload: MatchCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN, UserRole.CLUB_MANAGER)),
):
    if payload.team_a_id == payload.team_b_id:
        raise HTTPException(status_code=400, detail="Teams must be different")
    match = Match(**payload.model_dump())
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.patch("/{match_id}/score")
def update_score(
    match_id: int,
    payload: MatchScoreUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN,
        UserRole.CLUB_MANAGER, UserRole.OFFICIAL
    )),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    match.score_a = payload.score_a
    match.score_b = payload.score_b
    if payload.winner_id:
        match.winner_id = payload.winner_id
    if payload.status:
        match.status = payload.status
        if payload.status == MatchStatus.IN_PROGRESS and not match.started_at:
            match.started_at = datetime.utcnow()
        if payload.status == MatchStatus.COMPLETED and not match.ended_at:
            match.ended_at = datetime.utcnow()
    match.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(match)
    return {"message": "Score updated", "match_id": match_id}


@router.post("/{match_id}/events", status_code=201)
def add_event(
    match_id: int,
    payload: MatchEventCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(
        UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN,
        UserRole.CLUB_MANAGER, UserRole.OFFICIAL
    )),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    event = MatchEvent(match_id=match_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"message": "Event recorded", "event_id": event.id}


@router.get("/{match_id}/events")
def get_events(match_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    events = db.query(MatchEvent).filter(MatchEvent.match_id == match_id).order_by(
        MatchEvent.created_at
    ).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "event_data": e.event_data,
            "team_id": e.team_id,
            "player_id": e.player_id,
            "minute": e.minute,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
