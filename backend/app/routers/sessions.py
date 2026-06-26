"""Reading sessions: a reader's pinned, immutable view of a project.

Creating a session snapshots the project's content as it is right now. The
reader renders from that snapshot, so an author's later autosaves never disturb
them — they opt in to the latest content via /refresh. A reader's checkpoint
answers are stored as responses on their own session, so readers never collide.

All session endpoints require authentication; the session belongs to the
logged-in user, and only they can read, refresh, or respond to it.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.models import ReadingSession, Response, ResponseCreate, User
from app.store import project_store, response_store, session_store

router = APIRouter(prefix="/projects/{project_id}/sessions", tags=["sessions"])


def _require_project(project_id: int) -> None:
    if project_store.get(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )


def _get_owned_session(
    project_id: int, session_id: int, current_user: User
) -> ReadingSession:
    session = session_store.get(project_id, session_id)
    # A session is private to its reader; hide others' sessions as 404.
    if session is None or session.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return session


@router.post("", response_model=ReadingSession)
def start_session(
    project_id: int, current_user: User = Depends(get_current_user)
) -> ReadingSession:
    """Start or resume the current user's session for this project.

    There is one session per (project, reader); re-posting resumes the existing
    one (with its `is_stale` flag) rather than minting a new snapshot.
    """
    _require_project(project_id)
    return session_store.create(project_id, str(current_user.id))


@router.get("/{session_id}", response_model=ReadingSession)
def get_session(
    project_id: int, session_id: int, current_user: User = Depends(get_current_user)
) -> ReadingSession:
    return _get_owned_session(project_id, session_id, current_user)


@router.post("/{session_id}/refresh", response_model=ReadingSession)
def refresh_session(
    project_id: int, session_id: int, current_user: User = Depends(get_current_user)
) -> ReadingSession:
    """Re-snapshot from the project's current content ("Get latest")."""
    _get_owned_session(project_id, session_id, current_user)
    session = session_store.refresh(project_id, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return session


# --- responses: a reader's answers to a checkpoint in their snapshot ---------


def _require_snapshot_checkpoint(
    project_id: int, session_id: int, checkpoint_id: int, current_user: User
) -> None:
    _get_owned_session(project_id, session_id, current_user)
    if not session_store.snapshot_has_checkpoint(session_id, checkpoint_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="checkpoint not in this session's snapshot",
        )


@router.get(
    "/{session_id}/checkpoints/{checkpoint_id}/responses",
    response_model=list[Response],
)
def list_responses(
    project_id: int,
    session_id: int,
    checkpoint_id: int,
    current_user: User = Depends(get_current_user),
) -> list[Response]:
    _require_snapshot_checkpoint(project_id, session_id, checkpoint_id, current_user)
    return response_store.list(session_id, checkpoint_id)


@router.post(
    "/{session_id}/checkpoints/{checkpoint_id}/responses",
    response_model=Response,
    status_code=status.HTTP_201_CREATED,
)
def add_response(
    project_id: int,
    session_id: int,
    checkpoint_id: int,
    payload: ResponseCreate,
    current_user: User = Depends(get_current_user),
) -> Response:
    _require_snapshot_checkpoint(project_id, session_id, checkpoint_id, current_user)
    return response_store.create(session_id, checkpoint_id, payload)
