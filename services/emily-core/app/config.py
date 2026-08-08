from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    emily_name: str = Field(default="Emily", validation_alias="EMILY_NAME")
    emily_log_level: str = Field(default="INFO", validation_alias="EMILY_LOG_LEVEL")
    home_assistant_url: str = Field(
        default="http://host.docker.internal:8123",
        validation_alias="HOME_ASSISTANT_URL",
    )
    home_assistant_token: str = Field(default="", validation_alias="HOME_ASSISTANT_TOKEN")
    home_assistant_mock: bool = Field(
        default=False, validation_alias="HOME_ASSISTANT_MOCK"
    )
    entity_cache_seconds: int = Field(
        default=30, ge=0, le=3_600, validation_alias="ENTITY_CACHE_SECONDS"
    )
    home_assistant_control_enabled: bool = Field(
        default=True, validation_alias="HOME_ASSISTANT_CONTROL_ENABLED"
    )
    cors_origins: str = Field(default="", validation_alias="EMILY_CORS_ORIGINS")
    max_request_bytes: int = Field(
        default=16_384,
        ge=1_024,
        le=1_048_576,
        validation_alias="EMILY_MAX_REQUEST_BYTES",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
