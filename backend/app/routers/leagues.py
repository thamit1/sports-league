"""
Leagues — multi-sport competition wrappers.

A league bundles N sports together; each sport is backed by a regular
tournament under the hood, so all existing tournament/match/registration
machinery is reused. The `league_sports` join table records the link.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import UserRole, LeagueStatus
from app.schemas.schemas import (
    LeagueCreate, LeagueUpdate, LeagueOut,
    LeagueSportAdd, LeagueSportOut,
)

router = APIRouter()


def _league_row(league_id: int):
    return execute_query(
        """SELECT l.*,
                  (SELECT name FROM clubs WHERE id = l.organizer_id) AS organizer_name,
                  (SELECT COUNT(*) FROM league_sports WHERE league_id = l.id) AS sport_count
             FROM leagues l
            WHERE l.id = ?""",
        (league_id,), fetch_one=True,
    )


@router.get("", response_model=List[LeagueOut])
@router.get("/", response_model=List[LeagueOut])
def list_leagues(_=Depends(get_current_user)):
    rows = execute_query(
        """SELECT l.*,
                  (SELECT name FROM clubs WHERE id = l.organizer_id) AS organizer_name,
                  (SELECT COUNT(*) FROM league_sports WHERE league_id = l.id) AS sport_count
             FROM leagues l
            ORDER BY COALESCE(l.start_date, l.created_at) DESC""",
        fetch_all=True,
    ) or []
    return rows


@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, _=Depends(get_current_user)):
    row = _league_row(league_id)
    if not row:
        raise HTTPException(status_code=404, detail="League not found")
    return row


@router.post("", response_model=LeagueOut, status_code=201)
@router.post("/", response_model=LeagueOut, status_code=201)
def create_league(payload: LeagueCreate,
                  _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN))):
    club = execute_query("SELECT id FROM clubs WHERE id = ?", (payload.organizer_id,), fetch_one=True)
    if not club:
        raise HTTPException(status_code=400, detail="Organising club not found")
    league_id = execute_query(
        """INSERT INTO leagues (name, organizer_id, status, description,
                                start_date, end_date, venue, max_teams_per_sport,
                                created_at, updated_at)
           VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (payload.name, payload.organizer_id, payload.description,
         payload.start_date.isoformat() if payload.start_date else None,
         payload.end_date.isoformat() if payload.end_date else None,
         payload.venue, payload.max_teams_per_sport),
        return_lastid=True,
    )
    return _league_row(league_id)


