"""Small, fail-closed credential dependencies for the MVP."""

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
analyst_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
PLACEHOLDER_PREFIX = "replace-with-"


def _configured_secret(value: str) -> bool:
    return bool(value and not value.lower().startswith(PLACEHOLDER_PREFIX))


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing credentials")


def require_webhook_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    if not _configured_secret(settings.webhook_secret) or not hmac.compare_digest(credentials.credentials, settings.webhook_secret):
        raise _unauthorized()


def require_analyst_auth(
    api_key: Annotated[str | None, Security(analyst_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if api_key is None or not _configured_secret(settings.analyst_api_key) or not hmac.compare_digest(api_key, settings.analyst_api_key):
        raise _unauthorized()
