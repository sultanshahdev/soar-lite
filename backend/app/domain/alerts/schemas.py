"""Validation and response contracts for generic security alerts."""

from datetime import datetime, timezone
from enum import StrEnum
import ipaddress
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GenericAlertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    event_type: str = Field(min_length=1, max_length=64)
    severity: Severity
    observed_at: datetime
    source_ip: str | None = Field(default=None, max_length=45)
    destination_host: str | None = Field(default=None, max_length=255)
    rule: str = Field(min_length=1, max_length=512)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("event_id", "event_type", "rule", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if not EVENT_TYPE_PATTERN.fullmatch(value):
            raise ValueError("must use lowercase letters, digits, dots, underscores, or hyphens")
        return value

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("must include a timezone offset")
        return value.astimezone(timezone.utc)

    @field_validator("source_ip")
    @classmethod
    def validate_source_ip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(ipaddress.ip_address(value))
        except ValueError as exc:
            raise ValueError("must be a valid IPv4 or IPv6 address") from exc


class IngestResponse(BaseModel):
    alert_id: UUID
    incident_id: UUID
    accepted: bool = True
    duplicate: bool


class AlertSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    source_event_id: str
    event_type: str
    severity: Severity
    source_ip: str | None
    destination_host: str | None
    rule_name: str
    observed_at: datetime
    received_at: datetime
    incident_id: UUID


class AlertDetail(AlertSummary):
    raw_payload: dict[str, object]


class IncidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    severity: Severity
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class IncidentDetail(IncidentSummary):
    alert_ids: list[UUID] = Field(default_factory=list)


class Page(BaseModel):
    items: list[AlertSummary | IncidentSummary]
    page: int
    page_size: int
    total: int
