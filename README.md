# 🏆 SLMS — Sports League Management System

A full-featured Sports League Management System built with **FastAPI** backend
and a **pure HTML/JS single-page frontend served by FastAPI** — zero npm, zero
Node.js. Default storage is **SQLite** (zero-config); MySQL is supported via a
single env-var switch.

**Status:** MVP deployed and live on BigRock shared hosting at
[https://sportsleague.amitastrosolutions.in](https://sportsleague.amitastrosolutions.in)

---

## 📁 Project Structure

```
sports-league/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py       # Settings (reads .env), DB switch
│   │   │   ├── database.py     # SQLAlchemy engine + session, init_db
│   │   │   ├── logging.py      # Logging config
│   │   │   └── security.py     # JWT auth + bcrypt password hashing
│   │   ├── models/models.py    # All DB models (Club, User, Team, Match…)
│   │   ├── routers/
│   │   │   ├── auth.py         # /api/auth/login|register|me
│   │   │   ├── clubs.py        # CRUD /api/clubs
│   │   │   ├── players.py      # CRUD /api/players
│   │   │   ├── teams.py        # CRUD /api/teams + roster management
│   │   │   ├── sports.py       # GET /api/sports (auto-seeded)
│   │   │   ├── matches.py      # CRUD /api/matches + scoring + events
│   │   │   ├── tournaments.py  # CRUD /api/tournaments + registration
│   │   │   └── dashboard.py    # GET /api/dashboard/stats|recent-*
│   │   ├── schemas/schemas.py  # Pydantic request/response models
│   │   └── main.py             # FastAPI app + serves SPA + global logging
│   ├── run.py                  # Local entry point (port 8765)
│   ├── requirements.txt
│   └── alembic.ini             # Reserved for future migrations
├── static/
│   └── index.html              # Complete SPA — no build step
├── logs/                       # Runtime logs
├── passenger_wsgi.py           # BigRock shared hosting entry (WSGI ↔ ASGI)
├── setup_db.sql                # Optional MySQL setup script
├── slms.db                     # Default SQLite database (auto-created)
└── 01-command.txt              # Local + deployment cheat sheet
```

---

## 🚀 Local Setup

### Step 1 — Python environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### Step 2 — (Optional) configure `.env`

SQLite works with **zero config** — `slms.db` is created at the project root on
first run. Create `backend/.env` only if you want to override defaults or
switch to MySQL.

```env
APP_ENV=development
SECRET_KEY=your-very-long-random-secret
JWT_SECRET_KEY=another-long-random-jwt-secret

# Default is sqlite; uncomment to switch:
# DB_TYPE=mysql
# DB_HOST=localhost
# DB_PORT=3306
# DB_NAME=slms_db
# DB_USER=slms_user
# DB_PASSWORD=YourPassword
```

For MySQL, optionally run `setup_db.sql` as root first.

### Step 3 — Run

```bash
cd backend
python run.py
```

Open: **http://localhost:8765**

- **Frontend (SPA):**  http://localhost:8765
- **API docs:**        http://localhost:8765/api/docs
- **Health check:**    http://localhost:8765/api/health

### Step 4 — First login

Register at `/` (use role `super_admin` for full access) or via API:

```bash
curl -X POST http://localhost:8765/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@slms.com",
    "password": "Admin@123",
    "first_name": "Super",
    "last_name": "Admin",
    "role": "super_admin"
  }'
```

---

## 🌐 Production Deployment (BigRock shared hosting)

The app is deployed on BigRock shared hosting — **not** a VPS. The bridge is:

```
Browser → Apache → Phusion Passenger (WSGI) → a2wsgi → FastAPI (ASGI)
```

cPanel's system Python is too old for FastAPI, so a **pre-compiled Python
3.12** lives in a local venv at `~/sports-league/.venv`. `passenger_wsgi.py`
detects the wrong interpreter and `os.execv`s into the 3.12 venv before any
modern syntax loads.

### Deploy cycle

```bash
# 1. Upload changes
scp -r * amitawn2@69.49.227.12:/home3/amitawn2/sports-league

# 2. Restart Passenger to pick up the new code
ssh amitawn2@69.49.227.12
touch ~/sports-league/tmp/restart.txt
```

### First-time / new dependency setup on the server

```bash
ssh amitawn2@69.49.227.12
cd /home3/amitawn2/sports-league
python3 -m venv .venv                          # only once
source ~/sports-league/.venv/bin/activate
cd backend
pip install --prefer-binary -r requirements.txt
touch ~/sports-league/tmp/restart.txt
```

### Verifying the server is running the right interpreter

```bash
cat /tmp/py_check.txt
# Should show: Executable: /home3/amitawn2/sports-league/.venv/bin/python3.12
```

### Switch cPanel → Application Manager → "Production" once stable
(more secure than Development mode).

### Shared-hosting constraints to remember

These shape what features can/can't be built:

- ❌ **No custom ports** — firewall blocks them. Everything goes through Apache on 80/443.
- ❌ **No always-on background workers** — shared hosting kills daemons. Use cPanel cron for scheduling.
- ⚠️ **No native WebSockets** — Passenger/WSGI doesn't speak WS. Real-time scoring (Phase 6) will need polling or SSE.
- ❌ **No system-level installs** (Redis, Celery broker). Stick to pure-Python deps installable via pip.
- ⚠️ **No persistent in-memory state** — Passenger may restart the worker between requests.
- ✅ **`passenger_wsgi.py` bootstrap must stay Python-2-safe** (`%s` formatting only) until `os.execv` switches to Python 3.12.

If a feature truly needs WebSockets, Redis, or a long-running worker, that's
the signal to migrate to a VPS — until then, design within these limits.

### Password reset (server-side)

```bash
cd backend
python - <<'PY'
from app.core.security import hash_password
from app.core.database import execute_query

new_hash = hash_password("abcdef1234")
execute_query("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, "myuser@myemail.com"))
print("Password reset done")
PY
```

---

## 🏅 Supported Sports (18+, auto-seeded)

| Category   | Sports                                          |
|------------|-------------------------------------------------|
| Team       | Football, Cricket, Basketball, Volleyball, Tug of War |
| Racket     | Tennis, Badminton, Table Tennis, Pickleball     |
| Precision  | Snooker, Billiards, Darts, Archery              |
| Aquatic    | Swimming, Rowing                                |
| Other      | Chess, Carrom, Foosball                         |

Sports auto-seed on first call to `/api/sports`.

---

## 🔐 Roles & Permissions

| Role           | Permissions                                      |
|----------------|--------------------------------------------------|
| `super_admin`  | Full access to everything                        |
| `club_admin`   | Manage own club: teams, matches, tournaments     |
| `club_manager` | Manage teams and matches within club             |
| `official`     | Update match scores and log events               |
| `player`       | View only                                        |
| `viewer`       | View only                                        |

---

## 📡 Key API Endpoints

Full interactive docs at **/api/docs** (Swagger) and **/api/redoc**.

### Auth
| Method | Endpoint               | Description        |
|--------|------------------------|--------------------|
| POST   | /api/auth/register     | Register new user  |
| POST   | /api/auth/login        | Login, get JWT     |
| GET    | /api/auth/me           | Current user info  |

### Clubs / Players / Teams / Matches / Tournaments / Dashboard
CRUD endpoints exist for all of the above. Highlights:

- `PATCH /api/matches/{id}/score` — live score updates
- `POST  /api/matches/{id}/events` — log goals/cards/etc.
- `POST  /api/tournaments/{id}/register` — register a team
- `GET   /api/dashboard/stats` — platform-wide counts
- `GET   /api/dashboard/recent-matches` / `recent-tournaments`

### System
| Method | Endpoint        | Description     |
|--------|-----------------|-----------------|
| GET    | /api/health     | Liveness probe  |

---

## 🗄️ Database Models

```
Club ──< User (players, admins)
Club ──< Team ──< TeamMember >── User
Sport ──< Team
Sport ──< Match ──< MatchEvent
Sport ──< Tournament ──< TournamentRegistration >── Team
Tournament ──< Match
User ──< PlayerMembership >── Club   (multi-club support)
```

Tables auto-create on startup via `init_db()`. `alembic.ini` is present for
future migration work but not actively driving schema changes yet.

---

## ✅ What's Done (current MVP)

- [x] FastAPI backend with 8 routers, JWT auth, bcrypt hashing
- [x] SQLite default + MySQL support via env flag
- [x] Single-file SPA frontend served by FastAPI ([static/index.html](static/index.html))
- [x] Auto-seeded sports catalog (18 sports)
- [x] CRUD for clubs, players, teams, matches, tournaments
- [x] Match scoring + event log
- [x] Tournament registration flow
- [x] Dashboard stats endpoints
- [x] Role-based permissions (6 roles)
- [x] Global request logging + unhandled-exception handler
- [x] Deployed to BigRock shared hosting via Passenger + a2wsgi

## 📌 Planned Next Phases

- [ ] **Phase 2:** Gamification (points, badges, leaderboards)
- [ ] **Phase 3:** Media uploads (player photos, club logos) — needs disk-quota planning on shared hosting
- [ ] **Phase 4:** Federation management (cross-club events)
- [ ] **Phase 5:** Advanced analytics & reporting
- [ ] **Phase 6:** ~~Real-time scoring via WebSockets~~ → **SSE or polling** (WebSockets not viable under Passenger)
- [ ] **Phase 7:** Mobile-optimised PWA
- [ ] **Future:** Alembic-driven migrations once the schema stabilises

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` locally | Activate venv: `source venv/bin/activate` |
| `Table doesn't exist` | Tables auto-create on startup; check DB connection |
| `401 Unauthorized` | Token expired — log in again |
| Port 8765 in use | Change in [backend/run.py](backend/run.py) |
| Server change not showing up | You forgot `touch ~/sports-league/tmp/restart.txt` |
| Server import errors | `cat /tmp/py_check.txt` — confirm `.venv/bin/python3.12` is being used |

---

Built with ❤️ — FastAPI · SQLAlchemy · SQLite/MySQL · Vanilla JS · Phusion Passenger
