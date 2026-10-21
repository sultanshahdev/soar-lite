from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.domain.alerts.schemas import AlertDetail, AlertSummary, GenericAlertIn, IngestResponse, Page, Severity
from app.domain.alerts.service import ingest_generic_alert
from app.persistence.database import get_db
from app.persistence.repositories.alerts import alert_by_id, paged_alerts
from app.security.auth import require_analyst_auth, require_webhook_auth

router = APIRouter(tags=["alerts"])


def require_json_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/json":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="content type must be application/json")


def enforce_payload_limit(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > settings.max_alert_payload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="alert payload exceeds the permitted size")


@router.post("/ingest/generic", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest(
    payload: GenericAlertIn,
    response: Response,
    _: Annotated[None, Depends(require_webhook_auth)],
    __: Annotated[None, Depends(require_json_content_type)],
    ___: Annotated[None, Depends(enforce_payload_limit)],
    session: Annotated[Session, Depends(get_db)],
) -> IngestResponse:
    alert, duplicate = ingest_generic_alert(session, payload)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return IngestResponse(alert_id=alert.id, incident_id=alert.incident_id, duplicate=duplicate)


@router.get("/alerts", response_model=Page)
def list_alerts(
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
    severity: Severity | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page:
    alerts, total = paged_alerts(session, severity.value if severity else None, page, page_size)
    return Page(items=[AlertSummary.model_validate(item) for item in alerts], page=page, page_size=page_size, total=total)


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
def get_alert(
    alert_id: UUID,
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
) -> AlertDetail:
    alert = alert_by_id(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return AlertDetail.model_validate(alert)
