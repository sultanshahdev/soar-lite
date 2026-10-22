from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import sessionmaker

from app.connectors.abuseipdb import AbuseIPDBResult, InvalidIPAddressError, ProviderUnavailableError
from app.persistence.models import Incident, InvestigationEvidence, InvestigationExecution
from app.workers.investigations import InvestigationProcessor, claim_next_investigation, utc_now


pytestmark = pytest.mark.integration


class SuccessConnector:
    async def check_ip(self, source_ip: str) -> AbuseIPDBResult:
        return AbuseIPDBResult(ip_address=source_ip, abuse_confidence_score=88, country_code="US", total_reports=10, looked_up_at=utc_now())


class FailingConnector:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def check_ip(self, source_ip: str):
        raise self.error


def finish_existing_claimable_investigations(db_session) -> None:
    """Keep each worker test independent from alerts queued by earlier tests."""
    db_session.execute(
        update(InvestigationExecution)
        .where(InvestigationExecution.status.in_(("queued", "running")))
        .values(status="completed", completed_at=utc_now(), lease_token=None, lease_owner=None, lease_expires_at=None)
    )
    db_session.commit()


def queued_investigation(db_session) -> UUID:
    incident = Incident(title="Suspicious IP", severity="high", status="new")
    db_session.add(incident)
    db_session.flush()
    execution = InvestigationExecution(incident_id=incident.id, investigation_type="suspicious_ip", status="queued", source_ip="8.8.8.8")
    db_session.add(execution)
    db_session.flush()
    execution_id = execution.id
    db_session.commit()
    return execution_id


@pytest.mark.asyncio
async def test_worker_claims_processes_and_persists_evidence(db_session, test_engine) -> None:
    finish_existing_claimable_investigations(db_session)
    execution_id = queued_investigation(db_session)
    worker_sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    processor = InvestigationProcessor(worker_sessions, SuccessConnector(), "worker-a", 60, 3, 10)
    assert await processor.process_once() is True
    with worker_sessions() as verification_session:
        stored = verification_session.get(InvestigationExecution, execution_id)
        assert stored.status == "completed"
        assert stored.attempt_count == 1
        assert verification_session.scalar(select(func.count()).select_from(InvestigationEvidence)) == 1


@pytest.mark.asyncio
async def test_worker_records_permanent_failure_and_retries_transient_failure(db_session, test_engine) -> None:
    finish_existing_claimable_investigations(db_session)
    worker_sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    permanent_id = queued_investigation(db_session)
    assert await InvestigationProcessor(worker_sessions, FailingConnector(InvalidIPAddressError("invalid")), "worker-a", 60, 3, 10).process_once()
    with worker_sessions() as verification_session:
        assert verification_session.get(InvestigationExecution, permanent_id).status == "failed"

    transient_id = queued_investigation(db_session)
    processor = InvestigationProcessor(worker_sessions, FailingConnector(ProviderUnavailableError("down")), "worker-a", 60, 3, 10)
    assert await processor.process_once()
    with worker_sessions() as verification_session:
        stored = verification_session.get(InvestigationExecution, transient_id)
        assert stored.status == "queued"
        assert stored.next_attempt_at is not None

    # Make each scheduled retry due and prove the configured limit is terminal.
    for expected_attempt in (2, 3):
        with worker_sessions() as scheduling_session:
            scheduling_session.get(InvestigationExecution, transient_id).next_attempt_at = utc_now() - timedelta(seconds=1)
            scheduling_session.commit()
        assert await processor.process_once()
        with worker_sessions() as verification_session:
            stored = verification_session.get(InvestigationExecution, transient_id)
            assert stored.attempt_count == expected_attempt

            if expected_attempt == 3:
                assert stored.status == "failed"
                assert stored.completed_at is not None
                assert stored.next_attempt_at is None


def test_competing_claims_and_expired_leases_are_safe(db_session, test_engine) -> None:
    finish_existing_claimable_investigations(db_session)
    execution_id = queued_investigation(db_session)
    worker_sessions = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with worker_sessions() as first_session, worker_sessions() as second_session:
        # An uncommitted row lock is skipped by a competing worker.
        first_session.scalar(
            select(InvestigationExecution)
            .where(InvestigationExecution.id == execution_id)
            .with_for_update(skip_locked=True)
        )
        assert claim_next_investigation(second_session, "worker-b", 60, 3) is None
        first_session.commit()

        # Once worker A atomically commits its claim, its active lease excludes worker B.
        first = claim_next_investigation(first_session, "worker-a", 60, 3)
        assert first is not None
        assert claim_next_investigation(second_session, "worker-b", 60, 3) is None

    with worker_sessions() as scheduling_session:
        scheduling_session.get(InvestigationExecution, execution_id).lease_expires_at = utc_now() - timedelta(seconds=1)
        scheduling_session.commit()
    with worker_sessions() as recovery_session:
        recovered = claim_next_investigation(recovery_session, "worker-b", 60, 3)
        assert recovered is not None
        assert recovered.lease_token != first.lease_token
    with worker_sessions() as verification_session:
        assert verification_session.get(InvestigationExecution, execution_id).lease_owner == "worker-b"
