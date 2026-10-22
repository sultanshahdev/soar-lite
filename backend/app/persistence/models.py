"""Persistent alert and incident records."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_incidents_severity"),
        CheckConstraint("status IN ('new', 'open', 'closed')", name="ck_incidents_status"),
        Index("ix_incidents_severity_created_at", "severity", "created_at"),
        Index("ix_incidents_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="incident")
    investigations: Mapped[list["InvestigationExecution"]] = relationship(back_populates="incident")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_alerts_source_event_id"),
        Index("ix_alerts_severity_received_at", "severity", "received_at"),
        Index("ix_alerts_incident_id", "incident_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_name: Mapped[str] = mapped_column(String(512), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="alerts")


class InvestigationExecution(Base):
    __tablename__ = "investigation_executions"
    __table_args__ = (
        UniqueConstraint("incident_id", "investigation_type", "source_ip", name="uq_investigations_incident_type_ip"),
        CheckConstraint("investigation_type IN ('suspicious_ip')", name="ck_investigations_type"),
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="ck_investigations_status"),
        CheckConstraint("attempt_count >= 0", name="ck_investigations_attempt_count"),
        Index("ix_investigations_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_investigations_incident_created_at", "incident_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False)
    investigation_type: Mapped[str] = mapped_column(String(64), nullable=False, default="suspicious_ip")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="investigations")
    evidence: Mapped[list["InvestigationEvidence"]] = relationship(back_populates="investigation")


class InvestigationEvidence(Base):
    __tablename__ = "investigation_evidence"
    __table_args__ = (Index("ix_investigation_evidence_investigation_created", "investigation_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_id: Mapped[UUID] = mapped_column(ForeignKey("investigation_executions.id", ondelete="CASCADE"), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    investigation: Mapped[InvestigationExecution] = relationship(back_populates="evidence")
