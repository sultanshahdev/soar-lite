from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResponseProposalIn(BaseModel):
    investigation_id: UUID
    target_ip: str = Field(min_length=1, max_length=45)


class ResponseDecisionIn(BaseModel):
    # Reasons are optional for this MVP, but retained whenever supplied.
    reason: str | None = Field(default=None, max_length=512)


class ResponseAuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    actor: str
    from_status: str | None
    to_status: str | None
    metadata_json: dict[str, object]
    created_at: datetime


class ResponseActionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    investigation_id: UUID | None
    action_type: Literal["block_ip"]
    target_ip: str
    status: Literal["proposed", "approved", "executing", "executed", "rejected", "failed", "reverted"]
    proposed_by: str
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime
    executed_at: datetime | None
    execution_result: dict[str, object] | None
    execution_error: str | None


class LabBlockEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_action_id: UUID
    incident_id: UUID
    ip_address: str
    active: bool
    created_at: datetime
    deactivated_at: datetime | None
    execution_metadata: dict[str, object]


class LabBlocklistPage(BaseModel):
    simulation: Literal[True] = True
    items: list[LabBlockEntryOut]
    page: int
    page_size: int
    total: int


class ResponseActionDetail(ResponseActionSummary):
    audit_events: list[ResponseAuditEventOut]


class ResponseActionPage(BaseModel):
    items: list[ResponseActionSummary]
    page: int
    page_size: int
    total: int
