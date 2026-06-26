# Interactive Lessons

A FastAPI service for authoring interactive lessons: projects built from
ordered sections of rich content blocks (Markdown, images, code) and
checkpoints, with per-reader snapshot sessions, progress, and optimistic
concurrency. SQLAlchemy + SQLite persistence, typed Pydantic schemas, thin
routers, and a `unittest` suite.

## Layout

```
app/
  main.py        # FastAPI app + router wiring
  config.py      # env-driven settings
  models.py      # Pydantic request/response schemas
  db.py          # SQLAlchemy engine, session, ORM tables
  store.py       # repository mapping ORM <-> Pydantic (same interface as before)
  auth.py        # password hashing, JWT, current-user dependency
  seed.py        # sample happy-path data (python -m app.seed)
  cleanup.py     # prune idle reading sessions (python -m app.cleanup)
  concurrency.py # optimistic-locking helper (If-Match -> 409)
  routers/
    health.py      # GET /health
    auth.py        # register / login / me
    projects.py    # CRUD /projects
    sections.py    # CRUD /projects/{id}/sections
    blocks.py      # CRUD /projects/{id}/sections/{id}/blocks
    checkpoints.py # read /projects/{id}/sections/{id}/checkpoints
    sessions.py    # reader snapshots + responses /projects/{id}/sessions
tests/           # unittest + TestClient (in-memory DB)
```

## Authentication

Register and log in for a JWT access token; send it as
`Authorization: Bearer <token>` on protected requests.

```
POST /auth/register   {email, password}     -> the new user
POST /auth/login      form: username=email&password=...  -> {access_token}
GET  /auth/me         (bearer token)         -> the current user
```

**Authorization model:**

- **Reading is public** — anyone can `GET` projects, sections, blocks, checkpoints.
- **Authoring requires the owner** — creating a project sets you as its
  `owner_id`; only the owner may add/delete its sections and blocks (else `403`,
  or `401` if unauthenticated).
- **Reading sessions require a login** — a session belongs to the authenticated
  user (the old free-text `user_id` is gone); only that user can read, refresh,
  or respond to it. One session per (project, user).

```bash
# register + log in
curl -X POST localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "me@example.com", "password": "password123"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -d 'username=me@example.com&password=password123' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# author a project (you become its owner)
curl -X POST localhost:8000/projects -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "My Lesson"}'
```

> Config: set a real `JWT_SECRET_KEY` in production (the default is a dev
> placeholder). Token lifetime is `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Content model

A **project** is built from ordered **sections** ("steps"). Each section
renders an ordered list of **content blocks**, and a block is one of:

| `type`        | required field  | notes |
|---------------|-----------------|-------|
| `text`        | `text_content`  | **Markdown** rich text — links & inline code live in here |
| `code_block`  | `code_content`  | `keyword_metadata` can hold the language |
| `image`       | `image_url`     | `keyword_metadata` can hold alt text |
| `checkpoint`  | `title`         | creates a checkpoint a reader answers |

Inline elements — links (`[label](url)`), inline code (`` `x` ``), bold, etc.
— are **not** separate blocks; they're written into a `text` block's Markdown.

Blocks are returned ordered by `position` (auto-appended when omitted), so a
client renders a whole section in one query. A `checkpoint` block points at a
**checkpoint** (a `title`); a reader's answers to it live on their reading
session (below), not on the shared content. The authoring tree:

```
POST /projects                                  {name, description?}
POST /projects/{pid}/sections                   {title?, position?}
POST /projects/{pid}/sections/{sid}/blocks      {type, ...type fields}
GET  /projects/{pid}/sections/{sid}/blocks      ordered blocks (checkpoints embedded)
GET  /projects/{pid}/sections/{sid}/checkpoints checkpoints in the section
```

Deleting a project, section, or checkpoint block cascades to its descendants
(enforced at the DB level via SQLite foreign keys).

```bash
# a Markdown text block (note the inline link and inline code), then a code block
curl -X POST localhost:8000/projects/1/sections/1/blocks \
  -H "Content-Type: application/json" \
  -d '{"type": "text", "text_content": "Read the [docs](https://fastapi.tiangolo.com), then run `make test`."}'

