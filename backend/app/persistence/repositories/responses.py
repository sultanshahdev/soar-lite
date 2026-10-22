from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import ResponseAction


def response_action_by_id(session: Session, action_id: UUID, with_audit: bool = False) -> ResponseAction | None:
    statement = select(ResponseAction).where(ResponseAction.id == action_id)
    if with_audit:
        statement = statement.options(selectinload(ResponseAction.audit_events))
    return session.scalar(statement)


def paged_response_actions(session: Session, action_status: str | None, page: int, page_size: int) -> tuple[list[ResponseAction], int]:
    statement = select(ResponseAction).order_by(ResponseAction.created_at.desc(), ResponseAction.id.desc())
    count = select(func.count()).select_from(ResponseAction)
    if action_status:
        statement = statement.where(ResponseAction.status == action_status)
        count = count.where(ResponseAction.status == action_status)
    return list(session.scalars(statement.offset((page - 1) * page_size).limit(page_size))), int(session.scalar(count) or 0)
