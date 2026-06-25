"""Checkpoints within a section.

Checkpoints are created via a `type=checkpoint` content block (see blocks.py);
these endpoints read them and their inputs. Each checkpoint has a title and a
list of inputs.
"""
from fastapi import APIRouter, HTTPException, status

from app.models import Checkpoint
from app.store import checkpoint_store, section_store

router = APIRouter(
    prefix="/projects/{project_id}/sections/{section_id}/checkpoints",
    tags=["checkpoints"],
)


def _require_section(project_id: int, section_id: int) -> None:
    if section_store.get(project_id, section_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
        )


@router.get("", response_model=list[Checkpoint])
def list_checkpoints(project_id: int, section_id: int) -> list[Checkpoint]:
    _require_section(project_id, section_id)
    return checkpoint_store.list(section_id)


@router.get("/{checkpoint_id}", response_model=Checkpoint)
def get_checkpoint(
    project_id: int, section_id: int, checkpoint_id: int
) -> Checkpoint:
    _require_section(project_id, section_id)
    checkpoint = checkpoint_store.get(section_id, checkpoint_id)
    if checkpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="checkpoint not found"
        )
    return checkpoint
