"""SQLAlchemy persistence layer.

Owns the engine, session factory, and ORM table definitions so the store
and routers stay storage-agnostic. Swap the database URL/driver here without
touching callers.

The database path comes from app.config (DATABASE_PATH env) so it's easy to
point at a throwaway file or ":memory:" during tests. For in-memory we use a
StaticPool so the single connection (and thus the schema and data) is shared
across threads and sessions for the life of the process.

make_engine() also creates the parent directory for a file DB and turns on
SQLite foreign-key enforcement (off by default in SQLite), so the FK
constraints below are actually enforced at the database level.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.config import settings


def make_engine(db_path: str = settings.database_path) -> Engine:
    """Build the SQLite engine, enforcing foreign keys on every connection."""
    if db_path == ":memory:":
        url = "sqlite://"
        kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    else:
        Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path}"
        kwargs = {"connect_args": {"check_same_thread": False}}

    new_engine = create_engine(url, **kwargs)

    @event.listens_for(new_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return new_engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_token: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    reset_token: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class RefreshTokenORM(Base):
    """A server-side, revocable refresh token (stored hashed)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class ProjectORM(Base):
    __tablename__ = "projects"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    # Bumped on every content edit; used for optimistic concurrency (If-Match).
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # The authoring user. Null if the owner was deleted.
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    sections: Mapped[list["ProjectSectionORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectSectionORM.position",
    )


class ProjectSectionORM(Base):
    """An ordered "step" within a project."""

    __tablename__ = "project_sections"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    project: Mapped["ProjectORM"] = relationship(back_populates="sections")
    blocks: Mapped[list["ContentBlockORM"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="ContentBlockORM.position",
    )
    checkpoints: Mapped[list["CheckpointORM"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class ContentBlockORM(Base):
    """One ordered, typed element rendered within a section."""

    __tablename__ = "content_blocks"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # text_content holds Markdown for `text` blocks (inline links live here).
    text_content: Mapped[Optional[str]] = mapped_column(String(20000), nullable=True)
    code_content: Mapped[Optional[str]] = mapped_column(String(20000), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    keyword_metadata: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Set only when type == "checkpoint"; points at the block's checkpoint.
    checkpoint_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="CASCADE"), nullable=True, index=True
    )

    section: Mapped["ProjectSectionORM"] = relationship(back_populates="blocks")
    checkpoint: Mapped[Optional["CheckpointORM"]] = relationship()


class CheckpointORM(Base):
    __tablename__ = "checkpoints"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    section: Mapped["ProjectSectionORM"] = relationship(back_populates="checkpoints")


class ReadingSessionORM(Base):
    """A reader's frozen view of a project.

    Captures an immutable JSON snapshot of the project's content at the moment
    the reader started, so an author's later autosaves never disturb them.
    """

    __tablename__ = "reading_sessions"
    # One live session per (project, reader): re-opening resumes it rather than
    # piling up a new frozen snapshot per visit.
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_session_project_user"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # The project.version this snapshot was taken from.
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    # Bumped on every access; drives TTL-based cleanup of abandoned sessions.
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    responses: Mapped[list["SessionResponseORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionResponseORM.id",
    )


class SessionResponseORM(Base):
    """A reader's input on a checkpoint, scoped to their reading session.

    `checkpoint_id` references a checkpoint *in the session's snapshot*, not a
    live row (which the author may have since changed) — so it is intentionally
    not a foreign key.
    """

    __tablename__ = "session_responses"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checkpoint_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # A response has a text note, a link, or both (at least one, per the schema).
    text: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    session: Mapped["ReadingSessionORM"] = relationship(back_populates="responses")


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)
