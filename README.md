# 🏆 SLMS — Sports League Management System

A full-featured Sports League Management System built with **FastAPI + MySQL** backend
and a **pure HTML/JS frontend served by FastAPI** — zero npm, zero Node.js required.

---

## 📁 Project Structure

```
slms/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py       # Settings (reads .env)
│   │   │   ├── database.py     # SQLAlchemy engine + session
│   │   │   └── security.py     # JWT auth + password hashing
│   │   ├── models/
│   │   │   └── models.py       # All DB models (Club, User, Team, Match…)
│   │   ├── routers/
│   │   │   ├── auth.py         # POST /api/auth/login|register, GET /me
│   │   │   ├── clubs.py        # CRUD /api/clubs
│   │   │   ├── players.py      # CRUD /api/players
│   │   │   ├── teams.py        # CRUD /api/teams + roster management
│   │   │   ├── sports.py       # GET /api/sports (auto-seeded 18 sports)
│   │   │   ├── matches.py      # CRUD /api/matches + live scoring + events
│   │   │   ├── tournaments.py  # CRUD /api/tournaments + registration
│   │   │   └── dashboard.py    # GET /api/dashboard/stats|recent-*
│   │   ├── schemas/
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   └── main.py             # FastAPI app + serves frontend
│   ├── run.py                  # Entry point: python run.py
│   ├── requirements.txt
│   └── .env.example
├── static/
│   └── index.html              # Complete SPA (no build step!)
└── setup_db.sql                # MySQL setup script
```

---

## 🚀 Quick Setup (5 steps)

### Step 1 — MySQL Database

```bash
# As MySQL root:
mysql -u root -p < setup_db.sql
```

Or manually:
```sql
CREATE DATABASE slms_db CHARACTER SET utf8mb4;
CREATE USER 'slms_user'@'localhost' IDENTIFIED BY 'YourPassword';
GRANT ALL PRIVILEGES ON slms_db.* TO 'slms_user'@'localhost';
FLUSH PRIVILEGES;
```

---

### Step 2 — Python Environment

```bash
cd slms/backend

# Create virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 3 — Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
APP_ENV=development
SECRET_KEY=your-very-long-random-secret-key-here
JWT_SECRET_KEY=another-long-random-jwt-secret-here

DB_HOST=localhost
DB_PORT=3306
DB_NAME=slms_db
DB_USER=slms_user
DB_PASSWORD=YourPassword
```

---

### Step 4 — Run

```bash
cd slms/backend
python run.py
```

That's it! Visit: **http://localhost:8000**

- **Frontend (SPA):**  http://localhost:8000
- **API Docs:**        http://localhost:8000/api/docs
- **Health Check:**    http://localhost:8000/api/health

---

### Step 5 — First Login

1. Open http://localhost:8000
2. Click **"Register"** to create your first account
3. Use role `super_admin` for full access
4. Or via API directly:

