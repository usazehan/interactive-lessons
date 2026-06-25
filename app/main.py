"""Application entrypoint.

Run locally:    uvicorn app.main:app --reload
Docs:           http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI

from app.config import settings
from app.routers import (
    blocks,
    checkpoints,
    health,
    projects,
    sections,
    sessions,
)

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(sections.router)
app.include_router(blocks.router)
app.include_router(checkpoints.router)
app.include_router(sessions.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
