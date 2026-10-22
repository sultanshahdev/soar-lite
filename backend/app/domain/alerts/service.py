"""Transactional generic-alert ingestion and supported investigation queueing."""

import ipaddress

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.alerts.schemas import GenericAlertIn
from app.persistence.models import Alert, Incident, InvestigationExecution
from app.persistence.repositories.alerts import alert_by_source_event

GENERIC_SOURCE = "generic"
SUSPICIOUS_IP_EVENT_TYPES = {"suspicious_login"}


def _incident_title(alert: GenericAlertIn) -> str:
    readable_type = alert.event_type.replace("_", " ").replace("-", " ").title()
    return f"{readable_type} — {alert.destination_host or 'unknown destination'}"


def should_queue_suspicious_ip_investigation(payload: GenericAlertIn) -> bool:
    """Queue only supported alert types with globally routable source addresses."""
    if payload.event_type not in SUSPICIOUS_IP_EVENT_TYPES or payload.source_ip is None:
        return False
    return ipaddress.ip_address(payload.source_ip).is_global


def ingest_generic_alert(session: Session, payload: GenericAlertIn) -> tuple[Alert, bool]:
    """Atomically store a new alert and its incident, or return a duplicate."""
    existing = alert_by_source_event(session, GENERIC_SOURCE, payload.event_id)
    if existing is not None:
        return existing, True

    raw_payload = payload.model_dump(mode="json")
    try:
        incident = Incident(
            title=_incident_title(payload),
            description=payload.rule,
            severity=payload.severity.value,
            status="new",
        )
        alert = Alert(
            source=GENERIC_SOURCE,
            source_event_id=payload.event_id,
            event_type=payload.event_type,
            severity=payload.severity.value,
            source_ip=payload.source_ip,
            destination_host=payload.destination_host,
            rule_name=payload.rule,
            observed_at=payload.observed_at,
            raw_payload=raw_payload,
            incident=incident,
        )
        session.add(alert)
        if should_queue_suspicious_ip_investigation(payload):
            session.add(
                InvestigationExecution(
                    incident=incident,
                    investigation_type="suspicious_ip",
                    status="queued",
                    source_ip=payload.source_ip,
                )
            )
        session.commit()
        session.refresh(alert)
        return alert, False
    except IntegrityError:
        session.rollback()
        existing = alert_by_source_event(session, GENERIC_SOURCE, payload.event_id)
        if existing is not None:
            return existing, True
        raise
