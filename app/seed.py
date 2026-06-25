"""Seed the database with sample happy-path data.

Creates a few projects and gives the first one a fully-worked section: an
ordered run of content blocks (Markdown text, code, image) plus a checkpoint
block. Useful for exercising the section / block / session endpoints right away
(a reader's answers live on a reading session, so the seed authors content
only).

Run against whatever DATABASE_PATH points at (default interactive_lessons.db):

    python -m app.seed
"""
from app.models import (
    BlockType,
    ContentBlockCreate,
    Project,
    ProjectCreate,
    SectionCreate,
)
from app.store import block_store, project_store, section_store

SAMPLE_PROJECTS = [
    ProjectCreate(name="Onboarding", description="Intro project for new users."),
    ProjectCreate(name="Research Sprint", description="Collect and review sources."),
    ProjectCreate(name="Empty Project", description="No sections yet — add some."),
]


def seed() -> list[Project]:
    """Create the sample projects and a worked section. Returns the projects."""
    projects = [project_store.create(p) for p in SAMPLE_PROJECTS]

    section = section_store.create(
        projects[0].id, SectionCreate(title="Getting started")
    )

    # An ordered run of content blocks (position auto-appends). The text block
    # is Markdown — its link and inline code live inside text_content.
    block_store.create(
        section.id,
        ContentBlockCreate(
            type=BlockType.text,
            text_content=(
                "Welcome! Read the [FastAPI docs](https://fastapi.tiangolo.com), "
                "then hit `GET /health` to confirm the server is up."
            ),
        ),
    )
    block_store.create(
        section.id,
        ContentBlockCreate(
            type=BlockType.code_block,
            code_content="uvicorn app.main:app --reload",
            keyword_metadata="bash",
        ),
    )
    block_store.create(
        section.id,
        ContentBlockCreate(
            type=BlockType.image,
            image_url="https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
            keyword_metadata="FastAPI logo",
        ),
    )

    # A checkpoint block. A reader answers it on their own reading session.
    block_store.create(
        section.id,
        ContentBlockCreate(type=BlockType.checkpoint, title="Confirm it runs"),
    )
    return projects


if __name__ == "__main__":
    created = seed()
    print("Seeded projects:")
    for project in created:
        print(f"  id={project.id}  {project.name}")
    print(
        "\nTry:\n"
        f"  curl localhost:8000/projects/{created[0].id}/sections/1/blocks\n"
        "  # a reader starts a pinned snapshot session:\n"
        f"  curl -X POST localhost:8000/projects/{created[0].id}/sessions "
        "-H 'Content-Type: application/json' -d '{\"user_id\": \"userA\"}'"
    )
