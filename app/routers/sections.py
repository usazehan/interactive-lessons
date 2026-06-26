"""Sections ("steps"): ordered units within a project.

Reads are public; writes require the authenticated project owner. Mutations
bump the project version and honor an optional `If-Match` header for optimistic
concurrency (see app.concurrency).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.auth import get_current_user, require_project_owner
from app.concurrency import require_matching_version
from app.models import Section, SectionCreate, User
from app.store import project_store, section_store

router = APIRouter(prefix="/projects/{project_id}/sections", tags=["sections"])


def _require_project(project_id: int) -> None:
    if project_store.get(project_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )


@router.get("", response_model=list[Section])
def list_sections(project_id: int) -> list[Section]:
    _require_project(project_id)
    return section_store.list(project_id)


@router.post("", response_model=Section, status_code=status.HTTP_201_CREATED)
def create_section(
    project_id: int,
    payload: SectionCreate,
    response: Response,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
    current_user: User = Depends(get_current_user),
) -> Section:
    require_project_owner(project_id, current_user)
    require_matching_version(project_id, if_match)
    section = section_store.create(project_id, payload)
    response.headers["ETag"] = str(project_store.bump_version(project_id))
    return section


@router.get("/{section_id}", response_model=Section)
def get_section(project_id: int, section_id: int) -> Section:
    section = section_store.get(project_id, section_id)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
        )
    return section


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    project_id: int,
    section_id: int,
    response: Response,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
    current_user: User = Depends(get_current_user),
) -> None:
    require_project_owner(project_id, current_user)
    require_matching_version(project_id, if_match)
    if not section_store.delete(project_id, section_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
        )
    response.headers["ETag"] = str(project_store.bump_version(project_id))
