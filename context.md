# SOAR Lite Context

## Project

SOAR Lite — Local-First Security Orchestration, Automation and Response.

## Objective

Build a locally runnable MVP in two days, demonstrating alert ingestion, incident creation, security investigation, human approval, controlled response, and audit logging.

## Technology and architecture

FastAPI, Python, PostgreSQL, SQLAlchemy, Alembic, React, TypeScript, Vite, and Docker Compose. The application is a modular monolith with separate API and worker processes, persistent database, and registered integration adapters.

Initial playbook: suspicious IP investigation. Planned integrations: authenticated JSON webhook, AbuseIPDB, and an isolated reversible lab response service.

## Progress tracking

| Milestone | Status | Notes |
| --- | --- | --- |
| 1. Repository and infrastructure initialization | Verified with one test-environment blocker | Git, Graphify skill, dependencies, Docker Compose configuration, and frontend build were verified. The FastAPI `TestClient` health test hangs with the installed FastAPI/Starlette/HTTPX combination; direct health-handler verification passes. |
| 2. Alert ingestion and incident persistence | Implemented; PostgreSQL verification pending | Models, migration, authenticated ingestion/retrieval routes, deduplication, and tests are present. Test initialization now resets only the disposable test schema and applies Alembic through the same connection; sandbox loopback access prevents the final live run. |
| 3. Investigation workflow and intelligence enrichment | In progress | Task 3A investigation persistence is implemented; external enrichment and worker execution are not implemented. PostgreSQL verification remains pending. |
| 4. Approval and controlled laboratory response | Planned | Not implemented. |
| 5. React incident-response console | Planned | Not implemented. |
| 6. End-to-end testing and local deployment | Planned | Not implemented. |

## Handoff

Most recent verified progress (2026-10-21): Git is initialized on `main` but has no commits yet; project files are staged and an unexpected untracked `tatus` file exists. `AGENTS.md` and this context file are present. Graphify 0.9.59 and its project Codex skill (`.codex/skills/graphify/SKILL.md`) are present. Backend dependencies import successfully (FastAPI 0.158.0; SQLAlchemy 2.1.6), and frontend dependencies are installed. `npm run build` passed. `docker compose --env-file .env -f infra/compose.yaml config` passed. Docker Compose is installed.

Health verification: calling `health_check()` returns `{"status": "ok", "service": "soar-lite"}`. The existing `pytest` test starts but hangs at `TestClient.get()`; a ten-second direct `TestClient` probe timed out. Installed versions were FastAPI 0.158.0, Starlette 1.9.0, and HTTPX 0.28.1, and Starlette emits a deprecation warning indicating that its test client expects `httpx2`. This must be resolved before considering the backend test suite fully verified.

Most recent implementation (2026-10-21): generic webhook ingestion now validates event IDs, event types, severity, timezone-aware timestamps, and IP addresses; it persists the original payload as JSONB, atomically creates a `new` incident, and handles duplicate `(source, source_event_id)` submissions through a database constraint. Read APIs use a separate `X-API-Key` analyst credential. `WEBHOOK_SECRET` and `ANALYST_API_KEY` fail closed when missing or placeholders. The initial relationship is many-alerts-to-one-incident at the schema level, although this milestone creates one incident per alert.

PostgreSQL test initialization fix (2026-10-21): a prior test run could leave `alembic_version` at the latest revision after `Base.metadata.drop_all()` removed the tables. Alembic then correctly skipped the migration while the test client queried missing tables, producing `UndefinedTable: alerts`. The fixture now requires a URL containing `soar_lite_test`, resets only that database's `public` schema, and invokes `alembic upgrade head` with the exact same SQLAlchemy connection supplied to test sessions. Alembic's environment now honors `DATABASE_URL` for normal runs and an explicit Alembic connection for tests.

Verification: `pytest` reports `6 passed, 2 skipped` without `TEST_DATABASE_URL`; Alembic offline SQL generation verified both tables, JSONB storage, indexes, and the unique source/event constraint. A live integration run was attempted against `127.0.0.1:55432`, but the sandbox's network isolation returned `psycopg.OperationalError: connection is bad: no error details available`, so live database verification remains pending. Docker Compose configuration validates and the frontend build passes. Graphify was updated after the code change. No claim of end-to-end completion is made until the disposable PostgreSQL test database is exercised.

Next actionable task: run the documented disposable PostgreSQL integration test and acceptance flow, then proceed to suspicious-IP investigation and intelligence enrichment. No playbook execution, external enrichment, approvals, containment, or frontend workflow UI has been implemented.

Task 3A (2026-10-21): added persistent `InvestigationExecution` and `InvestigationEvidence` records, including retry scheduling, worker-lease, timestamps, and redacted-error fields. Migration `20261021_0002` preserves alerts and incidents. Authenticated analyst endpoints now list and retrieve investigations; details include evidence and both views include associated incident IDs. No investigation is automatically created and no worker or external API behavior exists.

Verification: model/schema tests and existing non-PostgreSQL tests pass (`7 passed`). Four PostgreSQL integration tests are skipped without `TEST_DATABASE_URL`, including the new investigation read/authorization coverage. Alembic offline SQL renders both new tables and their constraints. Graphify was updated. Task 3B must wait for live disposable-PostgreSQL verification of this migration and endpoint suite.
