"""
Rating engine — DUPR-style Elo ratings on a 0–100 scale.

Pure service: no FastAPI imports. Uses the project's raw-SQL helper
(`execute_query`) to read/write rows. All datetimes are UTC ISO strings.
All rating values are rounded to 2 decimal places before storage.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

from app.core.database import execute_query

logger = logging.getLogger("slms.ratings")


# ── Sport-name groupings for score-margin handling ─────────────────────────
POINT_RATIO_SPORTS = {"Badminton", "Table Tennis", "Pickleball", "Tennis", "Snooker", "Billiards", "Carrom", "Darts", "Archery"}
GOAL_DIFF_SPORTS   = {"Football", "Basketball", "Volleyball", "Foosball"}
TIME_INVERTED      = {"Swimming", "Rowing"}
CRICKET            = {"Cricket"}
CHESS              = {"Chess"}
BINARY_ONLY        = {"Tug of War"}

# Sports where doubles is plausible (used by the recalculation classifier).
DOUBLES_CAPABLE = {
    "Badminton", "Tennis", "Table Tennis", "Pickleball", "Volleyball",
    "Rowing", "Tug of War", "Cricket", "Football", "Basketball",
}


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


def _coerce_score(value):
    """Best-effort coercion of a stored score to a number, or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict):
        # legacy/score-update dicts: try a common 'total' or 'points' field
        for key in ("total", "points", "value", "score"):
            if key in value:
                return _coerce_score(value[key])
        return None
    return None


# ── Pure math helpers ──────────────────────────────────────────────────────