curl -X POST localhost:8000/projects/1/sections/1/blocks \
  -H "Content-Type: application/json" \
  -d '{"type": "code_block", "code_content": "uvicorn app.main:app", "keyword_metadata": "bash"}'
```

## Reading sessions (concurrent readers vs. editors)

An author (User B) autosaves edits to a project while a reader (User A) is
working through it. To keep A's view stable, A starts a **reading session**,
which freezes an immutable **snapshot** of the project's content. A renders
from the snapshot, so B's later edits never disturb them; A opts in to the
latest via `/refresh`. A reader's checkpoint **responses** live on their own
session, so two readers never collide.

The snapshot is a short **stability window**, not a permanent fork:

- There is **one session per (project, reader)** — re-posting resumes the
  existing one instead of piling up a new snapshot per visit.
- The session reports **`is_stale`** and **`latest_version`**, so the client
  knows when A is behind and can prompt "Get latest."
- Sessions track `last_accessed_at` and are **pruned by TTL**
  (`session_ttl_seconds`, default 7 days). They're cleaned up opportunistically
  when any reader starts a session; for projects that go quiet, point a
  scheduler (cron, k8s `CronJob`, …) at the CLI backstop:

  ```bash
  python -m app.cleanup                    # use the configured TTL
  python -m app.cleanup --max-age-seconds 3600
  ```

All session routes require a bearer token; the user comes from it.

```
POST /projects/{pid}/sessions                   (auth) -> snapshot (start or resume)
GET  /projects/{pid}/sessions/{sid}             the reader's view (+ is_stale, latest_version)
POST /projects/{pid}/sessions/{sid}/refresh     re-snapshot ("Get latest")
POST /projects/{pid}/sessions/{sid}/checkpoints/{cid}/responses   {text?, link?, label?}
```

Content edits use **optimistic concurrency**: a project's `version` is returned
as an `ETag`, and an editor may send `If-Match: <version>` on a write. A stale
write gets **`409 Conflict`** instead of clobbering a newer edit; omitting the
header is last-write-wins.

```bash
# a logged-in reader pins a snapshot
curl -X POST localhost:8000/projects/1/sessions -H "Authorization: Bearer $TOKEN"

# editor's stale write is rejected
curl -i -X POST localhost:8000/projects/1/sections/1/blocks \
  -H "Authorization: Bearer $TOKEN" -H "If-Match: 1" \
  -d '{"type": "text", "text_content": "..."}'      # -> 409 if version moved on
```

### Seed sample data

```bash
python -m app.seed   # a few projects + one fully-worked section
```

## Persistence

Data is stored in SQLite via SQLAlchemy. Each layer has one job:

- `db.py` — SQLAlchemy engine/session + the ORM tables (the database rows).
  `make_engine()` creates the DB's parent directory and turns on SQLite
  foreign-key enforcement, so parent/child deletes cascade at the DB level.
- `models.py` — Pydantic schemas for request/response validation (the API shape).
- `store.py` — thin repositories that map between the two.

The database file path lives in `config.py` (`settings.database_path`),
env-driven via `DATABASE_PATH` (default `interactive_lessons.db`, created on first
run). Use `:memory:` for an ephemeral database — the test suite does this so
it never touches the real file.

Config is managed by `pydantic-settings`: values are typed and validated, and
can be set via environment variables or a local `.env` file (git-ignored).
`APP_NAME`, `DEBUG`, and `DATABASE_PATH` are all overridable this way.

```bash
DATABASE_PATH=/tmp/app.db uvicorn app.main:app --reload
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs

# test
python -m unittest discover -s tests -v
```

## Docker

```bash
docker build -t interactive-lessons .
docker run -p 8000:8000 interactive-lessons
```

## Extending

- New resource: add a schema in `models.py`, an ORM table in `db.py`, a
  repository in `store.py`, and a router in `routers/` included in `main.py`.
  Mirror `projects.py`.
- Persistence: swap the SQLAlchemy backing in `db.py`/`store.py`; router
  signatures stay the same.
- Config: add a field to `Settings` in `config.py` (env-driven via
  pydantic-settings).
