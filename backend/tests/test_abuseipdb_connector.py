import httpx
import pytest

from app.connectors.abuseipdb import (
    AbuseIPDBConnector,
    ConnectorConfigurationError,
    InvalidIPAddressError,
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderResponseError,
    ProviderUnavailableError,
)


def connector_with(handler) -> AbuseIPDBConnector:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AbuseIPDBConnector(api_key="unit-test-key", client=client)


@pytest.mark.asyncio
async def test_normalizes_successful_check_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ipAddress"] == "8.8.8.8"
        assert request.headers["Key"] == "unit-test-key"
        return httpx.Response(200, json={"data": {"abuseConfidenceScore": 83, "countryCode": "US", "totalReports": 14}})

    result = await connector_with(handler).check_ip("8.8.8.8")
    assert result.ip_address == "8.8.8.8"
    assert result.abuse_confidence_score == 83
    assert result.country_code == "US"
    assert result.total_reports == 14
    assert result.provider == "abuseipdb"
    assert result.looked_up_at.tzinfo is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("ip", ["not-an-ip", "127.0.0.1", "10.0.0.1", "192.0.2.1"])
async def test_rejects_invalid_or_non_global_ips(ip: str) -> None:
    with pytest.raises(InvalidIPAddressError):
        await AbuseIPDBConnector(api_key="unit-test-key").check_ip(ip)


@pytest.mark.asyncio
async def test_rejects_missing_api_key() -> None:
    with pytest.raises(ConnectorConfigurationError):
        await AbuseIPDBConnector(api_key="").check_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_handles_timeout_rate_limit_and_invalid_credentials() -> None:
    def timeout_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(ProviderUnavailableError):
        await connector_with(timeout_handler).check_ip("8.8.8.8")

    with pytest.raises(ProviderRateLimitedError):
        await connector_with(lambda _: httpx.Response(429)).check_ip("8.8.8.8")
    with pytest.raises(ProviderAuthenticationError):
        await connector_with(lambda _: httpx.Response(401)).check_ip("8.8.8.8")


@pytest.mark.asyncio
async def test_rejects_server_and_invalid_provider_responses() -> None:
    with pytest.raises(ProviderUnavailableError):
        await connector_with(lambda _: httpx.Response(503)).check_ip("8.8.8.8")
    with pytest.raises(ProviderResponseError):
        await connector_with(lambda _: httpx.Response(200, json={"data": {"countryCode": "US"}})).check_ip("8.8.8.8")
