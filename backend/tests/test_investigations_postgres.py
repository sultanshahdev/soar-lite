from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.persistence.models import Incident, InvestigationEvidence, InvestigationExecution


pytestmark = pytest.mark.integration


def test_lists_and_reads_investigations_with_evidence(db_session, api_client, analyst_headers) -> None:
    incident = Incident(title="Suspicious IP — lab-server-01", severity="high", status="new")
    db_session.add(incident)
    db_session.flush()
    investigation = InvestigationExecution(
        incident_id=incident.id,
        investigation_type="suspicious_ip",
        status="queued",
        attempt_count=0,
        source_ip="198.51.100.23",
        next_attempt_at=datetime.now(timezone.utc),
    )
    db_session.add(investigation)
    db_session.flush()
    db_session.add(InvestigationEvidence(investigation_id=investigation.id, evidence_source="manual_fixture", result={"score": 42}))
    db_session.commit()

    listed = api_client.get("/api/v1/investigations?investigation_status=queued", headers=analyst_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["incident_id"] == str(incident.id)

    detail = api_client.get(f"/api/v1/investigations/{investigation.id}", headers=analyst_headers)
    assert detail.status_code == 200
    assert detail.json()["source_ip"] == "198.51.100.23"
    assert len(detail.json()["evidence"]) == 1
    assert detail.json()["evidence"][0]["evidence_source"] == "manual_fixture"
    assert detail.json()["evidence"][0]["result"] == {"score": 42}


def test_investigation_endpoints_require_analyst_auth_and_handle_missing(api_client, analyst_headers) -> None:
    assert api_client.get("/api/v1/investigations").status_code == 401
    assert api_client.get(f"/api/v1/investigations/{uuid4()}", headers=analyst_headers).status_code == 404
