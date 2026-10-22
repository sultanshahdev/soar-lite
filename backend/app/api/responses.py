"""Persist analyst proposals and decisions; execution belongs to the later worker task."""

import ipaddress
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.responses.schemas import ResponseActionDetail, ResponseActionPage, ResponseActionSummary, ResponseDecisionIn, ResponseProposalIn
from app.persistence.database import get_db
from app.persistence.models import InvestigationExecution, ResponseAction, ResponseAuditEvent, utc_now
from app.persistence.repositories.alerts import incident_by_id
from app.persistence.repositories.responses import paged_response_actions, response_action_by_id
from app.security.auth import require_analyst_auth

router = APIRouter(tags=["response-actions"])

# The present authentication scheme is a shared analyst API key, not individual accounts.
ANALYST_ACTOR = "analyst_api_key"


def _global_ip(value: str) -> str:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="target_ip must be a valid IP address") from exc
    if not parsed.is_global:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="target_ip must be globally routable")
    return str(parsed)


@router.post("/incidents/{incident_id}/response-actions", response_model=ResponseActionSummary, status_code=status.HTTP_201_CREATED)
def propose_response_action(
    incident_id: UUID,
    payload: ResponseProposalIn,
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
) -> ResponseAction:
    target_ip = _global_ip(payload.target_ip)
    if incident_by_id(session, incident_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    investigation = session.get(InvestigationExecution, payload.investigation_id)
    if investigation is None or investigation.incident_id != incident_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="investigation is not associated with this incident")
    if investigation.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="investigation must be completed before proposing a response")
    if _global_ip(investigation.source_ip) != target_ip:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="target_ip is not supported by the investigation")

    action = ResponseAction(
        incident_id=incident_id,
        investigation_id=investigation.id,
        action_type="block_ip",
        target_ip=target_ip,
        status="proposed",
        proposed_by=ANALYST_ACTOR,
    )
    try:
        session.add(action)
        session.flush()
        session.add(ResponseAuditEvent(response_action_id=action.id, event_type="response_proposed", actor=ANALYST_ACTOR, from_status=None, to_status="proposed", metadata_json={"target_ip": target_ip, "action_type": "block_ip"}))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="an active proposal already exists for this incident and target") from exc
    session.refresh(action)
    return action


def _decide(action_id: UUID, payload: ResponseDecisionIn, session: Session, to_status: Literal["approved", "rejected"]) -> ResponseAction:
    now = utc_now()
    action = session.execute(
        update(ResponseAction)
        .where(ResponseAction.id == action_id, ResponseAction.status == "proposed")
        .values(status=to_status, decided_by=ANALYST_ACTOR, decided_at=now, decision_reason=payload.reason, updated_at=now)
        .returning(ResponseAction)
    ).scalar_one_or_none()
    if action is None:
        if response_action_by_id(session, action_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response action not found")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="response action is no longer proposed")
    session.add(ResponseAuditEvent(
        response_action_id=action.id,
        event_type=f"response_{to_status}",
        actor=ANALYST_ACTOR,
        from_status="proposed",
        to_status=to_status,
        metadata_json={"reason_provided": payload.reason is not None},
    ))
    session.commit()
    session.refresh(action)
    return action


@router.post("/response-actions/{action_id}/approve", response_model=ResponseActionSummary)
def approve_response_action(action_id: UUID, payload: ResponseDecisionIn, _: Annotated[None, Depends(require_analyst_auth)], session: Annotated[Session, Depends(get_db)]) -> ResponseAction:
    return _decide(action_id, payload, session, "approved")


@router.post("/response-actions/{action_id}/reject", response_model=ResponseActionSummary)
def reject_response_action(action_id: UUID, payload: ResponseDecisionIn, _: Annotated[None, Depends(require_analyst_auth)], session: Annotated[Session, Depends(get_db)]) -> ResponseAction:
    return _decide(action_id, payload, session, "rejected")


@router.get("/response-actions", response_model=ResponseActionPage)
def list_response_actions(
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
    action_status: Literal["proposed", "approved", "executing", "executed", "rejected", "failed", "reverted"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ResponseActionPage:
    actions, total = paged_response_actions(session, action_status, page, page_size)
    return ResponseActionPage(items=[ResponseActionSummary.model_validate(action) for action in actions], page=page, page_size=page_size, total=total)


@router.get("/response-actions/{action_id}", response_model=ResponseActionDetail)
def get_response_action(action_id: UUID, _: Annotated[None, Depends(require_analyst_auth)], session: Annotated[Session, Depends(get_db)]) -> ResponseActionDetail:
    action = response_action_by_id(session, action_id, with_audit=True)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response action not found")
    return ResponseActionDetail(**ResponseActionSummary.model_validate(action).model_dump(), audit_events=sorted(action.audit_events, key=lambda event: (event.created_at, event.id)))
