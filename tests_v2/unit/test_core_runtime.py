from __future__ import annotations

import logging

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def test_settings_use_only_aiporg2_environment(monkeypatch) -> None:
    monkeypatch.setenv("AIPORG2_DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("AIPORG2_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AIPORG2_NAVER_CLIENT_ID", "naver-id")
    monkeypatch.setenv("AIPORG2_NAVER_CLIENT_SECRET", "naver-secret")
    monkeypatch.setenv("AIPORG2_KAKAO_REST_API_KEY", "kakao-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///legacy.db")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite:///test.db"
    assert settings.log_level == "DEBUG"
    assert settings.naver_client_id == "naver-id"
    assert settings.naver_client_secret == "naver-secret"
    assert settings.kakao_rest_api_key == "kakao-key"
    assert settings.environment == "development"


def test_settings_are_cached_and_explicit_override_is_supported(monkeypatch) -> None:
    monkeypatch.delenv("AIPORG2_DATABASE_URL", raising=False)
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.database_url == "sqlite:///aiporg2.db"


def test_configure_logging_is_idempotent() -> None:
    logger_name = "aiporg2.test"
    configure_logging(level="INFO")
    configure_logging(level="DEBUG")

    logger = logging.getLogger(logger_name)
    assert logger.getEffectiveLevel() == logging.DEBUG
    aiporg_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_aiporg2_handler", False)
    ]
    assert len(aiporg_handlers) == 1
