# API conventions

API endpoints are versioned under `/api/v1`. JSON is the default representation. Current implementation: `GET /api/v1/health`, a liveness route that does not access PostgreSQL. Authenticated webhook and analyst APIs are planned.
