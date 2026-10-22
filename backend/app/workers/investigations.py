"""Small PostgreSQL-backed suspicious-IP investigation processor."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.connectors.abuseipdb import (
    AbuseIPDBConnector,
    AbuseIPDBError,
    ConnectorConfigurationError,
    InvalidIPAddressError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.persistence.models import InvestigationEvidence, InvestigationExecution


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClaimedInvestigation:
    id: UUID
    lease_token: UUID
    source_ip: str
    attempt_count: int


def claim_next_investigation(session: Session, worker_id: str, lease_seconds: int, max_attempts: int) -> ClaimedInvestigation | None:
    """Claim one due row using PostgreSQL row locks, then commit before I/O."""
    now = utc_now()
    session.execute(
        update(InvestigationExecution)
        .where(
            InvestigationExecution.status == "running",
            InvestigationExecution.lease_expires_at.is_not(None),
            InvestigationExecution.lease_expires_at <= now,
            InvestigationExecution.attempt_count >= max_attempts,
        )
        .values(status="failed", completed_at=now, lease_token=None, lease_owner=None, lease_expires_at=None, error_summary="retry limit reached")
    )
    available = or_(
        and_(
            InvestigationExecution.status == "queued",
            or_(InvestigationExecution.next_attempt_at.is_(None), InvestigationExecution.next_attempt_at <= now),
        ),
        and_(
            InvestigationExecution.status == "running",
            InvestigationExecution.lease_expires_at.is_not(None),
            InvestigationExecution.lease_expires_at <= now,
        ),
    )
    execution = session.scalar(
        select(InvestigationExecution)
        .where(available, InvestigationExecution.attempt_count < max_attempts)
        .order_by(InvestigationExecution.created_at, InvestigationExecution.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if execution is None:
        session.commit()
        return None

    token = uuid4()
    execution.status = "running"
    execution.attempt_count += 1
    execution.started_at = execution.started_at or now
    execution.lease_token = token
    execution.lease_owner = worker_id
    execution.lease_expires_at = now + timedelta(seconds=lease_seconds)
    execution.next_attempt_at = None
    execution.error_summary = None
    session.commit()
    return ClaimedInvestigation(execution.id, token, execution.source_ip, execution.attempt_count)


def complete_investigation(session: Session, claim: ClaimedInvestigation, result: dict[str, object]) -> None:
    execution = session.get(InvestigationExecution, claim.id)
    if execution is None or execution.status != "running" or execution.lease_token != claim.lease_token:
        return
    session.add(InvestigationEvidence(investigation_id=execution.id, evidence_source="abuseipdb", result=result))
    execution.status = "completed"
    execution.completed_at = utc_now()
    execution.lease_token = None
    execution.lease_owner = None
    execution.lease_expires_at = None
    execution.next_attempt_at = None
    execution.error_summary = None
    session.commit()


def fail_or_schedule_retry(
    session: Session,
    claim: ClaimedInvestigation,
    error: AbuseIPDBError,
    max_attempts: int,
    retry_base_seconds: int,
) -> None:
    execution = session.get(InvestigationExecution, claim.id)
    if execution is None or execution.status != "running" or execution.lease_token != claim.lease_token:
        return
    transient = isinstance(error, (ProviderUnavailableError, ProviderRateLimitedError))
    now = utc_now()
    execution.lease_token = None
    execution.lease_owner = None
    execution.lease_expires_at = None
    execution.error_summary = str(error)[:512]
    if transient and execution.attempt_count < max_attempts:
        execution.status = "queued"
        execution.next_attempt_at = now + timedelta(seconds=retry_base_seconds * (2 ** (execution.attempt_count - 1)))
    else:
        execution.status = "failed"
        execution.completed_at = now
        execution.next_attempt_at = None
    session.commit()


class InvestigationProcessor:
    def __init__(self, session_factory, connector: AbuseIPDBConnector, worker_id: str, lease_seconds: int, max_attempts: int, retry_base_seconds: int) -> None:
        self._session_factory = session_factory
        self._connector = connector
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds

    async def process_once(self) -> bool:
        with self._session_factory() as session:
            claim = claim_next_investigation(session, self._worker_id, self._lease_seconds, self._max_attempts)
        if claim is None:
            return False
        try:
            result = await self._connector.check_ip(claim.source_ip)
        except (InvalidIPAddressError, ConnectorConfigurationError, ProviderAuthenticationError, ProviderResponseError, ProviderUnavailableError, ProviderRateLimitedError) as exc:
            with self._session_factory() as session:
                fail_or_schedule_retry(session, claim, exc, self._max_attempts, self._retry_base_seconds)
            return True
        except Exception:
            with self._session_factory() as session:
                fail_or_schedule_retry(
                    session,
                    claim,
                    ProviderResponseError("investigation provider processing failed"),
                    self._max_attempts,
                    self._retry_base_seconds,
                )
            return True
        with self._session_factory() as session:
            complete_investigation(session, claim, result.model_dump(mode="json"))
        return True
