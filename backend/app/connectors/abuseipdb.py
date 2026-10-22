"""AbuseIPDB v2 check adapter; retry policy belongs to the future worker."""

from datetime import datetime, timezone
import ipaddress

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings


class AbuseIPDBResult(BaseModel):
    """Stable, provider-neutral subset of an AbuseIPDB check result."""

    ip_address: str
    abuse_confidence_score: int = Field(ge=0, le=100)
    country_code: str | None = None
    total_reports: int | None = Field(default=None, ge=0)
    provider: str = "abuseipdb"
    looked_up_at: datetime


class AbuseIPDBError(Exception):
    """Safe connector error intended for logs and future persisted summaries."""


class InvalidIPAddressError(AbuseIPDBError):
    pass


class ConnectorConfigurationError(AbuseIPDBError):
    pass


class ProviderAuthenticationError(AbuseIPDBError):
    pass


class ProviderRateLimitedError(AbuseIPDBError):
    pass


class ProviderUnavailableError(AbuseIPDBError):
    pass


class ProviderResponseError(AbuseIPDBError):
    pass


class AbuseIPDBConnector:
    endpoint = "https://api.abuseipdb.com/api/v2/check"

    def __init__(self, api_key: str | None = None, timeout_seconds: float | None = None, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.abuseipdb_api_key
        self._client = client
        self._timeout = timeout_seconds if timeout_seconds is not None else settings.abuseipdb_timeout_seconds

    async def check_ip(self, source_ip: str) -> AbuseIPDBResult:
        ip_address = self._validate_global_ip(source_ip)
        if not self._api_key or self._api_key.lower().startswith("replace-with-"):
            raise ConnectorConfigurationError("AbuseIPDB is not configured")

        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(self._timeout))
        close_client = self._client is None
        try:
            response = await client.get(
                self.endpoint,
                params={"ipAddress": str(ip_address), "maxAgeInDays": "90"},
                headers={"Accept": "application/json", "Key": self._api_key},
            )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError("AbuseIPDB request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("AbuseIPDB request failed") from exc
        finally:
            if close_client:
                await client.aclose()

        if response.status_code in (401, 403):
            raise ProviderAuthenticationError("AbuseIPDB rejected the configured credentials")
        if response.status_code == 429:
            raise ProviderRateLimitedError("AbuseIPDB rate limit exceeded")
        if response.status_code >= 500:
            raise ProviderUnavailableError("AbuseIPDB service is unavailable")
        if response.status_code >= 400:
            raise ProviderResponseError("AbuseIPDB rejected the lookup request")

        try:
            payload = response.json()
            data = payload["data"]
            if not isinstance(data, dict):
                raise TypeError("data is not an object")
            return AbuseIPDBResult(
                ip_address=str(ip_address),
                abuse_confidence_score=data["abuseConfidenceScore"],
                country_code=data.get("countryCode"),
                total_reports=data.get("totalReports"),
                looked_up_at=datetime.now(timezone.utc),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ProviderResponseError("AbuseIPDB returned an invalid response") from exc

    @staticmethod
    def _validate_global_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError as exc:
            raise InvalidIPAddressError("source IP address is invalid") from exc
        if not parsed.is_global:
            raise InvalidIPAddressError("source IP address must be globally routable")
        return parsed
