# SOAR Lite

Local-first Security Orchestration, Automation and Response (SOAR) MVP for a two-day build sprint.

## MVP scope

The planned demonstration is: Alert → Incident → Playbook → Threat Intelligence → Analyst Approval → Lab Response → Audit Log. This repository currently contains only the foundation: a health endpoint, an idle worker process, database/migration wiring, and a static analyst-console shell. No security operations, external calls, or containment are implemented.

## Stack and architecture

FastAPI, Python 3.12, SQLAlchemy 2, Alembic, PostgreSQL, React, TypeScript, Vite, Tailwind CSS, and Docker Compose. It is a modular monolith with separately running API and worker processes sharing PostgreSQL.

## Layout

- `backend/` — FastAPI application, worker scaffold, migrations, and tests.
- `frontend/` — React/Vite analyst console scaffold.
- `infra/compose.yaml` — local PostgreSQL, backend, worker, and frontend services.
- `lab/` — reserved for the future isolated response service; not runnable yet.
- `playbooks/`, `fixtures/`, `docs/` — planned artifacts and design notes.

## Local setup

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 24+ with npm, and Docker Compose (for containers).

```bash
cp .env.example .env
cd backend && uv sync --all-groups
cd ../frontend && npm install
```

Run locally:

```bash
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm run dev
```

The liveness endpoint is `http://127.0.0.1:8000/api/v1/health`. To run the stack when Docker is available: `docker compose --env-file .env -f infra/compose.yaml up --build`.

## Verification

```bash
cd backend && uv run pytest
cd frontend && npm run build
docker compose --env-file .env -f infra/compose.yaml config
```

## Graphify

Graphify is available as a CLI in the development environment. Its project-scoped Codex integration should live under `.codex/skills/graphify` after running the installer. In this environment the installer could not write the sandbox-mounted `.codex` directory; see `context.md`. Generate a graph once meaningful backend code exists:

```bash
graphify .
graphify query "How are alerts processed?"
```

## Upcoming milestones

1. Authenticated alert ingestion and incident persistence.
2. Suspicious-IP investigation and intelligence enrichment.
3. Analyst approval, controlled lab response, and audit trails.
4. Incident-response console and end-to-end verification.
