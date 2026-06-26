# Interactive Lessons

A full-stack app for authoring and following interactive, step-by-step lessons:
projects built from ordered sections of rich content blocks (Markdown, images,
code) and checkpoints, with per-reader snapshot sessions, progress, optimistic
concurrency, and JWT auth.

## Monorepo layout

```
backend/    FastAPI + SQLAlchemy + SQLite API   (see backend/README.md)
frontend/   Next.js (App Router, TypeScript, Tailwind) client
```

The frontend talks to the backend over HTTP; the backend enables CORS for the
frontend origin (`CORS_ORIGINS`, default `http://localhost:3000`).

## Run it locally

**Backend** (`http://localhost:8000`):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed                 # optional: sample data + an author login
uvicorn app.main:app --reload
```

**Frontend** (`http://localhost:3000`):

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://localhost:8000
npm run dev
```

Open http://localhost:3000 — the home page lists projects from the API; `/login`
registers and signs in (the verification link is printed in the backend logs by
the console email backend).

## Tests

```bash
cd backend && python -m unittest discover -s tests -v   # 43 tests
cd frontend && npm run build                            # type-check + lint
```

See [backend/README.md](backend/README.md) for the API, auth model, content
model, reading sessions, and ops (seed / cleanup / promote).
