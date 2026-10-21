from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.domain.investigations.schemas import InvestigationDetail, InvestigationEvidenceOut, InvestigationPage, InvestigationSummary
from app.persistence.database import get_db
from app.persistence.repositories.investigations import investigation_by_id, paged_investigations
from app.security.auth import require_analyst_auth

router = APIRouter(tags=["investigations"])


@router.get("/investigations", response_model=InvestigationPage)
def list_investigations(
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
    investigation_status: Literal["queued", "running", "completed", "failed"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> InvestigationPage:
    investigations, total = paged_investigations(session, investigation_status, page, page_size)
    return InvestigationPage(items=[InvestigationSummary.model_validate(item) for item in investigations], page=page, page_size=page_size, total=total)


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
def get_investigation(
    investigation_id: UUID,
    _: Annotated[None, Depends(require_analyst_auth)],
    session: Annotated[Session, Depends(get_db)],
) -> InvestigationDetail:
    investigation = investigation_by_id(session, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="investigation not found")
    return InvestigationDetail(
        **InvestigationSummary.model_validate(investigation).model_dump(),
        evidence=[InvestigationEvidenceOut.model_validate(item) for item in investigation.evidence],
    )
