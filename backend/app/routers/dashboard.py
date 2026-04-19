from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import Club, User, Team, Match, Tournament, Sport, MatchStatus, TournamentStatus

router = APIRouter()


@router.get("/stats")
def global_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return {
        "clubs":           db.query(Club).filter(Club.is_active == True).count(),
        "players":         db.query(User).filter(User.is_active == True).count(),
        "teams":           db.query(Team).filter(Team.is_active == True).count(),
        "sports":          db.query(Sport).filter(Sport.is_active == True).count(),
        "matches_total":   db.query(Match).count(),
        "matches_live":    db.query(Match).filter(Match.status == MatchStatus.IN_PROGRESS).count(),
        "tournaments_active": db.query(Tournament).filter(
            Tournament.status == TournamentStatus.IN_PROGRESS
        ).count(),
    }


@router.get("/recent-matches")
def recent_matches(limit: int = 5, db: Session = Depends(get_db), _=Depends(get_current_user)):
    matches = (
        db.query(Match)
        .order_by(Match.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "sport": m.sport.name if m.sport else None,
            "team_a": m.team_a.name if m.team_a else None,
            "team_b": m.team_b.name if m.team_b else None,
            "score_a": m.score_a,
            "score_b": m.score_b,
            "status": m.status,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
        }
        for m in matches
    ]


@router.get("/recent-tournaments")
def recent_tournaments(limit: int = 5, db: Session = Depends(get_db), _=Depends(get_current_user)):
    tournaments = (
        db.query(Tournament)
        .order_by(Tournament.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "name": t.name,
            "sport": t.sport.name if t.sport else None,
            "status": t.status,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "end_date": t.end_date.isoformat() if t.end_date else None,
        }
        for t in tournaments
    ]
