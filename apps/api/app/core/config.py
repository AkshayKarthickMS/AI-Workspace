from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AEGIS_", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    app_name: str = "AegisOS API"
    app_version: str = "0.1.0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
