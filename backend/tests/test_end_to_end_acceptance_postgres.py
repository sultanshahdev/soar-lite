"""One real-persistence acceptance path; the only mocked boundary is AbuseIPDB."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.connectors.abuseipdb import AbuseIPDBResult
from app.persistence.models import InvestigationExecution, ResponseAction
from app.workers.investigations import InvestigationProcessor
from app.workers.responses import ResponseProcessor


pytestmark = pytest.mark.integration


class DeterministicAbuseIPDB:
    async def check_ip(self, source_ip: str) -> AbuseIPDBResult:
        return AbuseIPDBResult(
            ip_address=source_ip,
            abuse_confidence_score=88,
            country_code="US",
            total_reports=4,
            looked_up_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_full_human_approved_simulated_response_lifecycle(db_session, api_client, webhook_headers, analyst_headers, test_engine) -> None:
    """Webhook through reversible simulated containment uses actual APIs and PostgreSQL state."""
    # Keep this acceptance path independent of approved/queued records from focused tests.
    db_session.execute(update(InvestigationExecution).where(InvestigationExecution.status.in_(("queued", "running"))).values(status="completed"))
    db_session.execute(update(ResponseAction).where(ResponseAction.status.in_(("approved", "executing"))).values(status="failed"))
    db_session.commit()

    payload = {
        "event_id": "acceptance-suspicious-ip-001",
        "event_type": "suspicious_login",
        "severity": "high",
        "observed_at": "2026-10-22T12:00:00Z",
        "source_ip": "8.8.8.8",
        "destination_host": "acceptance-host",
        "rule": "Acceptance suspicious login",
        "metadata": {"fixture": True},
    }
    ingested = api_client.post("/api/v1/ingest/generic", json=payload, headers=webhook_headers)
    assert ingested.status_code == 201
    incident_id = ingested.json()["incident_id"]
    duplicate = api_client.post("/api/v1/ingest/generic", json=payload, headers=webhook_headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["incident_id"] == incident_id

    investigation = db_session.scalar(select(InvestigationExecution).where(InvestigationExecution.incident_id == incident_id))
    assert investigation is not None
    assert investigation.status == "queued"
    worker_sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    assert await InvestigationProcessor(worker_sessions, DeterministicAbuseIPDB(), "acceptance-investigator", 60, 3, 1).process_once()
    db_session.expire_all()
    investigation = db_session.get(InvestigationExecution, investigation.id)
    assert investigation.status == "completed"
    assert len(investigation.evidence) == 1
    assert investigation.evidence[0].result["abuse_confidence_score"] == 88

    proposal_body = {"investigation_id": str(investigation.id), "target_ip": "8.8.8.8"}
    proposed = api_client.post(f"/api/v1/incidents/{incident_id}/response-actions", json=proposal_body, headers=analyst_headers)
    assert proposed.status_code == 201
    action_id = proposed.json()["id"]
    with worker_sessions() as verification_session:
        assert verification_session.get(ResponseAction, action_id).status == "proposed"
    assert api_client.post(f"/api/v1/response-actions/{action_id}/approve", json={}).status_code == 401
    approved = api_client.post(f"/api/v1/response-actions/{action_id}/approve", json={"reason": "Acceptance review"}, headers=analyst_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    assert ResponseProcessor(worker_sessions, "acceptance-responder", 60, 3).process_once()
    action_detail = api_client.get(f"/api/v1/response-actions/{action_id}", headers=analyst_headers)
    assert action_detail.status_code == 200
    assert action_detail.json()["status"] == "executed"
    assert {event["event_type"] for event in action_detail.json()["audit_events"]} >= {"response_proposed", "response_approved", "response_execution_started", "response_executed"}
    active_blocks = api_client.get("/api/v1/lab/blocklist?active=true", headers=analyst_headers)
    assert any(entry["response_action_id"] == action_id and entry["ip_address"] == "8.8.8.8" for entry in active_blocks.json()["items"])

    reverted = api_client.post(f"/api/v1/response-actions/{action_id}/revert", json={"reason": "Acceptance reversal"}, headers=analyst_headers)
    assert reverted.status_code == 200
    assert reverted.json()["status"] == "reverted"
    final_detail = api_client.get(f"/api/v1/response-actions/{action_id}", headers=analyst_headers)
    assert "response_reverted" in {event["event_type"] for event in final_detail.json()["audit_events"]}
    inactive_blocks = api_client.get("/api/v1/lab/blocklist?active=false", headers=analyst_headers)
    assert any(entry["response_action_id"] == action_id and not entry["active"] for entry in inactive_blocks.json()["items"])
