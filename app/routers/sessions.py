"""Reading sessions: a reader's pinned, immutable view of a project.

Creating a session snapshots the project's content as it is right now. The
reader renders from that snapshot, so an author's later autosaves never disturb
them — they opt in to the latest content via /refresh. A reader's checkpoint
answers are stored as responses on their own session, so readers never collide.
"""
from fastapi import APIRouter, HTTPException, status

from app.models import ReadingSession, ReadingSessionCreate, Response, ResponseCreate
from app.store import project_store, response_store, session_store

router = APIRouter(prefix="/projects/{project_id}/sessions", tags=["sessions"])


def _require_project(project_id: int) -> None:
    if project_store.get(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )


def _get_session(project_id: int, session_id: int) -> ReadingSession:
    session = session_store.get(project_id, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return session


@router.post("", response_model=ReadingSession)
def start_session(project_id: int, payload: ReadingSessionCreate) -> ReadingSession:
    """Start or resume the reader's session for this project.

    There is one session per (project, reader); re-posting resumes the existing
    one (with its `is_stale` flag) rather than minting a new snapshot.
    """
    _require_project(project_id)
    return session_store.create(project_id, payload.user_id)


@router.get("/{session_id}", response_model=ReadingSession)
def get_session(project_id: int, session_id: int) -> ReadingSession:
    return _get_session(project_id, session_id)


@router.post("/{session_id}/refresh", response_model=ReadingSession)
def refresh_session(project_id: int, session_id: int) -> ReadingSession:
    """Re-snapshot from the project's current content ("Get latest")."""
    session = session_store.refresh(project_id, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return session


# --- responses: a reader's answers to a checkpoint in their snapshot ---------


def _require_snapshot_checkpoint(
    project_id: int, session_id: int, checkpoint_id: int
) -> None:
    _get_session(project_id, session_id)
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
    project_id: int, session_id: int, checkpoint_id: int
) -> list[Response]:
    _require_snapshot_checkpoint(project_id, session_id, checkpoint_id)
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
) -> Response:
    _require_snapshot_checkpoint(project_id, session_id, checkpoint_id)
    return response_store.create(session_id, checkpoint_id, payload)
