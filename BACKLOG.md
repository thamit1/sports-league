# 📋 SLMS Backlog

Single source of truth for in-progress and planned work. Update as phases ship.

Token estimates are rough — wall-clock cost of getting from "spec in hand" to
"merged + smoke-tested + graph regenerated", not lines of code.

---

## ✅ Done

| # | Phase / Feature | Notes |
|---|---|---|
| — | MVP (clubs, players, teams, matches, tournaments, sports) | Original codebase |
| — | **Sports auto-seeded on every startup** (idempotent) | [database.py `_seed_default_sports`](backend/app/core/database.py) |
| — | **Full CRUD UI** for clubs, teams, matches, tournaments, sports + edit/delete + unregister | |
| — | **Ratings & Rankings** (DUPR-style, 0–100 Elo, sport-specific margin rules, recalc jobs, leaderboards, sparklines) | [RATINGS.md](RATINGS.md) |
| — | **Knowledge-graph CLI** for fast cross-file lookups | [graph_q.py](graph_q.py), [GRAPH_UPDATE_QUICK_REFERENCE.md](GRAPH_UPDATE_QUICK_REFERENCE.md) |
| 1 | **Score Capture MVP** — `score_keeper` role + per-match assignment + mobile-friendly Score Entry kiosk | |
| 2 | **Role-model refactor** — `user_assignments` (scoped, composable), chip UI, drift healing, partial unique index for NULL scope_id | |
| 4 | **Multi-sport League + Captain workflows** — leagues table, per-sport tournaments, captain scoped role, "My Teams" view, score-confirmation flow (`awaiting_confirmation` / `disputed`), league standings (aggregate + per-sport) | |
| 6.1 | **Sport-specific scoring (Slice 1)** — kiosk dispatcher framework, cricket widget (runs/wickets/overs/balls), chess (1/½/0), Tug of War (binary). `formatScore(sport, score)` helper used everywhere. | Cricket score JSON has `total: runs` so the rating engine's `_coerce_score` keeps working without changes. |
| 6.1b | **Player attribution in scoring** — "Scoring as: [player ▾]" selector on each team card, every scoring tap creates a `MatchEvent` row attributing the score to a player, scoring router gets `POST/GET/DELETE /scoring/matches/{id}/events` + `/roster`, recent-events feed at the bottom of the kiosk with ✕ to undo (deletes event + rolls back team total). | Score keepers can now log events (existing `/matches/{id}/events` is still admin-only). |
| 6.1c | **Cricket bowler attribution + bowling figures** — second "Bowler" selector on each cricket card (sources from the OTHER team's roster). Each event stores `event_data.bowler_id`. Recent-events feed shows "+4 by Bumrah". New "🎯 Bowling Figures" card under the kiosk computes O/R/W/Econ per bowler. `_kioskLogEvent(side, type, value, extra)` and the scoring router's `add_scoring_event` accept an `extra` object that merges into `event_data`. | No schema change — uses the existing JSON column. |

## 🚧 In Progress

_Nothing in progress. Pick the next phase / slice from below._

## ⏳ Planned

| # | Phase | Rough effort | Headline scope |
|---|---|---|---|
| 3 | Public Viewer + Member Self-Enrollment | ~800K tokens | `/api/public/*` no-auth routes, public landing page, tournament-registration request flow with admin approval, `enrollment_requests` table |
| 5 | Facility Booking & Management | ~1M tokens | `facilities` + `bookings` tables, conflict detection, calendar view, match-scheduling hooks |
| 6.2 | **Sport-specific Scoring — Slice 2** — Tennis kiosk (0/15/30/40, deuce, advantage, set tracking with 2-game lead) + Badminton/TT/Pickleball kiosk (+/- points + "End Game" commit, game history per side). `formatScore` updated for both shapes. Tennis `total = sets`, racket-sports `total = cumulative points` (so the rating engine reads the right number). | No tiebreak in tennis (admin can manually adjust if needed); racket sports rely on the score keeper hitting "End Game" — target points (21/11) shown as a hint only. |
| 6.3 | **Sport-specific Scoring — Slice 3** — Frame/leg/board widget reused for Snooker (frames), Billiards (frames), Darts (legs), Carrom (boards). One "+ X won" button per side, attribution via the player selector, events feed entries typed as `frame` / `leg` / `board`. `formatScore` pluralises the noun. | Per-frame point detail (breaks, finishing checkouts) deferred; only frame outcome captured at this slice. |
| 6.4 | **Sport-specific Scoring — Slice 4** — Timed widget for Swimming / Rowing (lower-is-better) and Archery (higher-is-better). Numeric input per side; winner computed honouring `_lowerIsBetter`. Attribution selector + events feed suppressed (the player IS the side). | Single-heat results only; multi-heat / leaderboard-style competition deferred. |
| 6.1d | **Cricket extras** — Wd / Nb / B / LB buttons on the cricket kiosk. Wide / no-ball add 1 run with no ball-counter advance; byes / leg-byes add 1 run and 1 ball. Bowling-figures rollup honours the distinction (bowler not charged for byes; no ball bowled for wide/no-ball). Tap multiple times for multi-run extras. | |
| 6.1e | **Bowling figures on Match Detail** — `_renderBowlingFigures` reused on the read-only Match Detail page (cricket matches only). Pulls names from the events themselves where available, falls back to `/teams/{id}/members`. Events list also now shows Player column. | `/api/matches/{id}/events` enriched to include `player_name` + `team_name` via JOIN. |
| 6.3 | Sport-specific Scoring — Slice 3 | ~200K tokens | Snooker / Billiards / Darts / Carrom (frame-based) |
| 6.4 | Sport-specific Scoring — Slice 4 | ~200K tokens | Time-based: Swimming / Rowing / Archery (heat or round scoring; lower-is-better support) |

## 🚫 Deferred

| Item | Why |
|---|---|
| Federation Admin (inter-club events) | Skip until a real inter-club event needs it; design against concrete requirements rather than speculation |
| Per-club login model (multi-login for multi-club members) | Single login + admin-added memberships is simpler; revisit when a concrete privacy/data-isolation need surfaces |
| Public read endpoints before Phase 3 | Today, all `/api/*` routes require auth. Phase 3 is the right time to add the public layer end-to-end. |
| Migration of `match_assignments` into `user_assignments` | They serve different semantics (operational vs capability). Unify only if Phase 4/5 reveals duplication pain. |

## 🐞 Known Issues / Tech Debt

| Item | Severity | Notes |
|---|---|---|
| `_safe_json` helper duplicated in [matches.py](backend/app/routers/matches.py) + [dashboard.py](backend/app/routers/dashboard.py) | Low | Lift to a shared module when a third caller appears |
| `graph_generator.py` crashes on trailing `✓` under Windows cp1252 | Low | Files are written before the crash. Patch with `PYTHONIOENCODING=utf-8` or replace the glyph |
| Players page is really "Users" admin | Low | Cosmetic — will get renamed during Phase 3 when member self-service lands |
| BigRock deploy not run since Phase 1 | Medium | Stack of features unshipped locally — needs an `scp + touch restart.txt` cycle before users see them |

## 🪪 Conventions

- New collection endpoints **must declare both `""` and `"/"`** to avoid the 405 the SPA catch-all creates ([backend/app/routers/clubs.py](backend/app/routers/clubs.py) is the canonical example)
- Soft-delete by default (`is_active = 0` or `status = 'cancelled'`); hard-delete only for join rows like `tournament_registrations`, `team_members`, `match_assignments`
- All new datetime fields stored as UTC ISO strings
- Rating values rounded to 2 decimal places on storage
- New rating tables and helpers live in [backend/app/services/rating_engine.py](backend/app/services/rating_engine.py) — pure service, no FastAPI imports
- Frontend: new pages follow the `async renderXxx()` + post-mount-hook pattern; no new libraries; all CSS in the existing `<style>` block
