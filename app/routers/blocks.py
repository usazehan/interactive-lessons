"""Content blocks: the ordered, typed elements rendered within a section.

A block is text (Markdown), image, code_block, or checkpoint. Links and inline
code live inside a text block's Markdown. List returns blocks ordered by
position, so a client renders a section in one pass.
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.concurrency import require_matching_version
from app.models import ContentBlock, ContentBlockCreate
from app.store import block_store, project_store, section_store

router = APIRouter(
    prefix="/projects/{project_id}/sections/{section_id}/blocks",
    tags=["blocks"],
)


def _require_section(project_id: int, section_id: int) -> None:
    if section_store.get(project_id, section_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="section not found"
        )


@router.get("", response_model=list[ContentBlock])
def list_blocks(project_id: int, section_id: int) -> list[ContentBlock]:
    _require_section(project_id, section_id)
    return block_store.list(section_id)


@router.post("", response_model=ContentBlock, status_code=status.HTTP_201_CREATED)
def create_block(
    project_id: int,
    section_id: int,
    payload: ContentBlockCreate,
    response: Response,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> ContentBlock:
    _require_section(project_id, section_id)
    require_matching_version(project_id, if_match)
    block = block_store.create(section_id, payload)
    response.headers["ETag"] = str(project_store.bump_version(project_id))
    return block


@router.get("/{block_id}", response_model=ContentBlock)
def get_block(project_id: int, section_id: int, block_id: int) -> ContentBlock:
    _require_section(project_id, section_id)
    block = block_store.get(section_id, block_id)
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="block not found"
        )
    return block


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_block(
    project_id: int,
    section_id: int,
    block_id: int,
    response: Response,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> None:
    _require_section(project_id, section_id)
    require_matching_version(project_id, if_match)
    if not block_store.delete(section_id, block_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="block not found"
        )
    response.headers["ETag"] = str(project_store.bump_version(project_id))
