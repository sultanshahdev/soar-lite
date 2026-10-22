from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://soar:soar_local_dev_password@postgres:5432/soar_lite"
    webhook_secret: str = "replace-with-a-long-random-secret"
    analyst_api_key: str = "replace-with-a-long-random-analyst-key"
    abuseipdb_api_key: str = ""
    abuseipdb_timeout_seconds: float = 5.0
    investigation_poll_seconds: float = 1.0
    investigation_lease_seconds: int = 60
    investigation_max_attempts: int = 3
    investigation_retry_base_seconds: int = 30
    max_alert_payload_bytes: int = 65_536


@lru_cache
def get_settings() -> Settings:
    return Settings()
