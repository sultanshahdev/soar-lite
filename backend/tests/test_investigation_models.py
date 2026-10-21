from sqlalchemy import inspect

from app.persistence.models import InvestigationEvidence, InvestigationExecution


def test_investigation_model_has_retry_lease_and_evidence_fields() -> None:
    execution_columns = {column.name for column in inspect(InvestigationExecution).columns}
    assert {"incident_id", "investigation_type", "status", "attempt_count", "source_ip", "next_attempt_at", "lease_token", "lease_expires_at", "error_summary"} <= execution_columns
    evidence_columns = {column.name for column in inspect(InvestigationEvidence).columns}
    assert {"investigation_id", "evidence_source", "result", "created_at"} <= evidence_columns
    assert InvestigationExecution.evidence.property.mapper.class_ is InvestigationEvidence