def calculate_expected_score(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected score, scaled for a 0–100 rating range."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 40.0))


def calculate_score_margin(sport_name: str, score_a, score_b) -> Tuple[float, float]:
    """
    Return (actual_score_a, actual_score_b) each in [0.0, 1.0].

    Falls back to a binary win/loss/draw when scores are missing or
    cannot be coerced to numbers.
    """
    a = _coerce_score(score_a)
    b = _coerce_score(score_b)

    # Chess: scores are already 1 / 0.5 / 0 outcomes
    if sport_name in CHESS and a is not None and b is not None:
        return float(a), float(b)

    # Binary-only sports
    if sport_name in BINARY_ONLY:
        if a is None or b is None:
            return 0.5, 0.5
        if a > b:
            return 1.0, 0.0
        if b > a:
            return 0.0, 1.0
        return 0.5, 0.5

    # Anything missing → fallback to binary
    if a is None or b is None:
        return 0.5, 0.5

    # Time-inverted sports: lower score wins
    if sport_name in TIME_INVERTED:
        if a + b <= 0:
            return 0.5, 0.5
        return b / (a + b), a / (a + b)

    # Goal/point differential with soft cap at 10
    if sport_name in GOAL_DIFF_SPORTS:
        diff = abs(a - b)
        margin = min(diff, 10) / 10.0 * 0.5
        if a > b:
            return 0.5 + margin, 0.5 - margin
        if b > a:
            return 0.5 - margin, 0.5 + margin
        return 0.5, 0.5

    # Cricket: run differential with soft cap at 100
    if sport_name in CRICKET:
        diff = abs(a - b)
        margin = min(diff, 100) / 100.0 * 0.5
        if a > b:
            return 0.5 + margin, 0.5 - margin
        if b > a:
            return 0.5 - margin, 0.5 + margin
        return 0.5, 0.5

    # Points-based ratio (default for racket / precision sports)
    if sport_name in POINT_RATIO_SPORTS:
        if a + b <= 0:
            return 0.5, 0.5
        return a / (a + b), b / (a + b)

    # Default fallback: binary win/loss/draw
    if a > b:
        return 1.0, 0.0
    if b > a:
        return 0.0, 1.0
    return 0.5, 0.5


def get_k_factor(provisional_threshold: int, k_prov: float, k_est: float, k_elite: float,
                 current_rating: float, matches_played: int) -> float:
    if matches_played < provisional_threshold:
        return k_prov
    if current_rating > 75.0:
        return k_elite
    return k_est


def calculate_new_rating(old_rating: float, k_factor: float, actual_score: float,
                         expected_score: float, max_change: float) -> float:
    delta = k_factor * (actual_score - expected_score)
    delta = max(-max_change, min(max_change, delta))
    new_rating = old_rating + delta
    new_rating = max(0.0, min(100.0, new_rating))
    return round(new_rating, 2)


# ── DB helpers ─────────────────────────────────────────────────────────────

def get_or_create_player_rating(player_id: int, sport_id: int, match_type: str,
                                 starting_rating: float) -> dict:
    row = execute_query(
        "SELECT * FROM player_ratings WHERE player_id = ? AND sport_id = ? AND match_type = ?",
        (player_id, sport_id, match_type),
        fetch_one=True,
    )
    if row:
        return row

    now = _utcnow_iso()
    execute_query(
        """INSERT INTO player_ratings
           (player_id, sport_id, match_type, rating, peak_rating, matches_played,
            matches_won, matches_drawn, matches_lost, is_provisional, is_active,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 1, 1, ?, ?)""",
        (player_id, sport_id, match_type,
         float(starting_rating), float(starting_rating), now, now),
        return_lastid=True,
    )
    return execute_query(
        "SELECT * FROM player_ratings WHERE player_id = ? AND sport_id = ? AND match_type = ?",
        (player_id, sport_id, match_type),
        fetch_one=True,
    )


def _get_team_roster(team_id: int):
    return execute_query(
        "SELECT player_id FROM team_members WHERE team_id = ? AND is_active = 1",
        (team_id,), fetch_all=True,
    ) or []


def _update_player_rating_row(rating_row, new_rating: float, won: bool, drew: bool,
                              match_played_at: Optional[str]):
    peak = max(rating_row['peak_rating'], new_rating)
    matches_played = rating_row['matches_played'] + 1
    matches_won    = rating_row['matches_won']    + (1 if won else 0)
    matches_drawn  = rating_row['matches_drawn']  + (1 if drew else 0)
    matches_lost   = rating_row['matches_lost']   + (1 if (not won and not drew) else 0)
    now = _utcnow_iso()
    execute_query(
        """UPDATE player_ratings SET
              rating = ?, peak_rating = ?,
              matches_played = ?, matches_won = ?, matches_drawn = ?, matches_lost = ?,
              is_provisional = CASE WHEN ? < (SELECT provisional_threshold FROM sport_rating_configs WHERE sport_id = player_ratings.sport_id) THEN 1 ELSE 0 END,
              last_match_at = ?, last_calculated_at = ?, updated_at = ?
           WHERE id = ?""",
        (new_rating, peak,
         matches_played, matches_won, matches_drawn, matches_lost,
         matches_played, match_played_at or now, now, now,
         rating_row['id']),
    )


def _insert_history(player_id: int, sport_id: int, match_id: int, match_type: str,
                    rating_before: float, rating_after: float, expected: float,
                    actual: float, opponent_rating: float, k: float,
                    match_played_at: Optional[str]):
    execute_query(
        """INSERT INTO rating_history
           (player_id, sport_id, match_id, match_type, rating_before, rating_after,
            rating_delta, expected_score, actual_score, opponent_rating_at_time,
            k_factor_used, match_played_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (player_id, sport_id, match_id, match_type,
         round(rating_before, 2), round(rating_after, 2),
         round(rating_after - rating_before, 2),
         round(expected, 4), round(actual, 4),
         round(opponent_rating, 2), round(k, 2),
         match_played_at, _utcnow_iso()),
    )


# ── Match processing ───────────────────────────────────────────────────────

def process_single_match(match: dict, match_type: str, config: dict, sport_name: str) -> dict:
    """
    Apply rating updates for one completed match.

    `match` and `config` are dict rows (from execute_query / dict_factory).
    """
    team_a_roster = _get_team_roster(match['team_a_id'])
    team_b_roster = _get_team_roster(match['team_b_id'])
    if not team_a_roster or not team_b_roster:
        return {"skipped": True, "reason": "empty roster",
                "players_updated": 0, "pairings_processed": 0}

    actual_a, actual_b = calculate_score_margin(sport_name, match.get('score_a'), match.get('score_b'))
    starting = config['starting_rating']
    max_change = config['max_rating_change_per_match']
    prov_t = config['provisional_threshold']
    k_prov = config['k_factor_provisional']
    k_est  = config['k_factor_established']
    k_elite = config['k_factor_elite']

    match_played_at = match.get('scheduled_at') or match.get('ended_at')
    players_updated = 0
    pairings = 0

    if match_type == "doubles":
        # Aggregate (mean) team rating drives the opponent for each player
        a_ratings = [get_or_create_player_rating(p['player_id'], match['sport_id'], "doubles", starting)
                     for p in team_a_roster]
        b_ratings = [get_or_create_player_rating(p['player_id'], match['sport_id'], "doubles", starting)
                     for p in team_b_roster]
        team_a_avg = sum(r['rating'] for r in a_ratings) / len(a_ratings)
        team_b_avg = sum(r['rating'] for r in b_ratings) / len(b_ratings)

        for r in a_ratings:
            old = r['rating']
            k = get_k_factor(prov_t, k_prov, k_est, k_elite, old, r['matches_played'])
            expected = calculate_expected_score(old, team_b_avg)
            new = calculate_new_rating(old, k, actual_a, expected, max_change)
            won = actual_a > actual_b
            drew = actual_a == actual_b
            _update_player_rating_row(r, new, won, drew, match_played_at)
            _insert_history(r['player_id'], match['sport_id'], match['id'], "doubles",
                            old, new, expected, actual_a, team_b_avg, k, match_played_at)
            players_updated += 1
            pairings += 1

        for r in b_ratings:
            old = r['rating']
            k = get_k_factor(prov_t, k_prov, k_est, k_elite, old, r['matches_played'])
            expected = calculate_expected_score(old, team_a_avg)
            new = calculate_new_rating(old, k, actual_b, expected, max_change)
            won = actual_b > actual_a
            drew = actual_a == actual_b
            _update_player_rating_row(r, new, won, drew, match_played_at)
            _insert_history(r['player_id'], match['sport_id'], match['id'], "doubles",
                            old, new, expected, actual_b, team_a_avg, k, match_played_at)
            players_updated += 1
            pairings += 1
        return {"players_updated": players_updated, "pairings_processed": pairings}

    # Singles: every player on team A is paired against every player on team B
    for pa in team_a_roster:
        ra = get_or_create_player_rating(pa['player_id'], match['sport_id'], "singles", starting)
        for pb in team_b_roster:
            rb = get_or_create_player_rating(pb['player_id'], match['sport_id'], "singles", starting)
            old_a, old_b = ra['rating'], rb['rating']
            ka = get_k_factor(prov_t, k_prov, k_est, k_elite, old_a, ra['matches_played'])
            kb = get_k_factor(prov_t, k_prov, k_est, k_elite, old_b, rb['matches_played'])
            e_a = calculate_expected_score(old_a, old_b)
            e_b = 1.0 - e_a
            new_a = calculate_new_rating(old_a, ka, actual_a, e_a, max_change)
            new_b = calculate_new_rating(old_b, kb, actual_b, e_b, max_change)

            won_a = actual_a > actual_b
            won_b = actual_b > actual_a
            drew  = actual_a == actual_b
            _update_player_rating_row(ra, new_a, won_a, drew, match_played_at)
            _update_player_rating_row(rb, new_b, won_b, drew, match_played_at)
            _insert_history(pa['player_id'], match['sport_id'], match['id'], "singles",
                            old_a, new_a, e_a, actual_a, old_b, ka, match_played_at)
            _insert_history(pb['player_id'], match['sport_id'], match['id'], "singles",
                            old_b, new_b, e_b, actual_b, old_a, kb, match_played_at)

            # Refresh local cache so subsequent pairings see the latest values
            ra = execute_query("SELECT * FROM player_ratings WHERE id = ?", (ra['id'],), fetch_one=True)
            players_updated += 2
            pairings += 1
    return {"players_updated": players_updated, "pairings_processed": pairings}


def _classify_match_type(sport_name: str, team_a_size: int, team_b_size: int) -> str:
    if team_a_size == 1 and team_b_size == 1:
        return "singles"
    if sport_name in DOUBLES_CAPABLE:
        return "doubles"
    return "singles"


def _sport_row(sport_id: int):
    return execute_query("SELECT * FROM sports WHERE id = ?", (sport_id,), fetch_one=True)


def _config_row(sport_id: int):
    return execute_query("SELECT * FROM sport_rating_configs WHERE sport_id = ? AND is_active = 1",
                         (sport_id,), fetch_one=True)


# ── Recalculation orchestration ────────────────────────────────────────────

def run_full_recalculation(sport_id: Optional[int], triggered_by_user_id: int) -> int:
    """
    Reset and replay all completed matches in chronological order.

    Returns the recalculation_jobs.id. Raises on fatal error after marking
    the job 'failed'.
    """
    now = _utcnow_iso()
    job_id = execute_query(
        """INSERT INTO recalculation_jobs
           (triggered_by_id, sport_id, status, started_at, created_at)
           VALUES (?, ?, 'running', ?, ?)""",
        (triggered_by_user_id, sport_id, now, now),
        return_lastid=True,
    )
    try:
        if sport_id is None:
            sport_rows = execute_query(
                "SELECT id FROM sports WHERE is_active = 1", fetch_all=True
            ) or []
            sport_ids = [r['id'] for r in sport_rows]
        else:
            sport_ids = [sport_id]

        total_matches = 0
        total_players = 0

        for sid in sport_ids:
            config = _config_row(sid)
            if not config:
                logger.warning("Skipping sport %s — no rating config", sid)
                continue
            sport = _sport_row(sid)
            if not sport:
                continue

            # Wipe history & reset ratings for this sport
            execute_query("DELETE FROM rating_history WHERE sport_id = ?", (sid,))
            execute_query(
                """UPDATE player_ratings SET
                     rating = ?, peak_rating = ?,
                     matches_played = 0, matches_won = 0, matches_drawn = 0, matches_lost = 0,
                     is_provisional = 1, last_match_at = NULL, last_calculated_at = NULL,
                     updated_at = ?
                   WHERE sport_id = ?""",
                (config['starting_rating'], config['starting_rating'], _utcnow_iso(), sid),
            )

            matches = execute_query(
                """SELECT * FROM matches
                   WHERE sport_id = ? AND status = 'completed'
                   ORDER BY COALESCE(scheduled_at, ended_at, created_at) ASC""",
                (sid,), fetch_all=True,
            ) or []

            for m in matches:
                a_size = len(_get_team_roster(m['team_a_id']))
                b_size = len(_get_team_roster(m['team_b_id']))
                if a_size == 0 or b_size == 0:
                    continue
                match_type = _classify_match_type(sport['name'], a_size, b_size)
                result = process_single_match(m, match_type, config, sport['name'])
                if not result.get("skipped"):
                    total_matches += 1
                    total_players += result.get("players_updated", 0)

        compute_rankings(sport_id)

        execute_query(
            """UPDATE recalculation_jobs SET
                 status = 'completed', matches_processed = ?, players_updated = ?, completed_at = ?
               WHERE id = ?""",
            (total_matches, total_players, _utcnow_iso(), job_id),
        )
        return job_id
    except Exception as exc:
        logger.exception("Recalculation job %s failed", job_id)
        execute_query(
            "UPDATE recalculation_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
            (str(exc), _utcnow_iso(), job_id),
        )
        raise


def compute_rankings(sport_id: Optional[int]) -> None:
    """Rebuild PlayerRanking snapshots for global / club / age_group / division scopes."""
    if sport_id is None:
        sport_rows = execute_query("SELECT id FROM sports WHERE is_active = 1", fetch_all=True) or []
        sport_ids = [r['id'] for r in sport_rows]
    else:
        sport_ids = [sport_id]

    for sid in sport_ids:
        execute_query("DELETE FROM player_rankings WHERE sport_id = ?", (sid,))
        config = _config_row(sid)
        if not config:
            continue
        thresh = config['provisional_threshold']
        now = _utcnow_iso()

        for mt in ("singles", "doubles"):
            ratings = execute_query(
                """SELECT pr.*, u.club_id
                     FROM player_ratings pr
                     LEFT JOIN users u ON u.id = pr.player_id
                    WHERE pr.sport_id = ? AND pr.match_type = ? AND pr.matches_played >= ?
                    ORDER BY pr.rating DESC, pr.matches_played DESC""",
                (sid, mt, thresh), fetch_all=True,
            ) or []
            if not ratings:
                continue

            total_global = len(ratings)
            for idx, r in enumerate(ratings, start=1):
                execute_query(
                    """INSERT OR REPLACE INTO player_rankings
                       (player_id, sport_id, match_type, scope, scope_value, rank, rating, total_ranked, calculated_at)
                       VALUES (?, ?, ?, 'global', NULL, ?, ?, ?, ?)""",
                    (r['player_id'], sid, mt, idx, r['rating'], total_global, now),
                )

            # Group by club
            by_club: dict = {}
            for r in ratings:
                if r.get('club_id') is None:
                    continue
                by_club.setdefault(r['club_id'], []).append(r)
            for club_id, members in by_club.items():
                members.sort(key=lambda x: (-x['rating'], -x['matches_played']))
                total = len(members)
                for idx, r in enumerate(members, start=1):
                    execute_query(
                        """INSERT OR REPLACE INTO player_rankings
                           (player_id, sport_id, match_type, scope, scope_value, rank, rating, total_ranked, calculated_at)
                           VALUES (?, ?, ?, 'club', ?, ?, ?, ?, ?)""",
                        (r['player_id'], sid, mt, str(club_id), idx, r['rating'], total, now),
                    )

            # Group by age_group / division (via team memberships)
            for scope_col, scope_name in (('age_group', 'age_group'), ('division', 'division')):
                pid_to_values = {}
                for r in ratings:
                    rows = execute_query(
                        f"""SELECT DISTINCT t.{scope_col} AS val
                              FROM team_members tm
                              JOIN teams t ON t.id = tm.team_id
                             WHERE tm.player_id = ? AND tm.is_active = 1
                               AND t.sport_id = ? AND t.{scope_col} IS NOT NULL""",
                        (r['player_id'], sid), fetch_all=True,
                    ) or []
                    pid_to_values[r['player_id']] = [row['val'] for row in rows]

                buckets: dict = {}
                for r in ratings:
                    for val in pid_to_values.get(r['player_id'], []):
                        buckets.setdefault(val, []).append(r)
                for val, members in buckets.items():
                    members.sort(key=lambda x: (-x['rating'], -x['matches_played']))
                    total = len(members)
                    for idx, r in enumerate(members, start=1):
                        execute_query(
                            """INSERT OR REPLACE INTO player_rankings
                               (player_id, sport_id, match_type, scope, scope_value, rank, rating, total_ranked, calculated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (r['player_id'], sid, mt, scope_name, str(val), idx, r['rating'], total, now),
                        )


def apply_season_reset(sport_id: int) -> int:
    """Apply the configured season-reset to all PlayerRating rows for a sport. Returns rows touched."""
    config = _config_row(sport_id)
    if not config:
        return 0
    reset_type = config['season_reset_type']
    factor     = config['season_reset_factor']
    starting   = config['starting_rating']
    if reset_type == "none":
        return 0

    ratings = execute_query(
        "SELECT * FROM player_ratings WHERE sport_id = ?", (sport_id,), fetch_all=True
    ) or []
    now = _utcnow_iso()
    affected = 0
    for r in ratings:
        if reset_type == "hard":
            execute_query(
                """UPDATE player_ratings SET
                     rating = ?, peak_rating = ?, is_provisional = 1,
                     last_calculated_at = ?, updated_at = ?
                   WHERE id = ?""",
                (starting, starting, now, now, r['id']),
            )
        elif reset_type == "soft":
            new_rating = round(r['rating'] + (starting - r['rating']) * factor, 2)
            execute_query(
                """UPDATE player_ratings SET
                     rating = ?, last_calculated_at = ?, updated_at = ?
                   WHERE id = ?""",
                (new_rating, now, now, r['id']),
            )
        affected += 1
    return affected
