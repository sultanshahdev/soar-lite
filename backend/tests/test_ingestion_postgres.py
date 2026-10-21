from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.persistence.models import Alert, Incident


pytestmark = pytest.mark.integration


def test_ingests_persists_and_retrieves_alert(api_client, db_session, alert_payload, webhook_headers, analyst_headers) -> None:
    created = api_client.post("/api/v1/ingest/generic", json=alert_payload, headers=webhook_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["accepted"] is True and body["duplicate"] is False

    assert db_session.scalar(select(func.count()).select_from(Alert)) == 1
    assert db_session.scalar(select(func.count()).select_from(Incident)) == 1
    alert = db_session.get(Alert, body["alert_id"])
    assert alert is not None and str(alert.incident_id) == body["incident_id"]

    duplicate = api_client.post("/api/v1/ingest/generic", json=alert_payload, headers=webhook_headers)
    assert duplicate.status_code == 200
    assert duplicate.json() == {**body, "duplicate": True}
    assert db_session.scalar(select(func.count()).select_from(Alert)) == 1
    assert db_session.scalar(select(func.count()).select_from(Incident)) == 1

    incident = api_client.get(f"/api/v1/incidents/{body['incident_id']}", headers=analyst_headers)
    assert incident.status_code == 200
    assert incident.json()["status"] == "new"
    assert incident.json()["severity"] == "high"
    assert incident.json()["alert_ids"] == [body["alert_id"]]

    listed = api_client.get("/api/v1/alerts?severity=high", headers=analyst_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert "raw_payload" not in listed.json()["items"][0]


def test_rejects_bad_credentials_invalid_payload_and_missing_resources(api_client, alert_payload, webhook_headers, analyst_headers) -> None:
    assert api_client.post("/api/v1/ingest/generic", json=alert_payload).status_code == 401
    malformed = {**alert_payload, "severity": "invalid"}
    assert api_client.post("/api/v1/ingest/generic", json=malformed, headers=webhook_headers).status_code == 422
    assert api_client.get("/api/v1/alerts", headers={}).status_code == 401
    assert api_client.get(f"/api/v1/alerts/{uuid4()}", headers=analyst_headers).status_code == 404
    assert api_client.get(f"/api/v1/incidents/{uuid4()}", headers=analyst_headers).status_code == 404
