"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import billing as billing_router
from app.routers import users as users_router
from app.scheduler import shutdown_scheduler, start_scheduler

from app import models  # noqa: F401  (populate Base.metadata)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("app")

_SETTINGS = get_settings()
# server/app/main.py -> server/ -> repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
_REACT_DIST = os.path.join(_REPO_ROOT, "frontend", "dist")


# Idempotent additive migrations (safe to re-run every startup).
_ADDITIVE_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscribed_at TIMESTAMP WITH TIME ZONE",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _ADDITIVE_MIGRATIONS:
            try:
                await conn.execute(text(sql))
            except Exception as e:  # pragma: no cover
                log.warning("Migration skipped (%s): %s", sql, e)

        if _SETTINGS.admin_email:
            await conn.execute(
                text("UPDATE users SET role='admin' WHERE lower(email)=lower(:email)"),
                {"email": _SETTINGS.admin_email},
            )
            log.info("Ensured admin role for %s", _SETTINGS.admin_email)

    log.info("DB schema ensured")

    await start_scheduler()
    try:
        yield
    finally:
        await shutdown_scheduler()
        await engine.dispose()


app = FastAPI(
    title=_SETTINGS.app_name,
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        _SETTINGS.app_base_url.rstrip("/"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(billing_router.router)
app.include_router(admin_router.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "app": _SETTINGS.app_name}


# --------------- static/SPA serving ---------------
# Preference order on GET /:
#   1. React build at frontend/dist (if built)
#   2. Legacy vanilla UI at app/static (dev fallback)

if os.path.isdir(_REACT_DIST):
    _ASSETS_DIR = os.path.join(_REACT_DIST, "assets")
    if os.path.isdir(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    _VITE_SVG = os.path.join(_REACT_DIST, "vite.svg")
    if os.path.isfile(_VITE_SVG):
        @app.get("/vite.svg", include_in_schema=False)
        async def _vite_icon():
            return FileResponse(_VITE_SVG)

    _INDEX = os.path.join(_REACT_DIST, "index.html")

    @app.get("/", include_in_schema=False)
    async def _root():
        return FileResponse(_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str):
        # Don't swallow API routes or assets - FastAPI matches those first anyway.
        if full_path.startswith(("api/", "static/", "assets/")):
            raise HTTPException(status_code=404)
        return FileResponse(_INDEX)

    log.info("Serving React SPA from %s", _REACT_DIST)

elif os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    log.info("Serving legacy static UI from %s (React build not found)", _STATIC_DIR)
