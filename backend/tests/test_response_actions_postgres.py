from uuid import UUID, uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.api.responses import _decide
from app.domain.responses.schemas import ResponseDecisionIn
from app.persistence.models import Incident, InvestigationExecution, ResponseAction, ResponseAuditEvent


pytestmark = pytest.mark.integration


def completed_investigation(db_session, source_ip: str = "8.8.8.8") -> tuple[Incident, InvestigationExecution]:
    incident = Incident(title="Suspicious IP", severity="high", status="new")
    db_session.add(incident)
    db_session.flush()
    investigation = InvestigationExecution(
        incident_id=incident.id,
        investigation_type="suspicious_ip",
        status="completed",
        attempt_count=1,
        source_ip=source_ip,
    )
    db_session.add(investigation)
    db_session.commit()
    return incident, investigation


def proposal_payload(investigation: InvestigationExecution, target_ip: str = "8.8.8.8") -> dict[str, str]:
    return {"investigation_id": str(investigation.id), "target_ip": target_ip}


def test_proposal_auth_validation_and_duplicate_protection(db_session, api_client, analyst_headers) -> None:
    incident, investigation = completed_investigation(db_session)
    url = f"/api/v1/incidents/{incident.id}/response-actions"
    assert api_client.post(url, json=proposal_payload(investigation)).status_code == 401
    assert api_client.post(f"/api/v1/incidents/{uuid4()}/response-actions", json=proposal_payload(investigation), headers=analyst_headers).status_code == 404
    assert api_client.post(url, json=proposal_payload(investigation, "10.1.1.1"), headers=analyst_headers).status_code == 422
    assert api_client.post(url, json=proposal_payload(investigation, "1.1.1.1"), headers=analyst_headers).status_code == 422

    created = api_client.post(url, json=proposal_payload(investigation), headers=analyst_headers)
    assert created.status_code == 201
    assert created.json()["status"] == "proposed"
    assert created.json()["proposed_by"] == "analyst_api_key"
    assert api_client.post(url, json=proposal_payload(investigation), headers=analyst_headers).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(ResponseAuditEvent).where(ResponseAuditEvent.response_action_id == UUID(created.json()["id"]))) == 1


def test_proposal_requires_completed_associated_investigation(db_session, api_client, analyst_headers) -> None:
    incident, investigation = completed_investigation(db_session)
    unrelated, other_investigation = completed_investigation(db_session, "1.1.1.1")
    url = f"/api/v1/incidents/{incident.id}/response-actions"
    assert api_client.post(url, json=proposal_payload(other_investigation, "1.1.1.1"), headers=analyst_headers).status_code == 422
    investigation.status = "queued"
    db_session.commit()
    assert api_client.post(url, json=proposal_payload(investigation), headers=analyst_headers).status_code == 409


def test_approval_rejection_conflicts_and_audit_detail(db_session, api_client, analyst_headers) -> None:
    incident, investigation = completed_investigation(db_session)
    created = api_client.post(f"/api/v1/incidents/{incident.id}/response-actions", json=proposal_payload(investigation), headers=analyst_headers)
    action_id = UUID(created.json()["id"])
    approved = api_client.post(f"/api/v1/response-actions/{action_id}/approve", json={"reason": "Reviewed investigation"}, headers=analyst_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decision_reason"] == "Reviewed investigation"
    assert api_client.post(f"/api/v1/response-actions/{action_id}/reject", json={}, headers=analyst_headers).status_code == 409
    assert api_client.post(f"/api/v1/response-actions/{action_id}/approve", json={}, headers=analyst_headers).status_code == 409

    detail = api_client.get(f"/api/v1/response-actions/{action_id}", headers=analyst_headers)
    assert detail.status_code == 200
    assert [event["event_type"] for event in detail.json()["audit_events"]] == ["response_proposed", "response_approved"]
    assert db_session.get(ResponseAction, action_id).status == "approved"

    second_incident, second_investigation = completed_investigation(db_session, "9.9.9.9")
    second = api_client.post(f"/api/v1/incidents/{second_incident.id}/response-actions", json=proposal_payload(second_investigation, "9.9.9.9"), headers=analyst_headers)
    rejected_id = second.json()["id"]
    assert api_client.post(f"/api/v1/response-actions/{rejected_id}/reject", json={"reason": "False positive"}, headers=analyst_headers).status_code == 200
    assert api_client.post(f"/api/v1/response-actions/{rejected_id}/approve", json={}, headers=analyst_headers).status_code == 409


def test_response_action_list_is_authenticated_and_filterable(db_session, api_client, analyst_headers) -> None:
    incident, investigation = completed_investigation(db_session)
    api_client.post(f"/api/v1/incidents/{incident.id}/response-actions", json=proposal_payload(investigation), headers=analyst_headers)
    assert api_client.get("/api/v1/response-actions").status_code == 401
    listed = api_client.get("/api/v1/response-actions?action_status=proposed&page=1&page_size=1", headers=analyst_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert all(item["status"] == "proposed" for item in listed.json()["items"])


def test_concurrent_conflicting_decisions_create_one_transition_and_audit(db_session, test_engine) -> None:
    incident, investigation = completed_investigation(db_session)
    action = ResponseAction(
        incident_id=incident.id,
        investigation_id=investigation.id,
        action_type="block_ip",
        target_ip="8.8.8.8",
        status="proposed",
        proposed_by="analyst_api_key",
    )
    db_session.add(action)
    db_session.commit()
    action_id = action.id
    sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def decide(status: str) -> int:
        with sessions() as session:
            try:
                _decide(action_id, ResponseDecisionIn(), session, status)  # type: ignore[arg-type]
                return 200
            except Exception as exc:
                session.rollback()
                return getattr(exc, "status_code", 500)

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(decide, ("approved", "rejected")))
    assert sorted(statuses) == [200, 409]
    db_session.expire_all()
    stored = db_session.get(ResponseAction, action_id)
    assert stored.status in {"approved", "rejected"}
    assert db_session.scalar(select(func.count()).select_from(ResponseAuditEvent).where(ResponseAuditEvent.response_action_id == action_id)) == 1
