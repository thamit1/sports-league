import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import engine, Base
from app.routers import auth, clubs, players, teams, sports, matches, tournaments, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sports League Management System",
    description="SLMS — Unified Edition API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routers ──────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",        tags=["Auth"])
app.include_router(clubs.router,       prefix="/api/clubs",       tags=["Clubs"])
app.include_router(players.router,     prefix="/api/players",     tags=["Players"])
app.include_router(teams.router,       prefix="/api/teams",       tags=["Teams"])
app.include_router(sports.router,      prefix="/api/sports",      tags=["Sports"])
app.include_router(matches.router,     prefix="/api/matches",     tags=["Matches"])
app.include_router(tournaments.router, prefix="/api/tournaments", tags=["Tournaments"])
app.include_router(dashboard.router,   prefix="/api/dashboard",   tags=["Dashboard"])

@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0"}

# ─── Serve Static Frontend ────────────────────────────────────────
# Resolve: backend/app/main.py → backend/app → backend → project_root
BASE_DIR   = pathlib.Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"

@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"error": "Frontend not found. Place index.html in /static/ at project root."}
