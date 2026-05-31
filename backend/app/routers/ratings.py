from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from app.core.database import execute_query
from app.core.security import get_current_user, require_roles
from app.models.models import UserRole
from app.schemas.schemas import (
    SportRatingConfigCreate, SportRatingConfigUpdate, SportRatingConfigOut,
    PlayerRatingOut, RatingHistoryOut,
    LeaderboardOut, LeaderboardEntryOut,
    RecalculationJobOut, RecalculationRequest, SeasonResetRequest,
)
from app.services import rating_engine

router = APIRouter()


# ── Visibility helper ─────────────────────────────────────────────────────

def _check_visibility(config_row, current_user) -> bool:
    if config_row is None:
        # No config = admins only (safe default)
        return current_user.role in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value, UserRole.CLUB_MANAGER.value)
    vis = config_row.get('visibility', 'club_members')
    if vis == "public":
        return True
    if vis == "club_members":
        return current_user is not None
    if vis == "admins_only":
        return current_user.role in (UserRole.SUPER_ADMIN.value, UserRole.CLUB_ADMIN.value, UserRole.CLUB_MANAGER.value)
    return False


def _config_for(sport_id: int):
    return execute_query(
        "SELECT * FROM sport_rating_configs WHERE sport_id = ?",
        (sport_id,), fetch_one=True,
    )


def _sport_name_map():
    rows = execute_query("SELECT id, name, icon FROM sports", fetch_all=True) or []
    return {r['id']: r for r in rows}


# ── Admin: SportRatingConfig CRUD ─────────────────────────────────────────

@router.get("/config", response_model=List[SportRatingConfigOut])
@router.get("/config/", response_model=List[SportRatingConfigOut])
def list_configs(_=Depends(require_roles(UserRole.SUPER_ADMIN))):
    rows = execute_query(
        """SELECT c.*, s.name AS sport_name
             FROM sport_rating_configs c
             LEFT JOIN sports s ON s.id = c.sport_id
            ORDER BY s.name""",
        fetch_all=True,
    ) or []
    return rows


