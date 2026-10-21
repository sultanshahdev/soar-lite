from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import Alert, Incident


def alert_by_source_event(session: Session, source: str, event_id: str) -> Alert | None:
    return session.scalar(select(Alert).where(Alert.source == source, Alert.source_event_id == event_id))


def alert_by_id(session: Session, alert_id: UUID) -> Alert | None:
    return session.scalar(select(Alert).where(Alert.id == alert_id))


def incident_by_id(session: Session, incident_id: UUID) -> Incident | None:
    statement = select(Incident).options(selectinload(Incident.alerts)).where(Incident.id == incident_id)
    return session.scalar(statement)


def paged_alerts(session: Session, severity: str | None, page: int, page_size: int) -> tuple[list[Alert], int]:
    statement: Select[tuple[Alert]] = select(Alert).order_by(Alert.received_at.desc(), Alert.id.desc())
    count = select(func.count()).select_from(Alert)
    if severity:
        statement = statement.where(Alert.severity == severity)
        count = count.where(Alert.severity == severity)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size))), int(session.scalar(count) or 0)


def paged_incidents(session: Session, severity: str | None, incident_status: str | None, page: int, page_size: int) -> tuple[list[Incident], int]:
    statement: Select[tuple[Incident]] = select(Incident).order_by(Incident.created_at.desc(), Incident.id.desc())
    count = select(func.count()).select_from(Incident)
    if severity:
        statement = statement.where(Incident.severity == severity)
        count = count.where(Incident.severity == severity)
    if incident_status:
        statement = statement.where(Incident.status == incident_status)
        count = count.where(Incident.status == incident_status)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size))), int(session.scalar(count) or 0)
