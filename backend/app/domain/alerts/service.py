"""Transactional generic-alert ingestion."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.alerts.schemas import GenericAlertIn
from app.persistence.models import Alert, Incident
from app.persistence.repositories.alerts import alert_by_source_event

GENERIC_SOURCE = "generic"


def _incident_title(alert: GenericAlertIn) -> str:
    readable_type = alert.event_type.replace("_", " ").replace("-", " ").title()
    return f"{readable_type} — {alert.destination_host or 'unknown destination'}"


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
        session.commit()
        session.refresh(alert)
        return alert, False
    except IntegrityError:
        session.rollback()
        existing = alert_by_source_event(session, GENERIC_SOURCE, payload.event_id)
        if existing is not None:
            return existing, True
        raise
