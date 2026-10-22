from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker

from app.persistence.models import Incident, InvestigationExecution, LabBlockEntry, ResponseAction, ResponseAuditEvent
from app.workers.responses import ResponseProcessor, claim_next_response_action, complete_response_action, fail_response_action, utc_now


pytestmark = pytest.mark.integration


def approved_action(db_session, ip: str = "8.8.8.8") -> ResponseAction:
    incident = Incident(title="Containment test", severity="high", status="new")
    db_session.add(incident)
    db_session.flush()
    investigation = InvestigationExecution(incident_id=incident.id, investigation_type="suspicious_ip", status="completed", attempt_count=1, source_ip=ip)
    db_session.add(investigation)
    db_session.flush()
    action = ResponseAction(incident_id=incident.id, investigation_id=investigation.id, action_type="block_ip", target_ip=ip, status="approved", proposed_by="analyst_api_key", decided_by="analyst_api_key")
    db_session.add(action)
    db_session.commit()
    return action


def finish_existing_claimable_actions(db_session) -> None:
    db_session.execute(update(ResponseAction).where(ResponseAction.status.in_(("approved", "executing"))).values(status="failed", lease_token=None, lease_owner=None, lease_expires_at=None))
    db_session.commit()


def test_only_approved_actions_execute_and_effect_is_idempotent(db_session, test_engine) -> None:
    finish_existing_claimable_actions(db_session)
    proposed = approved_action(db_session, "8.8.8.8")
    proposed.status = "proposed"
    rejected = approved_action(db_session, "1.1.1.1")
    rejected.status = "rejected"
    executable = approved_action(db_session, "9.9.9.9")
    db_session.commit()
    processor = ResponseProcessor(sessionmaker(bind=test_engine, autoflush=False, autocommit=False), "worker-a", 60, 3)
    assert processor.process_once() is True
    db_session.expire_all()
    assert db_session.get(ResponseAction, executable.id).status == "executed"
    assert db_session.get(ResponseAction, proposed.id).status == "proposed"
    assert db_session.get(ResponseAction, rejected.id).status == "rejected"
    assert db_session.scalar(select(func.count()).select_from(LabBlockEntry).where(LabBlockEntry.response_action_id == executable.id)) == 1
    assert processor.process_once() is False


def test_competing_claims_expiry_and_stale_completion_are_safe(db_session, test_engine) -> None:
    finish_existing_claimable_actions(db_session)
    action = approved_action(db_session)
    sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with sessions() as first, sessions() as second:
        claim = claim_next_response_action(first, "worker-a", 60, 3)
        assert claim is not None
        assert claim_next_response_action(second, "worker-b", 60, 3) is None
    with sessions() as expiry:
        expiry.get(ResponseAction, action.id).lease_expires_at = utc_now() - timedelta(seconds=1)
        expiry.commit()
    with sessions() as recovery:
        recovered = claim_next_response_action(recovery, "worker-b", 60, 3)
        assert recovered is not None
        assert recovered.lease_token != claim.lease_token
    with sessions() as stale:
        assert complete_response_action(stale, claim, "worker-a") is False
    with sessions() as completion:
        assert complete_response_action(completion, recovered, "worker-b") is True


def test_failure_is_terminal_and_audited(db_session, test_engine) -> None:
    finish_existing_claimable_actions(db_session)
    action = approved_action(db_session)
    sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with sessions() as session:
        claim = claim_next_response_action(session, "worker-a", 60, 3)
        assert claim is not None
    with sessions() as session:
        assert fail_response_action(session, claim, "worker-a", RuntimeError("simulated adapter failure"))
    db_session.expire_all()
    stored = db_session.get(ResponseAction, action.id)
    assert stored.status == "failed"
    assert stored.execution_error == "simulated adapter failure"
    assert db_session.scalar(select(func.count()).select_from(ResponseAuditEvent).where(ResponseAuditEvent.response_action_id == action.id, ResponseAuditEvent.event_type == "response_execution_failed")) == 1


def test_authenticated_revert_only_releases_its_own_simulated_block(db_session, api_client, analyst_headers, test_engine) -> None:
    finish_existing_claimable_actions(db_session)
    first = approved_action(db_session, "8.8.4.4")
    second = approved_action(db_session, "8.8.4.4")
    processor = ResponseProcessor(sessionmaker(bind=test_engine, autoflush=False, autocommit=False), "worker-a", 60, 3)
    assert processor.process_once() and processor.process_once()
    assert api_client.post(f"/api/v1/response-actions/{first.id}/revert", json={"reason": "exercise complete"}).status_code == 401
    reverted = api_client.post(f"/api/v1/response-actions/{first.id}/revert", json={"reason": "exercise complete"}, headers=analyst_headers)
    assert reverted.status_code == 200
    assert reverted.json()["status"] == "reverted"
    assert api_client.post(f"/api/v1/response-actions/{first.id}/revert", json={}, headers=analyst_headers).status_code == 409
    entries = api_client.get("/api/v1/lab/blocklist?active=true", headers=analyst_headers)
    assert entries.status_code == 200
    assert any(item["response_action_id"] == str(second.id) for item in entries.json()["items"])
    assert not any(item["response_action_id"] == str(first.id) for item in entries.json()["items"])
    db_session.expire_all()
    events = db_session.scalars(select(ResponseAuditEvent.event_type).where(ResponseAuditEvent.response_action_id == first.id)).all()
    assert "response_reverted" in events
