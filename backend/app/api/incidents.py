from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.domain.alerts.schemas import IncidentDetail, IncidentSummary, Page, Severity
from app.persistence.database import get_db
from app.persistence.repositories.alerts import incident_by_id, paged_incidents
from app.security.auth import require_analyst_auth

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=Page)
def list_incidents(
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
    severity: Severity | None = None,
    incident_status: Literal["new", "open", "closed"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page:
    incidents, total = paged_incidents(session, severity.value if severity else None, incident_status, page, page_size)
    return Page(items=[IncidentSummary.model_validate(item) for item in incidents], page=page, page_size=page_size, total=total)


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(
    incident_id: UUID,
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
) -> IncidentDetail:
    incident = incident_by_id(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    result = IncidentDetail.model_validate(incident)
    result.alert_ids = [alert.id for alert in incident.alerts]
    return result
