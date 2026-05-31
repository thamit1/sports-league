# ⭐ Ratings & Rankings — Setup Guide

A DUPR-style player rating system on a **0–100 scale**, computed from
completed match scores using sport-specific Elo math. Ratings are
**derived**, never entered manually.

---

## 🧠 Mental model

```
Configure a sport ──▶ Play & complete matches ──▶ Trigger recalculation ──▶ View leaderboards
   (super_admin)        (officials / admins)         (super_admin)            (everyone allowed)
```

Recalculation is **manual and synchronous**. Match completion only marks a
match as eligible — it doesn't update ratings on its own. This is deliberate:
the same match log can be replayed with different K-factors, so you can
tune the system without losing data.

---

## 1️⃣ Configure a sport (one-time, per sport)

**Where:** Ratings → Configuration tab (super_admin only)

Click **+ Add Config** for any sport, set the knobs, save. A sport with
**no config has no ratings**. That's the kill switch — leaderboards and
profile cards stay empty until a config exists.

### Knobs explained

| Field | Default | What it does |
|---|---|---|
| **Provisional Threshold** | 5 | Matches needed before a player's rating is marked "Reliable". Below this, the rating shows as **Provisional** and the player is excluded from leaderboards. |
| **Starting Rating** | 50.0 | Where new players begin, also used by season-reset. |
| **K (Provisional)** | 32.0 | How much rating moves per match for new players. Higher = converges to true skill faster. |
| **K (Established)** | 16.0 | Standard rate for players ≥ provisional threshold and rating ≤ 75. |
| **K (Elite)** | 8.0 | Damped rate for players > 75. Prevents elite ratings from swinging wildly on a single match. |
| **Max Δ / Match** | 15.0 | Hard ceiling on per-match change in either direction. |
| **Visibility** | club_members | Who can see ratings for this sport: `public` / `club_members` / `admins_only`. |
| **Season Reset** | none | What happens when you click "Apply Season Reset": `none` / `soft` / `hard`. |
| **Soft Reset Factor** | 0.3 | For soft reset only: pulls each rating toward starting_rating by this fraction. `0.3` means a 70-rated player drops to `70 + (50-70)*0.3 = 64`. |
| **Active** | yes | Toggle off to freeze a sport's ratings without deleting them. |

### Suggested presets

- **Recreational / club leagues** — defaults are fine.
- **Highly competitive (need stability)** — drop K (Provisional) to 24, K (Established) to 12, K (Elite) to 6.
- **Brand-new tournament with cold ratings** — raise Max Δ to 20 for the first season so ratings settle quickly.

---

## 2️⃣ Make matches eligible

For the recalculation to pick a match up, **all four** must be true:

| Requirement | Where to check |
|---|---|
| `status = completed` | Matches page → filter by Completed |
| Both teams have ≥ 1 active player in the roster | Team Detail → Roster section |
| Score has been recorded | Match Detail → "Save Score" |
| The match's sport has a config | Ratings → Configuration tab |

Matches with empty rosters or scheduled-but-unplayed status are silently skipped.

### How scores are interpreted

Per sport, the engine normalises `score_a` / `score_b` into an "actual
score" in `[0.0, 1.0]`:

| Sport(s) | Margin rule |
|---|---|
| Badminton, Table Tennis, Pickleball, Tennis, Snooker, Billiards, Carrom, Darts, Archery | Point ratio: `score_a / (score_a + score_b)` |
| Football, Basketball, Volleyball, Foosball | Goal differential capped at 10 (winner: 0.5 + margin, loser: 0.5 − margin) |
| Cricket | Run differential capped at 100 |
| Swimming, Rowing | Inverted ratio (lower score / time wins) |
| Chess | Score is the result directly: 1 / 0.5 / 0 |
| Tug of War | Binary only — winner 1.0, loser 0.0 |
| Anything else / scores missing | Binary fallback: 1.0 / 0.5 / 0.0 |

Singles match (both teams have 1 player) → 1 update per side.
Doubles match (sport supports doubles + at least one team has > 1 player)
→ each player updates against the **average** rating of the opposing team.

---

## 3️⃣ Trigger a recalculation

**Where:** Ratings → Jobs tab → 🔄 **Trigger Recalculation** (super_admin only)

Pick a single sport, or "All Sports". Then **Run Recalculation**.

What happens, in order:
1. A `recalculation_jobs` row is inserted with status `running`.
2. For each selected sport with an active config:
   - All existing `rating_history` rows for that sport are deleted.
   - All `player_ratings` rows for that sport are reset to `starting_rating`.
   - Every completed match is replayed in chronological order (`scheduled_at` ASC).
   - For each match, both players' (or both teams') ratings are updated and a `rating_history` row is written.
3. Rankings are rebuilt for `global` / `club` / `age_group` / `division` scopes.
4. Job marked `completed` with `matches_processed` and `players_updated` counts.

If anything throws mid-job, status becomes `failed` and `error_message`
captures the exception. The partial state in `player_ratings` may be
inconsistent until you re-run — that's expected.

Typical duration: a few seconds for hundreds of matches. The UI shows a
spinner; the Jobs table auto-refreshes every 5 seconds while any job is
running.

---

## 4️⃣ View the results

