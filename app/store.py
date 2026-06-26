"""Repositories.

Map between the SQLAlchemy ORM (app.db) and the Pydantic API schemas
(app.models). Each store opens a session per operation; child resources are
always query-scoped to their parent so integrity is enforced at the data
layer rather than relying on the routers.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, text

from app.config import settings

from app.db import (
    CheckpointORM,
    ContentBlockORM,
    ProjectORM,
    ProjectSectionORM,
    ReadingSessionORM,
    SessionLocal,
    SessionResponseORM,
    UserORM,
    init_db,
)
from app.models import (
    BlockType,
    Checkpoint,
    ContentBlock,
    ContentBlockCreate,
    Project,
    ProjectCreate,
    ProjectSnapshot,
    ReadingSession,
    Response,
    ResponseCreate,
    Section,
    SectionCreate,
    SnapshotSection,
    User,
)


class UserStore:
    def __init__(self) -> None:
        init_db()

    def get(self, user_id: int) -> Optional[User]:
        with SessionLocal() as session:
            row = session.get(UserORM, user_id)
            return User.model_validate(row) if row is not None else None

    def get_orm_by_email(self, email: str) -> Optional[UserORM]:
        """Return the raw ORM row (incl. hashed_password) for login checks."""
        with SessionLocal() as session:
            return session.query(UserORM).filter_by(email=email).one_or_none()

    def create(self, email: str, hashed_password: str) -> User:
        with SessionLocal() as session:
            row = UserORM(email=email, hashed_password=hashed_password)
            session.add(row)
            session.commit()
            session.refresh(row)
            return User.model_validate(row)


class ProjectStore:
    def __init__(self) -> None:
        init_db()

    def list(self) -> list[Project]:
        with SessionLocal() as session:
            rows = session.query(ProjectORM).order_by(ProjectORM.id).all()
            return [Project.model_validate(row) for row in rows]

    def get(self, project_id: int) -> Optional[Project]:
        with SessionLocal() as session:
            row = session.get(ProjectORM, project_id)
            return Project.model_validate(row) if row is not None else None

    def create(self, data: ProjectCreate, owner_id: int) -> Project:
        with SessionLocal() as session:
            row = ProjectORM(**data.model_dump(), owner_id=owner_id)
            session.add(row)
            session.commit()
            session.refresh(row)
            return Project.model_validate(row)

    def delete(self, project_id: int) -> bool:
        with SessionLocal() as session:
            row = session.get(ProjectORM, project_id)
            if row is None:
                return False
            session.delete(row)  # cascades to sections, blocks, checkpoints
            session.commit()
            return True

    def bump_version(self, project_id: int) -> Optional[int]:
        """Increment a project's version after a content edit. Returns it."""
        with SessionLocal() as session:
            row = session.get(ProjectORM, project_id)
            if row is None:
                return None
            row.version += 1
            session.commit()
            return row.version


