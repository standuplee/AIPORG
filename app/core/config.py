"""Runtime settings for the isolated AIPORG 2.0 application."""

from functools import lru_cache
import os

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Small, explicit runtime contract for Phase 0 and local development."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    database_url: str = Field(default="sqlite:///aiporg2.db", min_length=1)
    environment: str = Field(default="development", min_length=1)
    log_level: str = Field(default="INFO", min_length=1)
    naver_client_id: str | None = None
    naver_client_secret: str | None = None
    kakao_rest_api_key: str | None = None
    youtube_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Read only the AIPORG2_ namespace, leaving the 1.0 environment untouched."""

        return cls(
            database_url=os.getenv("AIPORG2_DATABASE_URL", cls.model_fields["database_url"].default),
            environment=os.getenv("AIPORG2_ENVIRONMENT", cls.model_fields["environment"].default),
            log_level=os.getenv("AIPORG2_LOG_LEVEL", cls.model_fields["log_level"].default).upper(),
            naver_client_id=os.getenv("AIPORG2_NAVER_CLIENT_ID"),
            naver_client_secret=os.getenv("AIPORG2_NAVER_CLIENT_SECRET"),
            kakao_rest_api_key=os.getenv("AIPORG2_KAKAO_REST_API_KEY"),
            youtube_api_key=os.getenv("AIPORG2_YOUTUBE_API_KEY"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable settings snapshot."""

    return Settings.from_env()
