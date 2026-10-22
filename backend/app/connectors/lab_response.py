"""PostgreSQL-only simulated containment adapter.

This adapter never invokes a shell, firewall, network API, or Docker control plane.
"""

from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.persistence.models import LabBlockEntry, utc_now


class LabResponseAdapter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def block_ip(self, ip_address: str, response_action_id: UUID, incident_id: UUID) -> dict[str, object]:
        """Create or reactivate this action's simulated block, idempotently."""
        entry = self._session.scalar(select(LabBlockEntry).where(LabBlockEntry.response_action_id == response_action_id).with_for_update())
        if entry is None:
            entry = LabBlockEntry(response_action_id=response_action_id, incident_id=incident_id, ip_address=ip_address, active=True, execution_metadata={"simulation": "postgresql_lab_blocklist"})
            self._session.add(entry)
            self._session.flush()
            return {"simulated": True, "block_entry_id": str(entry.id), "created": True}
        if not entry.active:
            entry.active = True
            entry.deactivated_at = None
        return {"simulated": True, "block_entry_id": str(entry.id), "created": False}

    def unblock_ip(self, response_action_id: UUID) -> bool:
        """Deactivate only the entry owned by the given action."""
        entry = self._session.scalar(select(LabBlockEntry).where(LabBlockEntry.response_action_id == response_action_id).with_for_update())
        if entry is None or not entry.active:
            return False
        entry.active = False
        entry.deactivated_at = utc_now()
        return True

    def is_blocked(self, ip_address: str) -> bool:
        return bool(self._session.scalar(select(exists().where(LabBlockEntry.ip_address == ip_address, LabBlockEntry.active.is_(True)))))