class SectionStore:
    """Sections ("steps") are always scoped to their project."""

    def list(self, project_id: int) -> list[Section]:
        with SessionLocal() as session:
            rows = (
                session.query(ProjectSectionORM)
                .filter_by(project_id=project_id)
                .order_by(ProjectSectionORM.position, ProjectSectionORM.id)
                .all()
            )
            return [Section.model_validate(row) for row in rows]

    def get(self, project_id: int, section_id: int) -> Optional[Section]:
        with SessionLocal() as session:
            row = self._scoped(session, project_id, section_id)
            return Section.model_validate(row) if row is not None else None

    def create(self, project_id: int, data: SectionCreate) -> Section:
        with SessionLocal() as session:
            position = data.position
            if position is None:
                position = _next_position(
                    session, ProjectSectionORM, ProjectSectionORM.project_id, project_id
                )
            row = ProjectSectionORM(
                project_id=project_id, position=position, title=data.title
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return Section.model_validate(row)

    def delete(self, project_id: int, section_id: int) -> bool:
        with SessionLocal() as session:
            row = self._scoped(session, project_id, section_id)
            if row is None:
                return False
            session.delete(row)  # cascades to blocks, checkpoints, inputs
            session.commit()
            return True

    @staticmethod
    def _scoped(session, project_id: int, section_id: int) -> Optional[ProjectSectionORM]:
        return (
            session.query(ProjectSectionORM)
            .filter_by(id=section_id, project_id=project_id)
            .one_or_none()
        )


class ContentBlockStore:
    """Blocks are always scoped to their section."""

    def list(self, section_id: int) -> list[ContentBlock]:
        with SessionLocal() as session:
            rows = (
                session.query(ContentBlockORM)
                .filter_by(section_id=section_id)
                .order_by(ContentBlockORM.position, ContentBlockORM.id)
                .all()
            )
            return [ContentBlock.model_validate(row) for row in rows]

    def get(self, section_id: int, block_id: int) -> Optional[ContentBlock]:
        with SessionLocal() as session:
            row = self._scoped(session, section_id, block_id)
            return ContentBlock.model_validate(row) if row is not None else None

    def create(self, section_id: int, data: ContentBlockCreate) -> ContentBlock:
        with SessionLocal() as session:
            position = data.position
            if position is None:
                position = _next_position(
                    session, ContentBlockORM, ContentBlockORM.section_id, section_id
                )

            row = ContentBlockORM(
                section_id=section_id, type=data.type.value, position=position
            )
            if data.type is BlockType.checkpoint:
                # A checkpoint block creates and points at a checkpoint.
                checkpoint = CheckpointORM(section_id=section_id, title=data.title)
                session.add(checkpoint)
                session.flush()  # assign checkpoint.id
                row.checkpoint_id = checkpoint.id
            else:
                row.text_content = data.text_content
                row.code_content = data.code_content
                row.image_url = _url_str(data.image_url)
                row.keyword_metadata = data.keyword_metadata

            session.add(row)
            session.commit()
            session.refresh(row)
            return ContentBlock.model_validate(row)

    def delete(self, section_id: int, block_id: int) -> bool:
        with SessionLocal() as session:
            row = self._scoped(session, section_id, block_id)
            if row is None:
                return False
            if row.checkpoint_id is not None:
                # Deleting a checkpoint block removes its checkpoint (which
                # cascades to inputs and back to this block).
                checkpoint = session.get(CheckpointORM, row.checkpoint_id)
                if checkpoint is not None:
                    session.delete(checkpoint)
                else:
                    session.delete(row)
            else:
                session.delete(row)
            session.commit()
            return True

    @staticmethod
    def _scoped(session, section_id: int, block_id: int) -> Optional[ContentBlockORM]:
        return (
            session.query(ContentBlockORM)
            .filter_by(id=block_id, section_id=section_id)
            .one_or_none()
        )


class CheckpointStore:
    """Checkpoints are read-only here; they're created via checkpoint blocks."""

    def list(self, section_id: int) -> list[Checkpoint]:
        with SessionLocal() as session:
            rows = (
                session.query(CheckpointORM)
                .filter_by(section_id=section_id)
                .order_by(CheckpointORM.id)
                .all()
            )
            return [Checkpoint.model_validate(row) for row in rows]

    def get(self, section_id: int, checkpoint_id: int) -> Optional[Checkpoint]:
        with SessionLocal() as session:
            row = self._scoped(session, section_id, checkpoint_id)
            return Checkpoint.model_validate(row) if row is not None else None

    @staticmethod
    def _scoped(session, section_id: int, checkpoint_id: int) -> Optional[CheckpointORM]:
        return (
            session.query(CheckpointORM)
            .filter_by(id=checkpoint_id, section_id=section_id)
            .one_or_none()
        )


class ReadingSessionStore:
    """A reader's pinned, immutable snapshot of a project's content.

    A snapshot is an ephemeral stability window, not a permanent fork: there is
    one session per (project, reader), it carries a staleness flag so the reader
    knows to converge, and abandoned ones are pruned by TTL.
    """

    def create(self, project_id: int, user_id: str) -> ReadingSession:
        """Start or resume the reader's session for this project."""
        snapshot = build_snapshot(project_id)
        with SessionLocal() as session:
            _prune_idle(session)
            row = (
                session.query(ReadingSessionORM)
                .filter_by(project_id=project_id, user_id=user_id)
                .one_or_none()
            )
            if row is None:
                row = ReadingSessionORM(
                    project_id=project_id,
                    user_id=user_id,
                    project_version=snapshot.project_version,
                    snapshot=snapshot.model_dump_json(),
                )
                session.add(row)
            row.last_accessed_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._to_model(row, snapshot.project_version)

    def get(self, project_id: int, session_id: int) -> Optional[ReadingSession]:
        with SessionLocal() as session:
            row = self._scoped(session, project_id, session_id)
            if row is None:
                return None
            row.last_accessed_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._to_model(row, _live_version(session, project_id))

    def refresh(self, project_id: int, session_id: int) -> Optional[ReadingSession]:
        """Re-snapshot from the project's current content ("Get latest")."""
        snapshot = build_snapshot(project_id)
        with SessionLocal() as session:
            row = self._scoped(session, project_id, session_id)
            if row is None:
                return None
            row.snapshot = snapshot.model_dump_json()
            row.project_version = snapshot.project_version
            row.last_accessed_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._to_model(row, snapshot.project_version)

    def snapshot_has_checkpoint(self, session_id: int, checkpoint_id: int) -> bool:
        with SessionLocal() as session:
            row = session.get(ReadingSessionORM, session_id)
            if row is None:
                return False
            snapshot = ProjectSnapshot.model_validate_json(row.snapshot)
            return any(
                block.checkpoint_id == checkpoint_id
                for sec in snapshot.sections
                for block in sec.blocks
            )

    @staticmethod
    def _scoped(session, project_id: int, session_id: int) -> Optional[ReadingSessionORM]:
        return (
            session.query(ReadingSessionORM)
            .filter_by(id=session_id, project_id=project_id)
            .one_or_none()
        )

    @staticmethod
    def _to_model(row: ReadingSessionORM, latest_version: int) -> ReadingSession:
        return ReadingSession(
            id=row.id,
            project_id=row.project_id,
            user_id=row.user_id,
            project_version=row.project_version,
            latest_version=latest_version,
            is_stale=row.project_version < latest_version,
            last_accessed_at=row.last_accessed_at,
            snapshot=ProjectSnapshot.model_validate_json(row.snapshot),
        )


class ResponseStore:
    """A reader's checkpoint answers, scoped to their reading session."""

    def list(self, session_id: int, checkpoint_id: int) -> list[Response]:
        with SessionLocal() as session:
            rows = (
                session.query(SessionResponseORM)
                .filter_by(session_id=session_id, checkpoint_id=checkpoint_id)
                .order_by(SessionResponseORM.id)
                .all()
            )
            return [Response.model_validate(row) for row in rows]

    def create(
        self, session_id: int, checkpoint_id: int, data: ResponseCreate
    ) -> Response:
        with SessionLocal() as session:
            row = SessionResponseORM(
                session_id=session_id,
                checkpoint_id=checkpoint_id,
                text=data.text,
                link=_url_str(data.link),
                label=data.label,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return Response.model_validate(row)


def _url_str(value) -> Optional[str]:
    return str(value) if value is not None else None


def _next_position(session, model, scope_column, scope_value) -> int:
    """The next append position (max + 1) within a parent scope."""
    current_max = (
        session.query(func.max(model.position))
        .filter(scope_column == scope_value)
        .scalar()
    )
    return 0 if current_max is None else current_max + 1


def _live_version(session, project_id: int) -> int:
    version = (
        session.query(ProjectORM.version).filter_by(id=project_id).scalar()
    )
    return version if version is not None else 0


def _prune_idle(session, max_age_seconds: Optional[int] = None) -> int:
    """Delete reading sessions idle longer than the TTL. Caller commits."""
    ttl = settings.session_ttl_seconds if max_age_seconds is None else max_age_seconds
    cutoff = datetime.utcnow() - timedelta(seconds=ttl)
    return (
        session.query(ReadingSessionORM)
        .filter(ReadingSessionORM.last_accessed_at < cutoff)
        .delete(synchronize_session=False)
    )


def prune_stale_sessions(max_age_seconds: Optional[int] = None) -> int:
    """Remove abandoned reading-session snapshots. Returns how many were deleted.

    Safe to run on a schedule (e.g. a cron/worker) — snapshots are ephemeral;
    a reader simply re-snapshots on their next visit.
    """
    with SessionLocal() as session:
        deleted = _prune_idle(session, max_age_seconds)
        session.commit()
        return deleted


def build_snapshot(project_id: int) -> ProjectSnapshot:
    """Freeze a project's current content (sections + ordered blocks)."""
    project = project_store.get(project_id)
    version = project.version if project is not None else 0
    sections = [
        SnapshotSection(**sec.model_dump(), blocks=block_store.list(sec.id))
        for sec in section_store.list(project_id)
    ]
    return ProjectSnapshot(
        project_id=project_id, project_version=version, sections=sections
    )


def reset_db() -> None:
    """Wipe every table and reset id sequences. For tests."""
    with SessionLocal() as session:
        session.execute(sa_delete(SessionResponseORM))
        session.execute(sa_delete(ReadingSessionORM))
        session.execute(sa_delete(ContentBlockORM))
        session.execute(sa_delete(CheckpointORM))
        session.execute(sa_delete(ProjectSectionORM))
        session.execute(sa_delete(ProjectORM))
        session.execute(sa_delete(UserORM))
        session.execute(text("DELETE FROM sqlite_sequence"))
        session.commit()


user_store = UserStore()
project_store = ProjectStore()
section_store = SectionStore()
block_store = ContentBlockStore()
checkpoint_store = CheckpointStore()
session_store = ReadingSessionStore()
response_store = ResponseStore()