@router.patch("/{league_id}", response_model=LeagueOut)
def update_league(league_id: int, payload: LeagueUpdate,
                  _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN))):
    existing = execute_query("SELECT id FROM leagues WHERE id = ?", (league_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="League not found")
    updates = payload.model_dump(exclude_none=True)
    for k in ("start_date", "end_date"):
        if updates.get(k) is not None and not isinstance(updates[k], str):
            updates[k] = updates[k].isoformat()
    if updates.get("status") and updates["status"] not in {s.value for s in LeagueStatus}:
        raise HTTPException(status_code=400, detail=f"Invalid status: {updates['status']}")
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [league_id]
        execute_query(f"UPDATE leagues SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                      tuple(values))
    return _league_row(league_id)


@router.delete("/{league_id}", status_code=204)
def cancel_league(league_id: int,
                  _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN))):
    existing = execute_query("SELECT id FROM leagues WHERE id = ?", (league_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="League not found")
    execute_query(
        "UPDATE leagues SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (league_id,),
    )


# ── Sport-tournaments under a league ────────────────────────────────────────

@router.get("/{league_id}/sports", response_model=List[LeagueSportOut])
def list_league_sports(league_id: int, _=Depends(get_current_user)):
    rows = execute_query(
        """SELECT ls.*,
                  s.name AS sport_name, s.icon AS sport_icon,
                  t.status AS tournament_status,
                  (SELECT COUNT(*) FROM tournament_registrations WHERE tournament_id = ls.tournament_id) AS registered_teams
             FROM league_sports ls
             LEFT JOIN sports s ON s.id = ls.sport_id
             LEFT JOIN tournaments t ON t.id = ls.tournament_id
            WHERE ls.league_id = ?
            ORDER BY s.name""",
        (league_id,), fetch_all=True,
    ) or []
    return rows


@router.post("/{league_id}/sports", response_model=LeagueSportOut, status_code=201)
def add_league_sport(league_id: int, payload: LeagueSportAdd,
                     _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN))):
    league = execute_query("SELECT * FROM leagues WHERE id = ?", (league_id,), fetch_one=True)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    sport = execute_query("SELECT name FROM sports WHERE id = ? AND is_active = 1",
                          (payload.sport_id,), fetch_one=True)
    if not sport:
        raise HTTPException(status_code=400, detail="Sport not found or inactive")
    existing = execute_query(
        "SELECT id FROM league_sports WHERE league_id = ? AND sport_id = ?",
        (league_id, payload.sport_id), fetch_one=True,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Sport already added to this league")

    # Create a backing tournament — mirrors League's start/end so the existing
    # tournament UI continues to work as a per-sport view.
    tournament_id = execute_query(
        """INSERT INTO tournaments
           (name, sport_id, organizer_id, bracket_type, status, max_teams,
            start_date, end_date, venue, description, prize_pool, created_at)
           VALUES (?, ?, ?, ?, 'registration', ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)""",
        (
            f"{league['name']} — {sport['name']}",
            payload.sport_id,
            league['organizer_id'],
            payload.bracket_type or 'round_robin',
            league['max_teams_per_sport'],
            league['start_date'],
            league['end_date'],
            league['venue'],
            f"Sport bracket under league: {league['name']}",
        ),
        return_lastid=True,
    )

    ls_id = execute_query(
        "INSERT INTO league_sports (league_id, sport_id, tournament_id) VALUES (?, ?, ?)",
        (league_id, payload.sport_id, tournament_id),
        return_lastid=True,
    )
    return execute_query(
        """SELECT ls.*,
                  s.name AS sport_name, s.icon AS sport_icon,
                  t.status AS tournament_status,
                  0 AS registered_teams
             FROM league_sports ls
             LEFT JOIN sports s ON s.id = ls.sport_id
             LEFT JOIN tournaments t ON t.id = ls.tournament_id
            WHERE ls.id = ?""",
        (ls_id,), fetch_one=True,
    )


@router.get("/{league_id}/standings")
def league_standings(league_id: int, _=Depends(get_current_user)):
    """
    Aggregate + per-sport standings for the league.

    Per-sport: each registered team's W/D/L count from matches under that sport's
    tournament where status = 'completed'.
    Aggregate: per-club totals across all sports in the league.
    """
    league = execute_query("SELECT id, name FROM leagues WHERE id = ?", (league_id,), fetch_one=True)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    sport_rows = execute_query(
        """SELECT ls.sport_id, ls.tournament_id, s.name AS sport_name, s.icon AS sport_icon
             FROM league_sports ls LEFT JOIN sports s ON s.id = ls.sport_id
            WHERE ls.league_id = ?
            ORDER BY s.name""",
        (league_id,), fetch_all=True,
    ) or []

    per_sport = []
    club_totals = {}    # club_id -> {wins, draws, losses, played}

    for sr in sport_rows:
        teams = execute_query(
            """SELECT t.id, t.name, t.club_id, c.name AS club_name
                 FROM tournament_registrations tr
                 JOIN teams t ON t.id = tr.team_id
                 LEFT JOIN clubs c ON c.id = t.club_id
                WHERE tr.tournament_id = ?""",
            (sr['tournament_id'],), fetch_all=True,
        ) or []
        team_stats = {t['id']: {**t, 'wins':0, 'draws':0, 'losses':0, 'played':0} for t in teams}

        matches = execute_query(
            """SELECT id, team_a_id, team_b_id, winner_id
                 FROM matches
                WHERE tournament_id = ? AND status = 'completed'""",
            (sr['tournament_id'],), fetch_all=True,
        ) or []
        for m in matches:
            for side in (m['team_a_id'], m['team_b_id']):
                if side in team_stats:
                    team_stats[side]['played'] += 1
            if m['winner_id'] is None:
                for side in (m['team_a_id'], m['team_b_id']):
                    if side in team_stats:
                        team_stats[side]['draws'] += 1
            else:
                if m['winner_id'] in team_stats:
                    team_stats[m['winner_id']]['wins'] += 1
                loser = m['team_b_id'] if m['winner_id'] == m['team_a_id'] else m['team_a_id']
                if loser in team_stats:
                    team_stats[loser]['losses'] += 1

        # Sort standings: wins desc, then draws desc, then played desc
        sorted_teams = sorted(team_stats.values(),
                              key=lambda t: (-t['wins'], -t['draws'], -t['played'], t['name']))
        # Add rank
        for idx, t in enumerate(sorted_teams, start=1):
            t['rank'] = idx
            # Roll up into club aggregate
            club_id = t.get('club_id')
            if club_id is not None:
                ct = club_totals.setdefault(club_id, {
                    'club_id': club_id, 'club_name': t.get('club_name'),
                    'wins': 0, 'draws': 0, 'losses': 0, 'played': 0,
                })
                ct['wins']   += t['wins']
                ct['draws']  += t['draws']
                ct['losses'] += t['losses']
                ct['played'] += t['played']

        per_sport.append({
            'sport_id': sr['sport_id'],
            'sport_name': sr['sport_name'],
            'sport_icon': sr['sport_icon'],
            'tournament_id': sr['tournament_id'],
            'standings': sorted_teams,
        })

    aggregate = sorted(club_totals.values(),
                       key=lambda c: (-c['wins'], -c['draws'], -c['played'], c['club_name'] or ''))
    for idx, c in enumerate(aggregate, start=1):
        c['rank'] = idx

    return {
        'league_id': league_id,
        'league_name': league['name'],
        'aggregate': aggregate,
        'per_sport': per_sport,
    }


@router.delete("/{league_id}/sports/{sport_id}", status_code=204)
def remove_league_sport(league_id: int, sport_id: int,
                        _=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.CLUB_ADMIN))):
    """Removes the league/sport link AND soft-cancels the backing tournament."""
    row = execute_query(
        "SELECT tournament_id FROM league_sports WHERE league_id = ? AND sport_id = ?",
        (league_id, sport_id), fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="This sport is not part of the league")
    execute_query(
        "DELETE FROM league_sports WHERE league_id = ? AND sport_id = ?",
        (league_id, sport_id),
    )
    execute_query(
        "UPDATE tournaments SET status = 'cancelled' WHERE id = ?",
        (row['tournament_id'],),
    )