| Where | What you see |
|---|---|
| Ratings → **Leaderboard** | Top N players per sport / match-type / scope (global / club / age-group / division). Trend column = average delta over last 5 matches. |
| Ratings → **Player Ratings** | Search-as-you-type → grid of rating cards across all sports the player has played. |
| **Player Detail** page (below club memberships) | ⭐ Sport Ratings grid + 📈 Rating History sparkline (SVG) + last 10 matches table. |
| **Dashboard** (bottom widget) | 🏆 Top Rated Players — top-5 podium per sport / match-type. |

A player is hidden from leaderboards (but their card still shows up on
their own profile) until they cross the provisional threshold.

---

## 🌱 Season reset

**Where:** call `POST /api/ratings/season-reset/{sport_id}` with body
`{"confirm": true}` (super_admin). No UI button yet — wire it up in the
Configuration tab when you start using it.

| Reset type | Effect |
|---|---|
| `none` | No-op. Ratings carry over indefinitely. |
| `soft` | Pull every rating toward `starting_rating` by `season_reset_factor`. Peak rating preserved. |
| `hard` | Set every rating (and peak) back to `starting_rating`. All players marked provisional again. |

History is **not** wiped — only the live `player_ratings` rows change.
A subsequent recalculation will replay the full history again, so soft/hard
resets are most useful as a step *before* deciding to also wipe history,
or for ad-hoc "freeze this state and start fresh" moments.

---

## 🔌 API reference

All endpoints under `/api/ratings`. Full Swagger at **/api/docs**.

### Super-admin only

| Method | Endpoint | Purpose |
|---|---|---|
| GET    | /api/ratings/config | List all sport configs |
| GET    | /api/ratings/config/{sport_id} | Single config |
| POST   | /api/ratings/config | Create config for a sport |
| PATCH  | /api/ratings/config/{sport_id} | Update knobs |
| POST   | /api/ratings/recalculate | Run a full recalc (`{sport_id: int | null}`) |
| GET    | /api/ratings/jobs | List recent recalculation jobs |
| GET    | /api/ratings/jobs/{job_id} | Single job detail |
| POST   | /api/ratings/season-reset/{sport_id} | Apply season-reset (`{confirm: true}`) |

### Visibility-gated (any authenticated user with appropriate role)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/ratings/player/{player_id} | All ratings for a player (visibility-filtered per sport) |
| GET | /api/ratings/player/{player_id}/{sport_id} | Singles + doubles ratings for one sport |
| GET | /api/ratings/player/{player_id}/{sport_id}/history | Match-by-match history (paginated) |
| GET | /api/ratings/leaderboard/{sport_id} | Top N with filters: `match_type`, `scope`, `scope_value`, `limit`, `offset` |
| GET | /api/ratings/leaderboard/{sport_id}/club/{club_id} | Shortcut for club-scoped leaderboard |

Visibility check (per sport's config):
- `public` → anyone authenticated
- `club_members` → any authenticated user
- `admins_only` → super_admin / club_admin / club_manager
- *no config* → admins_only (safe default)

---

## 🐛 "Why don't I see any ratings?" — checklist

If the leaderboard shows **No ranked players in this scope**:

1. **Does the sport have a config?** → Ratings → Configuration. If absent, no ratings are ever computed.
2. **Are there completed matches?** → Matches page → filter Completed. Scheduled or in-progress matches are ignored.
3. **Do the teams have rosters?** → Team Detail → Roster. Empty roster on either side = match skipped.
4. **Was a recalculation triggered?** → Ratings → Jobs tab. If no `completed` job is listed (or you've added matches since the last one), run it.
5. **Did everyone clear the provisional threshold?** → Default is 5 matches per (player, sport, match_type). Below that, players are excluded from the leaderboard but their card still shows on their profile.
6. **Did the job fail?** → Check `error_message` on the latest job row.

---

## 📐 Math reference

**Expected score** (scaled Elo for 0–100 range):

```
E = 1 / (1 + 10^((rating_b - rating_a) / 40))
```

The `/40` denominator (vs. the classic `/400`) is the only adjustment for
the compressed scale — the curve shape is identical to chess Elo.

**New rating:**

```
delta = K * (actual_score - expected_score)
delta = clamp(delta, -max_change, +max_change)
new_rating = clamp(old_rating + delta, 0, 100)
```

Rounded to 2 decimal places on storage.

**K-factor selection** (per player, per update):

```
if matches_played < provisional_threshold: K = K_provisional
elif current_rating > 75:                   K = K_elite
else:                                       K = K_established
```

---

## 🗂️ Data model

Five new tables, all created in [backend/app/core/database.py `init_db()`](backend/app/core/database.py):

| Table | Purpose |
|---|---|
| `sport_rating_configs` | One row per sport — the knobs from Step 1. |
| `player_ratings` | Current rating per (player, sport, match_type). Mutated by every match update. |
| `rating_history` | Audit trail — one row per (player, match, recalc run). Wiped + rebuilt on full recalc. |
| `player_rankings` | Precomputed ranking snapshots per scope. Rebuilt at the end of every recalc. |
| `recalculation_jobs` | Audit trail of every recalc trigger — who, when, what sport, outcome. |

Engine code: [backend/app/services/rating_engine.py](backend/app/services/rating_engine.py) — pure service, no FastAPI imports.
Router: [backend/app/routers/ratings.py](backend/app/routers/ratings.py).