```bash
curl -X POST http://localhost:8000/api/auth/register \
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

## 🏅 Supported Sports (18+)

| Category   | Sports                                          |
|------------|-------------------------------------------------|
| Team       | Football, Cricket, Basketball, Volleyball, Tug of War |
| Racket     | Tennis, Badminton, Table Tennis, Pickleball     |
| Precision  | Snooker, Billiards, Darts, Archery              |
| Aquatic    | Swimming, Rowing                                |
| Other      | Chess, Carrom, Foosball                         |

Sports are **auto-seeded** on first API call to `/api/sports`.

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

### Auth
| Method | Endpoint               | Description        |
|--------|------------------------|--------------------|
| POST   | /api/auth/register     | Register new user  |
| POST   | /api/auth/login        | Login, get JWT     |
| GET    | /api/auth/me           | Current user info  |

### Clubs
| Method | Endpoint               | Description         |
|--------|------------------------|---------------------|
| GET    | /api/clubs             | List all clubs      |
| POST   | /api/clubs             | Create club (admin) |
| GET    | /api/clubs/{id}        | Get club details    |
| PATCH  | /api/clubs/{id}        | Update club         |

### Players
| Method | Endpoint               | Description                    |
|--------|------------------------|--------------------------------|
| GET    | /api/players           | List players (search, filter)  |
| GET    | /api/players/{id}      | Player profile                 |
| PATCH  | /api/players/{id}      | Update player                  |
| GET    | /api/players/{id}/clubs| Player's club memberships      |

### Teams
| Method | Endpoint                       | Description           |
|--------|--------------------------------|-----------------------|
| GET    | /api/teams                     | List teams            |
| POST   | /api/teams                     | Create team           |
| GET    | /api/teams/{id}                | Team details          |
| GET    | /api/teams/{id}/members        | Roster                |
| POST   | /api/teams/{id}/members        | Add player to roster  |
| DELETE | /api/teams/{id}/members/{pid}  | Remove from roster    |

### Matches
| Method | Endpoint                    | Description             |
|--------|-----------------------------|-------------------------|
| GET    | /api/matches                | List (filter by status) |
| POST   | /api/matches                | Schedule match          |
| GET    | /api/matches/{id}           | Match details           |
| PATCH  | /api/matches/{id}/score     | Update score/status     |
| GET    | /api/matches/{id}/events    | Event log               |
| POST   | /api/matches/{id}/events    | Log event               |

### Tournaments
| Method | Endpoint                         | Description          |
|--------|----------------------------------|----------------------|
| GET    | /api/tournaments                 | List all             |
| POST   | /api/tournaments                 | Create               |
| GET    | /api/tournaments/{id}            | Details              |
| POST   | /api/tournaments/{id}/register   | Register team        |
| GET    | /api/tournaments/{id}/teams      | Registered teams     |
| PATCH  | /api/tournaments/{id}/status     | Update status        |

### Dashboard
| Method | Endpoint                          | Description          |
|--------|-----------------------------------|----------------------|
| GET    | /api/dashboard/stats              | Platform-wide counts |
| GET    | /api/dashboard/recent-matches     | Last 5 matches       |
| GET    | /api/dashboard/recent-tournaments | Last 5 tournaments   |

Full interactive docs always available at: **http://localhost:8000/api/docs**

---

## 🗄️ Database Models

```
Club ──< User (players, admins)
Club ──< Team ──< TeamMember >── User
Sport ──< Team
Sport ──< Match
Sport ──< Tournament ──< TournamentRegistration >── Team
Tournament ──< Match
Match ──< MatchEvent
User ──< PlayerMembership >── Club  (multi-club support)
```

---

## 🔧 Upgrading / Extending

### Add a new sport
```python
# In backend/app/routers/sports.py, add to DEFAULT_SPORTS:
{"name": "Kabaddi", "category": "team", "max_team_size": 7, "min_team_size": 7, "icon": "🤸"}
```

### Add a new API endpoint
1. Create/edit a file in `backend/app/routers/`
2. Register it in `backend/app/main.py`
3. Add the frontend UI section in `static/index.html`

### Production deployment
```bash
# Use gunicorn with uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |
| `Access denied for user` | Check DB credentials in `.env` |
| `Table doesn't exist` | Tables auto-create on startup. Check DB connection. |
| `401 Unauthorized` | Token expired — log in again |
| Port 8000 in use | Change port in `run.py`: `port=8080` |

---

## 📌 Planned Next Phases

- [ ] Phase 2: Gamification (points, badges, leaderboards)
- [ ] Phase 3: Media uploads (player photos, club logos)
- [ ] Phase 4: Federation management (cross-club events)
- [ ] Phase 5: Advanced analytics & reporting
- [ ] Phase 6: Real-time scoring via WebSockets
- [ ] Phase 7: Mobile-optimised PWA

---

Built with ❤️ — FastAPI · SQLAlchemy · MySQL · Vanilla JS
