from app.domain.alerts.schemas import GenericAlertIn
from app.domain.alerts.service import should_queue_suspicious_ip_investigation


def payload(**overrides: object) -> GenericAlertIn:
    values: dict[str, object] = {
        "event_id": "investigation-policy",
        "event_type": "suspicious_login",
        "severity": "high",
        "observed_at": "2026-10-22T00:00:00Z",
        "source_ip": "8.8.8.8",
        "rule": "Repeated failed login attempts",
    }
    values.update(overrides)
    return GenericAlertIn.model_validate(values)


def test_only_global_suspicious_login_alerts_queue_investigations() -> None:
    assert should_queue_suspicious_ip_investigation(payload()) is True
    assert should_queue_suspicious_ip_investigation(payload(event_type="other_event")) is False
    assert should_queue_suspicious_ip_investigation(payload(source_ip="10.0.0.1")) is False
