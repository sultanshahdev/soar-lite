from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import InvestigationExecution


def investigation_by_id(session: Session, investigation_id: UUID) -> InvestigationExecution | None:
    statement = select(InvestigationExecution).options(selectinload(InvestigationExecution.evidence)).where(InvestigationExecution.id == investigation_id)
    return session.scalar(statement)


def paged_investigations(session: Session, investigation_status: str | None, page: int, page_size: int) -> tuple[list[InvestigationExecution], int]:
    statement = select(InvestigationExecution).order_by(InvestigationExecution.created_at.desc(), InvestigationExecution.id.desc())
    count = select(func.count()).select_from(InvestigationExecution)
    if investigation_status:
        statement = statement.where(InvestigationExecution.status == investigation_status)
        count = count.where(InvestigationExecution.status == investigation_status)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size))), int(session.scalar(count) or 0)
