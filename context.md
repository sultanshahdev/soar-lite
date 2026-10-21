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
| 2. Alert ingestion and incident persistence | Planned | Not implemented. |
| 3. Investigation workflow and intelligence enrichment | Planned | Not implemented. |
| 4. Approval and controlled laboratory response | Planned | Not implemented. |
| 5. React incident-response console | Planned | Not implemented. |
| 6. End-to-end testing and local deployment | Planned | Not implemented. |

## Handoff

Most recent verified progress (2026-10-21): Git is initialized on `main` but has no commits yet; project files are staged and an unexpected untracked `tatus` file exists. `AGENTS.md` and this context file are present. Graphify 0.9.59 and its project Codex skill (`.codex/skills/graphify/SKILL.md`) are present. Backend dependencies import successfully (FastAPI 0.158.0; SQLAlchemy 2.1.6), and frontend dependencies are installed. `npm run build` passed. `docker compose --env-file .env -f infra/compose.yaml config` passed. Docker Compose is installed.

Health verification: calling `health_check()` returns `{"status": "ok", "service": "soar-lite"}`. The existing `pytest` test starts but hangs at `TestClient.get()`; a ten-second direct `TestClient` probe timed out. Installed versions were FastAPI 0.158.0, Starlette 1.9.0, and HTTPX 0.28.1, and Starlette emits a deprecation warning indicating that its test client expects `httpx2`. This must be resolved before considering the backend test suite fully verified.

Next actionable task: summarize this state, resolve the test-client dependency compatibility without broad dependency changes, then begin authenticated alert ingestion and incident persistence. No SOAR business logic has been implemented.
