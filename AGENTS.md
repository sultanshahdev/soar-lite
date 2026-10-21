# SOAR Lite Agent Guide

## Project mission

Ship one complete, demonstrable local-first SOAR MVP within two days.

## Architecture

Use a modular monolith: FastAPI API and a separate Python worker process share application code and PostgreSQL. Keep the React client separate. Avoid unnecessary frameworks, microservices, Kubernetes, Celery, Redis, Temporal, AI models, and additional databases.

## Code organization

Keep API routes, domain logic, persistence, workflows, connectors, and workers logically separated. Keep integrations behind connector boundaries.

## Engineering standards

- Prefer readable, maintainable code with type annotations.
- Validate external inputs and keep modules focused.
- Avoid unnecessary abstractions and minimize dependencies.
- Implement small, testable increments.

## Security standards

- Never execute untrusted shell commands or change the host firewall.
- Do not commit secrets.
- Validate webhook inputs.
- Require analyst approval before containment.
- Use restricted integrations and allowlisted destinations.
- Record security-sensitive actions.

## AI agent workflow

Before substantial implementation: read this file and `context.md`; inspect relevant code; consult Graphify when a useful knowledge graph exists; implement the smallest complete change; run relevant tests; and update `context.md` only after verification.

## Scope discipline

Never implement unrelated enterprise features or expand scope without authorization. Do not add an autonomous multi-agent framework.

## Definition of done

A feature is complete only when implementation and relevant verification succeed. Document any verification that could not be performed.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
