import pathlib
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, logger
from app.routers import auth, clubs, players, teams, sports, matches, tournaments, dashboard

configure_logging()
logger.info("Starting Sports League Management System")

# Initialize database
logger.debug("Initializing database schema")
init_db()
logger.info("Database initialization complete")

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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info("Incoming request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = (time.time() - start_time) * 1000
    logger.info(
        "Completed request: %s %s -> %s in %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception for request %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
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
