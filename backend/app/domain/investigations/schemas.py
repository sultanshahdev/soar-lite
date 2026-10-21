from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvestigationEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_source: str
    result: dict[str, object]
    created_at: datetime


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    investigation_type: Literal["suspicious_ip"]
    status: Literal["queued", "running", "completed", "failed"]
    attempt_count: int
    source_ip: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    next_attempt_at: datetime | None


class InvestigationDetail(InvestigationSummary):
    evidence: list[InvestigationEvidenceOut]


class InvestigationPage(BaseModel):
    items: list[InvestigationSummary]
    page: int
    page_size: int
    total: int
