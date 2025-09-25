"""Application configuration management."""
from functools import lru_cache

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = Field(default="Agent Demo API", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    openai_api_key: str | None = Field(default="sk-UQh1uW7s55CD4571E52DT3BlbKFJ5752b685578B44bDAc6a", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-mini", alias="OPENAI_MODEL")
    openai_base_url: str | HttpUrl | None = Field(
        default="https://c-z0-api-01.hash070.com/v1", alias="OPENAI_BASE_URL"
    )
    reservation_hold_minutes: int = Field(default=10, alias="RESERVATION_HOLD_MINUTES")
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return parts or ["*"]
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()
