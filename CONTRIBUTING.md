# Contributing

Thank you for taking the time to contribute. This document explains how to set up your environment, how the codebase is organised, and what we expect before you submit a pull request.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Branch Naming](#branch-naming)
- [Commit Messages](#commit-messages)
- [Backend: Linting and Formatting](#backend-linting-and-formatting)
- [Frontend: Linting and Type Checking](#frontend-linting-and-type-checking)
- [Running Tests](#running-tests)
- [Database Migrations](#database-migrations)
- [Pull Request Checklist](#pull-request-checklist)
- [What We Will Not Merge](#what-we-will-not-merge)

---

## Development Setup

All you need is Docker 24+ and an Anthropic API key.

```bash
git clone https://github.com/rmusayevr/simurgh-ai.git
cd simurgh-ai
make install   # copies .env, builds images, migrates DB, seeds demo data
make dev       # starts the full stack with hot-reload
make superuser # create your admin account
```

The frontend dev server runs at http://localhost:5173 with hot-reload. The backend runs at http://localhost:8000 with auto-reload via Uvicorn. Run `make help` to see all available commands.

---

## Project Structure

```
backend/app/
├── api/v1/endpoints/   # Route handlers — one file per resource
├── core/               # Config, security, encryption, Celery
├── models/             # SQLModel ORM table definitions
├── schemas/            # Pydantic request/response schemas
├── services/           # Business logic (ai_service, debate_service, etc.)
└── main.py             # FastAPI app factory

frontend/src/
├── api/                # Typed Axios client
├── components/         # Reusable UI components
├── config/             # App configuration (including experiment.ts)
├── context/            # React context (auth state)
├── hooks/              # Custom React hooks
├── pages/              # Full-page route components
└── types/index.ts      # TypeScript types — kept in sync with backend enums
```

When adding a new feature, the typical change set is:
1. `models/` — add or modify the SQLModel table
2. `schemas/` — add Pydantic request/response schemas
3. `services/` — implement business logic
4. `api/v1/endpoints/` — expose the endpoint
5. `frontend/src/types/index.ts` — mirror any new enums
6. `frontend/src/api/client.ts` — add the typed API call
7. `frontend/src/components/` or `pages/` — build the UI

---

## Branch Naming

Use the following prefixes:

| Prefix | Use for |
|---|---|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `chore/` | Tooling, dependencies, config changes |
| `refactor/` | Code restructuring without behaviour change |
| `test/` | Adding or fixing tests |

Examples: `feat/jira-oauth`, `fix/rag-cross-project-leak`, `docs/proposal-generation`

---

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`

**Examples:**
```
feat(debate): add extended thinking support to consensus check
fix(rag): scope vector search to current project only
docs(api): add authentication note to API reference
chore(deps): upgrade anthropic SDK to 0.76.0
```

Keep the subject line under 72 characters. Use the body to explain *why*, not *what*.

---

## Backend: Linting and Formatting

The backend uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting.

```bash
# Via Makefile (recommended)
make lint-backend          # check lint + formatting
make fmt                   # auto-fix lint and formatting

# Or directly via Docker
docker compose exec backend ruff check .
docker compose exec backend ruff check . --fix
docker compose exec backend ruff format .
docker compose exec backend ruff format . --check
```

Ruff is configured in `backend/ruff.toml`. Alembic migration files in `alembic/versions/` are excluded from linting automatically.

**All lint and format checks must pass before submitting a PR.**

---

## Frontend: Linting and Type Checking

```bash
# Via Makefile (recommended)
make lint-frontend          # ESLint + tsc

# Or directly
cd frontend
npm run lint
npx tsc --noEmit
```

Keep `frontend/src/types/index.ts` in sync with the backend enums at all times. Any new Python `Enum` added to `backend/app/models/` needs a matching TypeScript constant added to `types/index.ts`.

---

## Running Tests

Tests are organised into four levels. Always run at least unit tests before submitting:

```bash
# Via Makefile (recommended)
make test                  # all tiers
make test-unit             # fast, no DB required
make test-api              # mocked DB
make test-integration      # real PostgreSQL + Redis
make test-e2e              # full stack

# Or directly with coverage
docker compose exec backend pytest --cov=app --cov-report=term-missing
```

**Guidelines for new tests:**
- Unit tests go in `tests/unit/` — mock all external dependencies
- New service methods need at least one unit test
- New API endpoints need at least one API test covering the happy path
- Mark slow tests with `@pytest.mark.slow`

---

## Database Migrations

If your change modifies a SQLModel table definition, you must include a migration:

```bash
# Auto-generate a migration from model changes
docker compose exec backend alembic revision --autogenerate -m "describe your change"

# Review the generated file in backend/alembic/versions/ before committing
# Auto-generated migrations are not always correct — check them carefully

# Apply and verify it works
docker compose exec backend alembic upgrade head

# Verify rollback works
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic upgrade head
```

**Never edit an existing migration file** that has already been applied to any environment. Always create a new one.

---

## Pull Request Checklist

Before opening a PR, confirm the following:

```
□ ruff check . passes with no errors
□ ruff format . --check passes (no formatting changes needed)
□ npx tsc --noEmit passes on the frontend
□ npm run lint passes on the frontend
□ All existing tests pass: pytest tests/unit/ -v
□ New code has tests (unit tests at minimum)
□ New SQLModel table changes include an Alembic migration
□ New backend enums are mirrored in frontend/src/types/index.ts
□ CHANGELOG.md has been updated under [Unreleased]
□ PR description explains what changed and why
□ No secrets, API keys, or .env files are included in the commit
```

---

## What We Will Not Merge

- Code that breaks existing tests without a clear justification
- Changes that add hardcoded secrets, API keys, or credentials anywhere in the codebase
- Frontend changes that break the TypeScript build (`tsc --noEmit`)
- Database model changes without a corresponding Alembic migration
- Large refactors without prior discussion in an issue