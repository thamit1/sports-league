from fastapi import APIRouter, Depends
from app.core.database import execute_query
from app.core.security import get_current_user
from app.models.models import MatchStatus, TournamentStatus
import json

router = APIRouter()


@router.get("/stats")
def global_stats(_=Depends(get_current_user)):
    clubs_count = execute_query(
        "SELECT COUNT(*) as count FROM clubs WHERE is_active = 1",
        fetch_one=True
    )
    players_count = execute_query(
        "SELECT COUNT(*) as count FROM users WHERE is_active = 1",
        fetch_one=True
    )
    teams_count = execute_query(
        "SELECT COUNT(*) as count FROM teams WHERE is_active = 1",
        fetch_one=True
    )
    sports_count = execute_query(
        "SELECT COUNT(*) as count FROM sports WHERE is_active = 1",
        fetch_one=True
    )
    matches_total = execute_query(
        "SELECT COUNT(*) as count FROM matches",
        fetch_one=True
    )
    matches_live = execute_query(
        "SELECT COUNT(*) as count FROM matches WHERE status = ?",
        (MatchStatus.IN_PROGRESS.value,),
        fetch_one=True
    )
    tournaments_active = execute_query(
        "SELECT COUNT(*) as count FROM tournaments WHERE status = ?",
        (TournamentStatus.IN_PROGRESS.value,),
        fetch_one=True
    )

    return {
        "clubs": clubs_count['count'],
        "players": players_count['count'],
        "teams": teams_count['count'],
        "sports": sports_count['count'],
        "matches_total": matches_total['count'],
        "matches_live": matches_live['count'],
        "tournaments_active": tournaments_active['count'],
    }


@router.get("/recent-matches")
def recent_matches(limit: int = 5, _=Depends(get_current_user)):
    matches_rows = execute_query(
        """SELECT m.*, s.name as sport_name, ta.name as team_a_name, tb.name as team_b_name
           FROM matches m
           LEFT JOIN sports s ON m.sport_id = s.id
           LEFT JOIN teams ta ON m.team_a_id = ta.id
           LEFT JOIN teams tb ON m.team_b_id = tb.id
           ORDER BY m.created_at DESC
           LIMIT ?""",
        (limit,),
        fetch_all=True
    )

    return [
        {
            "id": m['id'],
            "sport": m['sport_name'],
            "team_a": m['team_a_name'],
            "team_b": m['team_b_name'],
            "score_a": json.loads(m['score_a']) if m['score_a'] else None,
            "score_b": json.loads(m['score_b']) if m['score_b'] else None,
            "status": m['status'],
            "scheduled_at": m['scheduled_at'],
        }
        for m in matches_rows
    ]


@router.get("/recent-tournaments")
def recent_tournaments(limit: int = 5, _=Depends(get_current_user)):
    tournaments_rows = execute_query(
        """SELECT t.*, s.name as sport_name
           FROM tournaments t
           LEFT JOIN sports s ON t.sport_id = s.id
           ORDER BY t.created_at DESC
           LIMIT ?""",
        (limit,),
        fetch_all=True
    )

    return [
        {
            "id": t['id'],
            "name": t['name'],
            "sport": t['sport_name'],
            "status": t['status'],
            "start_date": t['start_date'],
            "end_date": t['end_date'],
        }
        for t in tournaments_rows
    ]
