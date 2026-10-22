# SOAR Lite

Local-first Security Orchestration, Automation and Response (SOAR) MVP for a two-day build sprint.

## MVP scope

The demonstration flow is: Alert → Incident → Investigation → Analyst Approval → simulated Lab Response → Audit Log. Containment is exclusively a PostgreSQL-backed lab blocklist: this project never modifies host networking, iptables/nftables/UFW, Docker networking, cloud firewalls, routers, or real infrastructure.

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

The backend runs Alembic migrations before starting. To run them manually:

```bash
cd backend && uv run alembic upgrade head
```

Configure non-placeholder `WEBHOOK_SECRET` and `ANALYST_API_KEY` in your untracked `.env`, then submit an alert:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest/generic \
  -H "Authorization: Bearer $WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  --data '{"event_id":"test-alert-001","event_type":"suspicious_login","severity":"high","observed_at":"2026-10-21T16:00:00Z","source_ip":"198.51.100.23","destination_host":"lab-server-01","rule":"Repeated failed login attempts","metadata":{"failed_attempts":12}}'

curl -H "X-API-Key: $ANALYST_API_KEY" http://127.0.0.1:8000/api/v1/incidents
```

After an investigation is completed, an analyst can propose and approve its IP; the worker persists a simulated block. Use `GET /api/v1/lab/blocklist` to view the PostgreSQL-only lab state and `POST /api/v1/response-actions/{action_id}/revert` to release that action's block.

## Reproducible demonstration

1. Configure untracked `.env` values for `WEBHOOK_SECRET` and `ANALYST_API_KEY`; do not put either value in frontend files. Start the local stack:

```bash
docker compose --env-file .env -f infra/compose.yaml up -d --build
```

2. Submit the webhook shown above with a globally routable source IP, then open `http://127.0.0.1:5173` and enter the analyst key in the development-only connection panel. Inspect the created incident and completed investigation evidence.
3. In **Response Actions**, choose the completed investigation, create the `block_ip` proposal, approve it, and wait for the worker to mark it `executed`. Inspect its persisted audit timeline and `Lab Blocklist` entry.
4. Revert the executed action with an analyst reason. The action becomes `reverted` and its action-owned lab entry becomes inactive. This is simulated containment only: no host firewall, iptables/nftables/UFW, Docker networking, cloud security group, router, or production network is changed.

The backend command applies migrations at startup. To apply them explicitly instead:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm backend alembic upgrade head
```

## Verification

```bash
cd backend && uv run pytest
cd frontend && npm run build
docker compose --env-file .env -f infra/compose.yaml config
```

The end-to-end acceptance test requires a deliberately disposable database URL containing `soar_lite_test`; never point it at the normal application database:

```bash
cd backend && TEST_DATABASE_URL=postgresql+psycopg://.../soar_lite_test uv run pytest -q tests/test_end_to_end_acceptance_postgres.py
```

## Graphify

Graphify is available as a CLI in the development environment. Its project-scoped Codex integration should live under `.codex/skills/graphify` after running the installer. In this environment the installer could not write the sandbox-mounted `.codex` directory; see `context.md`. Generate a graph once meaningful backend code exists:

```bash
graphify .
graphify query "How are alerts processed?"
```

## Upcoming milestones

1. Verify ingestion against local PostgreSQL and complete the acceptance demonstration.
2. Suspicious-IP investigation and intelligence enrichment.
3. Analyst approval, controlled lab response, and audit trails.
4. Incident-response console and end-to-end verification.
