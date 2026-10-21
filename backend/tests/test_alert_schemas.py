from datetime import timezone

import pytest
from pydantic import ValidationError

from app.domain.alerts.schemas import GenericAlertIn


def valid_payload() -> dict[str, object]:
    return {
        "event_id": "event-1",
        "event_type": "suspicious_login",
        "severity": "high",
        "observed_at": "2026-10-21T16:00:00+02:00",
        "source_ip": "2001:0db8::1",
        "rule": "Repeated failed login attempts",
    }


def test_normalizes_timestamp_and_ip() -> None:
    alert = GenericAlertIn.model_validate(valid_payload())
    assert alert.observed_at.tzinfo == timezone.utc
    assert alert.source_ip == "2001:db8::1"


@pytest.mark.parametrize("field,value", [("severity", "urgent"), ("source_ip", "not-an-ip"), ("observed_at", "2026-10-21T16:00:00")])
def test_rejects_invalid_alert_values(field: str, value: object) -> None:
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        GenericAlertIn.model_validate(payload)


def test_requires_fields() -> None:
    with pytest.raises(ValidationError):
        GenericAlertIn.model_validate({"event_id": "only-id"})
