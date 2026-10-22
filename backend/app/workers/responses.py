"""Leased processor for approved PostgreSQL-only lab response actions."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.connectors.lab_response import LabResponseAdapter
from app.persistence.models import ResponseAction, ResponseAuditEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClaimedResponseAction:
    id: UUID
    lease_token: UUID
    target_ip: str
    incident_id: UUID


def claim_next_response_action(session: Session, worker_id: str, lease_seconds: int, max_attempts: int) -> ClaimedResponseAction | None:
    now = utc_now()
    available = or_(ResponseAction.status == "approved", and_(ResponseAction.status == "executing", ResponseAction.lease_expires_at.is_not(None), ResponseAction.lease_expires_at <= now))
    action = session.scalar(select(ResponseAction).where(available).order_by(ResponseAction.created_at, ResponseAction.id).with_for_update(skip_locked=True).limit(1))
    if action is None:
        session.commit()
        return None
    if action.execution_attempt_count >= max_attempts:
        action.status = "failed"
        action.execution_error = "response execution retry limit reached"
        action.lease_token = None
        action.lease_owner = None
        action.lease_expires_at = None
        session.add(ResponseAuditEvent(response_action_id=action.id, event_type="response_execution_failed", actor=worker_id, from_status="executing", to_status="failed", metadata_json={"attempt": action.execution_attempt_count, "reason": "retry_limit"}))
        session.commit()
        return None
    prior_status = action.status
    token = uuid4()
    action.status = "executing"
    action.execution_attempt_count += 1
    action.lease_token = token
    action.lease_owner = worker_id
    action.lease_expires_at = now + timedelta(seconds=lease_seconds)
    action.execution_error = None
    session.add(ResponseAuditEvent(response_action_id=action.id, event_type="response_execution_started", actor=worker_id, from_status=prior_status, to_status="executing", metadata_json={"attempt": action.execution_attempt_count, "recovered_lease": prior_status == "executing"}))
    session.commit()
    return ClaimedResponseAction(action.id, token, action.target_ip, action.incident_id)


def complete_response_action(session: Session, claim: ClaimedResponseAction, worker_id: str) -> bool:
    action = session.get(ResponseAction, claim.id)
    if action is None or action.status != "executing" or action.lease_token != claim.lease_token:
        return False
    result = LabResponseAdapter(session).block_ip(claim.target_ip, action.id, claim.incident_id)
    now = utc_now()
    action.status = "executed"
    action.executed_at = now
    action.execution_result = result
    action.execution_error = None
    action.lease_token = None
    action.lease_owner = None
    action.lease_expires_at = None
    session.add(ResponseAuditEvent(response_action_id=action.id, event_type="response_executed", actor=worker_id, from_status="executing", to_status="executed", metadata_json={"simulated": True, "attempt": action.execution_attempt_count}))
    session.commit()
    return True


def fail_response_action(session: Session, claim: ClaimedResponseAction, worker_id: str, error: Exception) -> bool:
    action = session.get(ResponseAction, claim.id)
    if action is None or action.status != "executing" or action.lease_token != claim.lease_token:
        return False
    action.status = "failed"
    action.execution_error = str(error)[:512]
    action.lease_token = None
    action.lease_owner = None
    action.lease_expires_at = None
    session.add(ResponseAuditEvent(response_action_id=action.id, event_type="response_execution_failed", actor=worker_id, from_status="executing", to_status="failed", metadata_json={"attempt": action.execution_attempt_count, "error_type": type(error).__name__}))
    session.commit()
    return True


class ResponseProcessor:
    def __init__(self, session_factory, worker_id: str, lease_seconds: int, max_attempts: int) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts

    def process_once(self) -> bool:
        with self._session_factory() as session:
            claim = claim_next_response_action(session, self._worker_id, self._lease_seconds, self._max_attempts)
        if claim is None:
            return False
        try:
            with self._session_factory() as session:
                complete_response_action(session, claim, self._worker_id)
        except Exception as exc:
            with self._session_factory() as session:
                fail_response_action(session, claim, self._worker_id, exc)
        return True
