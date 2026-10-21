from app.api.health import health_check


def test_health_check() -> None:
    assert health_check() == {"status": "ok", "service": "soar-lite"}
