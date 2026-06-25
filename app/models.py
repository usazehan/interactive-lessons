"""Pydantic schemas.

Request/response models live here so routers stay thin and validation is
declarative. Add new resource schemas alongside these.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class HealthResponse(BaseModel):
    status: str
    app: str


# --- Project -> section -> content block -------------------------------------
#
# A project is built from ordered sections ("steps"). Each section renders an
# ordered list of content blocks: text, image, link, code block, inline code,
# or a checkpoint. A checkpoint block points at a checkpoint, which has a title
# and collects the inputs (text/link) a user supplies.


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class Project(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Optimistic-concurrency token; bumped on every content edit.
    version: int


class SectionCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    # Render order within the project. Appended to the end when omitted.
    position: Optional[int] = Field(default=None, ge=0)


class Section(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    position: int
    title: Optional[str] = None


# --- Checkpoints --------------------------------------------------------------
#
# Authored content. A checkpoint is a prompt with a title; a reader's answers
# live on their reading session (see ReadingSession / Response), not here, so
# two readers never collide and an author's edits never touch a reader's work.


class Checkpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    title: str


# --- Content blocks ----------------------------------------------------------


class BlockType(str, Enum):
    text = "text"          # Markdown rich text: links + inline code live here
    image = "image"
    code_block = "code_block"
    checkpoint = "checkpoint"


# The single payload field each non-checkpoint block type requires.
_REQUIRED_FIELD: dict[BlockType, str] = {
    BlockType.text: "text_content",
    BlockType.code_block: "code_content",
    BlockType.image: "image_url",
}
_CONTENT_FIELDS = ("text_content", "code_content", "image_url")


class ContentBlockBase(BaseModel):
    type: BlockType
    # Markdown for `text` blocks — inline links (`[x](url)`), inline code
    # (`` `x` ``), bold, etc. all live in this string.
    text_content: Optional[str] = Field(default=None, max_length=20000)
    code_content: Optional[str] = Field(default=None, max_length=20000)
    image_url: Optional[AnyHttpUrl] = None
    keyword_metadata: Optional[str] = Field(default=None, max_length=500)


class ContentBlockCreate(ContentBlockBase):
    position: Optional[int] = Field(default=None, ge=0)
    # Used only when type == checkpoint: the title of the created checkpoint.
    title: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_payload_matches_type(self) -> "ContentBlockCreate":
        if self.type is BlockType.checkpoint:
            if not (self.title and self.title.strip()):
                raise ValueError("title is required for a checkpoint block")
            if any(getattr(self, f) is not None for f in _CONTENT_FIELDS):
                raise ValueError("a checkpoint block must not carry content fields")
            return self

        if self.title is not None:
            raise ValueError("title is only valid for a checkpoint block")

        required = _REQUIRED_FIELD[self.type]
        value = getattr(self, required)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"{required} is required for a {self.type.value} block")

        for field in _CONTENT_FIELDS:
            if field != required and getattr(self, field) is not None:
                raise ValueError(
                    f"{field} is not valid for a {self.type.value} block"
                )
        return self


class ContentBlock(ContentBlockBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    section_id: int
    position: int
    checkpoint_id: Optional[int] = None
    # Populated for checkpoint blocks so the section renders in one pass.
    checkpoint: Optional[Checkpoint] = None


# --- Reading sessions (a reader's pinned snapshot) ---------------------------
#
# A reader starts a session, which freezes the project's content as it is right
# now. They render from this snapshot, so an author's later autosaves do not
# disturb them. The reader opts in to the latest content via /refresh.


class SnapshotSection(Section):
    blocks: list[ContentBlock] = []


class ProjectSnapshot(BaseModel):
    project_id: int
    project_version: int
    sections: list[SnapshotSection] = []


class ReadingSessionCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)


class ReadingSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    user_id: str
    # The version this snapshot was pinned to.
    project_version: int
    # The project's current version, and whether the snapshot is behind it.
    latest_version: int
    is_stale: bool
    last_accessed_at: datetime
    snapshot: ProjectSnapshot


# --- Session responses (a reader's checkpoint answers) -----------------------


class ResponseCreate(BaseModel):
    # A response may carry a text note, a link, or both. At least one required.
    text: Optional[str] = Field(default=None, max_length=5000)
    link: Optional[AnyHttpUrl] = None
    label: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _require_text_or_link(self) -> "ResponseCreate":
        has_text = bool(self.text and self.text.strip())
        if not has_text and self.link is None:
            raise ValueError("provide at least one of: text, link")
        return self


class Response(ResponseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    checkpoint_id: int