@router.get("/config/{sport_id}", response_model=SportRatingConfigOut)
def get_config(sport_id: int, _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    row = execute_query(
        """SELECT c.*, s.name AS sport_name
             FROM sport_rating_configs c
             LEFT JOIN sports s ON s.id = c.sport_id
            WHERE c.sport_id = ?""",
        (sport_id,), fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Config not found for this sport")
    return row


@router.post("/config", response_model=SportRatingConfigOut, status_code=201)
@router.post("/config/", response_model=SportRatingConfigOut, status_code=201)
def create_config(payload: SportRatingConfigCreate,
                  _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    sport = execute_query("SELECT id, name FROM sports WHERE id = ?", (payload.sport_id,), fetch_one=True)
    if not sport:
        raise HTTPException(status_code=400, detail="Sport not found")
    existing = execute_query("SELECT id FROM sport_rating_configs WHERE sport_id = ?", (payload.sport_id,), fetch_one=True)
    if existing:
        raise HTTPException(status_code=409, detail="Config already exists for this sport")

    cid = execute_query(
        """INSERT INTO sport_rating_configs
           (sport_id, provisional_threshold, season_reset_type, season_reset_factor,
            visibility, k_factor_provisional, k_factor_established, k_factor_elite,
            starting_rating, max_rating_change_per_match, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
        (payload.sport_id, payload.provisional_threshold, payload.season_reset_type,
         payload.season_reset_factor, payload.visibility,
         payload.k_factor_provisional, payload.k_factor_established, payload.k_factor_elite,
         payload.starting_rating, payload.max_rating_change_per_match),
        return_lastid=True,
    )
    row = execute_query(
        """SELECT c.*, s.name AS sport_name
             FROM sport_rating_configs c LEFT JOIN sports s ON s.id = c.sport_id
            WHERE c.id = ?""",
        (cid,), fetch_one=True,
    )
    return row


@router.patch("/config/{sport_id}", response_model=SportRatingConfigOut)
def update_config(sport_id: int,
                  payload: SportRatingConfigUpdate,
                  _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    existing = execute_query("SELECT id FROM sport_rating_configs WHERE sport_id = ?", (sport_id,), fetch_one=True)
    if not existing:
        raise HTTPException(status_code=404, detail="Config not found")
    updates = payload.model_dump(exclude_none=True)
    if updates:
        fields = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [sport_id]
        execute_query(f"UPDATE sport_rating_configs SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE sport_id = ?", tuple(values))
    row = execute_query(
        """SELECT c.*, s.name AS sport_name
             FROM sport_rating_configs c LEFT JOIN sports s ON s.id = c.sport_id
            WHERE c.sport_id = ?""",
        (sport_id,), fetch_one=True,
    )
    return row


# ── Admin: Recalculation ──────────────────────────────────────────────────

@router.post("/recalculate", response_model=RecalculationJobOut)
@router.post("/recalculate/", response_model=RecalculationJobOut)
def trigger_recalculation(payload: RecalculationRequest,
                          current_user=Depends(require_roles(UserRole.SUPER_ADMIN))):
    try:
        job_id = rating_engine.run_full_recalculation(payload.sport_id, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recalculation failed: {exc}")
    return _job_with_names(job_id)


@router.get("/jobs", response_model=List[RecalculationJobOut])
@router.get("/jobs/", response_model=List[RecalculationJobOut])
def list_jobs(limit: int = Query(20, ge=1, le=100),
              offset: int = Query(0, ge=0),
              _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    rows = execute_query(
        """SELECT j.*,
                  (u.first_name || ' ' || u.last_name) AS triggered_by_name,
                  s.name AS sport_name
             FROM recalculation_jobs j
             LEFT JOIN users u ON u.id = j.triggered_by_id
             LEFT JOIN sports s ON s.id = j.sport_id
            ORDER BY j.id DESC
            LIMIT ? OFFSET ?""",
        (limit, offset), fetch_all=True,
    ) or []
    return rows


@router.get("/jobs/{job_id}", response_model=RecalculationJobOut)
def get_job(job_id: int, _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    row = _job_with_names(job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


def _job_with_names(job_id: int):
    return execute_query(
        """SELECT j.*,
                  (u.first_name || ' ' || u.last_name) AS triggered_by_name,
                  s.name AS sport_name
             FROM recalculation_jobs j
             LEFT JOIN users u ON u.id = j.triggered_by_id
             LEFT JOIN sports s ON s.id = j.sport_id
            WHERE j.id = ?""",
        (job_id,), fetch_one=True,
    )


# ── Admin: Season reset ──────────────────────────────────────────────────

@router.post("/season-reset/{sport_id}")
def season_reset(sport_id: int,
                 payload: SeasonResetRequest,
                 _=Depends(require_roles(UserRole.SUPER_ADMIN))):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required")
    affected = rating_engine.apply_season_reset(sport_id)
    return {"sport_id": sport_id, "ratings_updated": affected}


# ── Player ratings (visibility enforced) ─────────────────────────────────

def _player_name(player_id: int) -> Optional[str]:
    row = execute_query("SELECT first_name, last_name FROM users WHERE id = ?", (player_id,), fetch_one=True)
    if not row:
        return None
    return f"{row['first_name']} {row['last_name']}"


def _global_rank(player_id: int, sport_id: int, match_type: str):
    row = execute_query(
        """SELECT rank, total_ranked FROM player_rankings
            WHERE player_id = ? AND sport_id = ? AND match_type = ? AND scope = 'global'""",
        (player_id, sport_id, match_type), fetch_one=True,
    )
    if not row:
        return None, None
    return row['rank'], row['total_ranked']


@router.get("/player/{player_id}", response_model=List[PlayerRatingOut])
def player_ratings_all(player_id: int, current_user=Depends(get_current_user)):
    rows = execute_query(
        """SELECT pr.*, s.name AS sport_name, s.icon AS sport_icon
             FROM player_ratings pr
             LEFT JOIN sports s ON s.id = pr.sport_id
            WHERE pr.player_id = ?""",
        (player_id,), fetch_all=True,
    ) or []

    name = _player_name(player_id)
    out: List[dict] = []
    for r in rows:
        cfg = _config_for(r['sport_id'])
        if not _check_visibility(cfg, current_user):
            continue
        rank, total = _global_rank(player_id, r['sport_id'], r['match_type'])
        out.append({
            **r,
            "player_name": name,
            "global_rank": rank,
            "total_ranked": total,
        })
    return out


@router.get("/player/{player_id}/{sport_id}", response_model=List[PlayerRatingOut])
def player_ratings_for_sport(player_id: int, sport_id: int,
                              current_user=Depends(get_current_user)):
    cfg = _config_for(sport_id)
    if not _check_visibility(cfg, current_user):
        raise HTTPException(status_code=403, detail="Ratings not visible for this sport")
    rows = execute_query(
        """SELECT pr.*, s.name AS sport_name, s.icon AS sport_icon
             FROM player_ratings pr
             LEFT JOIN sports s ON s.id = pr.sport_id
            WHERE pr.player_id = ? AND pr.sport_id = ?""",
        (player_id, sport_id), fetch_all=True,
    ) or []
    name = _player_name(player_id)
    result = []
    for r in rows:
        rank, total = _global_rank(player_id, sport_id, r['match_type'])
        result.append({**r, "player_name": name, "global_rank": rank, "total_ranked": total})
    return result


@router.get("/player/{player_id}/{sport_id}/history", response_model=List[RatingHistoryOut])
def player_history(player_id: int, sport_id: int,
                   match_type: str = Query("singles"),
                   limit: int = Query(50, ge=1, le=200),
                   offset: int = Query(0, ge=0),
                   current_user=Depends(get_current_user)):
    cfg = _config_for(sport_id)
    if not _check_visibility(cfg, current_user):
        raise HTTPException(status_code=403, detail="History not visible for this sport")

    rows = execute_query(
        """SELECT h.*,
                  m.team_a_id, m.team_b_id,
                  ta.name AS team_a_name, tb.name AS team_b_name
             FROM rating_history h
             LEFT JOIN matches m ON m.id = h.match_id
             LEFT JOIN teams ta ON ta.id = m.team_a_id
             LEFT JOIN teams tb ON tb.id = m.team_b_id
            WHERE h.player_id = ? AND h.sport_id = ? AND h.match_type = ?
            ORDER BY h.match_played_at DESC, h.id DESC
            LIMIT ? OFFSET ?""",
        (player_id, sport_id, match_type, limit, offset), fetch_all=True,
    ) or []

    # Determine opponent label (the OTHER team's name)
    out = []
    for r in rows:
        # Was the player on team A or B?
        on_a = execute_query(
            "SELECT 1 FROM team_members WHERE team_id = ? AND player_id = ?",
            (r['team_a_id'], player_id), fetch_one=True,
        )
        opponent = r['team_b_name'] if on_a else r['team_a_name']
        out.append({**r, "opponent_label": opponent})
    return out


# ── Leaderboard ───────────────────────────────────────────────────────────

def _trend_for(player_id: int, sport_id: int, match_type: str):
    rows = execute_query(
        """SELECT rating_delta FROM rating_history
            WHERE player_id = ? AND sport_id = ? AND match_type = ?
            ORDER BY match_played_at DESC, id DESC LIMIT 5""",
        (player_id, sport_id, match_type), fetch_all=True,
    ) or []
    if not rows:
        return None
    return round(sum(r['rating_delta'] for r in rows) / len(rows), 2)


@router.get("/leaderboard/{sport_id}", response_model=LeaderboardOut)
def leaderboard(sport_id: int,
                match_type: str = Query("singles"),
                scope: str = Query("global"),
                scope_value: Optional[str] = Query(None),
                limit: int = Query(50, ge=1, le=100),
                offset: int = Query(0, ge=0),
                current_user=Depends(get_current_user)):
    cfg = _config_for(sport_id)
    if not _check_visibility(cfg, current_user):
        raise HTTPException(status_code=403, detail="Leaderboard not visible for this sport")

    sport = execute_query("SELECT id, name FROM sports WHERE id = ?", (sport_id,), fetch_one=True)
    if not sport:
        raise HTTPException(status_code=404, detail="Sport not found")

    sql = """SELECT pr_rank.rank, pr_rank.rating, pr_rank.total_ranked,
                    pr.player_id, pr.peak_rating, pr.matches_played, pr.is_provisional,
                    (u.first_name || ' ' || u.last_name) AS player_name
               FROM player_rankings pr_rank
               JOIN player_ratings pr ON pr.player_id = pr_rank.player_id
                                      AND pr.sport_id = pr_rank.sport_id
                                      AND pr.match_type = pr_rank.match_type
               LEFT JOIN users u ON u.id = pr_rank.player_id
              WHERE pr_rank.sport_id = ? AND pr_rank.match_type = ? AND pr_rank.scope = ?"""
    params = [sport_id, match_type, scope]
    if scope == "global":
        sql += " AND pr_rank.scope_value IS NULL"
    else:
        if scope_value is None:
            raise HTTPException(status_code=400, detail="scope_value is required for this scope")
        sql += " AND pr_rank.scope_value = ?"
        params.append(scope_value)
    sql += " ORDER BY pr_rank.rank ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = execute_query(sql, tuple(params), fetch_all=True) or []
    total = rows[0]['total_ranked'] if rows else 0

    entries = []
    for r in rows:
        entries.append({
            "rank": r['rank'],
            "player_id": r['player_id'],
            "player_name": r['player_name'],
            "rating": r['rating'],
            "peak_rating": r['peak_rating'],
            "matches_played": r['matches_played'],
            "is_provisional": bool(r['is_provisional']),
            "trend": _trend_for(r['player_id'], sport_id, match_type),
        })

    return {
        "sport_id": sport_id,
        "sport_name": sport['name'],
        "match_type": match_type,
        "scope": scope,
        "scope_value": scope_value,
        "total_ranked": total,
        "entries": entries,
        "generated_at": datetime.utcnow(),
    }


@router.get("/leaderboard/{sport_id}/club/{club_id}", response_model=LeaderboardOut)
def leaderboard_club(sport_id: int, club_id: int,
                     match_type: str = Query("singles"),
                     limit: int = Query(50, ge=1, le=100),
                     offset: int = Query(0, ge=0),
                     current_user=Depends(get_current_user)):
    return leaderboard(sport_id, match_type, "club", str(club_id), limit, offset, current_user)
