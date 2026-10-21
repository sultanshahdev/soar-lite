# API conventions

API endpoints are versioned under `/api/v1`. JSON is the default representation. `GET /api/v1/health` is a liveness route and does not access PostgreSQL.

## Alert ingestion

`POST /api/v1/ingest/generic` accepts `application/json` and requires `Authorization: Bearer <WEBHOOK_SECRET>`. It rejects a missing, placeholder, or incorrect secret with `401`. Payloads are limited to 64 KiB when a `Content-Length` is provided.

```json
{
  "event_id": "test-alert-001",
  "event_type": "suspicious_login",
  "severity": "high",
  "observed_at": "2026-10-21T16:00:00Z",
  "source_ip": "198.51.100.23",
  "destination_host": "lab-server-01",
  "rule": "Repeated failed login attempts",
  "metadata": {"failed_attempts": 12, "window_seconds": 60}
}
```

Valid severity values are `low`, `medium`, `high`, and `critical`. Timestamps must include a timezone and are stored as UTC. IP addresses are validated with Python's `ipaddress` module. The unique `(source, source_event_id)` constraint provides idempotency: a repeat returns `200` and the original alert/incident identifiers with `duplicate: true`; a new event returns `201`.

## Analyst retrieval

`GET /alerts`, `GET /alerts/{alert_id}`, `GET /incidents`, and `GET /incidents/{incident_id}` require `X-API-Key: <ANALYST_API_KEY>`. List endpoints accept `page`, `page_size` (maximum 100), and `severity`; incidents also accept `incident_status` (`new`, `open`, or `closed`). List responses deliberately omit raw vendor payloads.

Every alert currently creates exactly one `new` incident. The relationship is `alerts.incident_id → incidents.id`, allowing future correlation to associate multiple alerts with one incident without schema replacement.
