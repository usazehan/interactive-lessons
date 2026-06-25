"""Projects: the top-level container.

A project is built from ordered sections of content blocks. Its `version` is an
optimistic-concurrency token (also returned as an ETag) that editors echo back
via If-Match on content edits.
"""
from fastapi import APIRouter, HTTPException, Response, status

from app.models import Project, ProjectCreate
from app.store import project_store

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    return project_store.list()


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> Project:
    return project_store.create(payload)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: int, response: Response) -> Project:
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    response.headers["ETag"] = str(project.version)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int) -> None:
    if not project_store.delete(project_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
