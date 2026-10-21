# Architecture

SOAR Lite is a modular monolith. FastAPI serves the API, and a separate Python process will handle approved background work. Both use PostgreSQL. React provides the local analyst console. Integration adapters live under `backend/app/connectors`.

The laboratory response service is deliberately excluded until controlled containment is implemented.
