"""Application entrypoint.

Run locally:    uvicorn app.main:app --reload
Docs:           http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth,
    blocks,
    checkpoints,
    health,
    projects,
    sections,
    sessions,
)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Allow the browser frontend (a different origin) to call the API. ETag is
# exposed so the client can read a project's version for If-Match edits.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(sections.router)
app.include_router(blocks.router)
app.include_router(checkpoints.router)
app.include_router(sessions.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}
