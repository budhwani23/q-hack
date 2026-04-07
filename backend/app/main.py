import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="React + FastAPI App",
    version="1.0.0",
    description="A full-stack starter with React frontend and FastAPI backend.",
)

# CORS — allow all origins in development; tighten for production as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routes  (/api/*)
# ---------------------------------------------------------------------------

app.include_router(router, prefix="/api")

# ---------------------------------------------------------------------------
# Serve the React build (static files)
# Built by the Docker multi-stage step and copied to /app/static
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    # Mount assets (JS, CSS, images) — must come before the catch-all
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: serve index.html for any non-API route (SPA routing)."""
        index = STATIC_DIR / "index.html"
        return FileResponse(index)
