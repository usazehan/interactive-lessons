"""Optimistic concurrency for content edits.

Authors autosave continuously; two editors (or two tabs) can race. Each edit
may carry an `If-Match: <version>` header with the project version it was based
on. If that's stale, the write is rejected with 409 instead of silently
clobbering a newer edit. Omitting the header is allowed (last-write-wins).
"""
from typing import Optional

from fastapi import HTTPException, status

from app.store import project_store


def require_matching_version(project_id: int, if_match: Optional[str]) -> None:
    """Raise 409 if If-Match is present and doesn't match the live version."""
    if if_match is None:
        return
    try:
        expected = int(if_match.strip().strip('"'))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="If-Match must be an integer project version",
        ) from exc

    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    if project.version != expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"stale edit: project is at version {project.version}, "
                f"not {expected} — refetch and retry"
            ),
        )
