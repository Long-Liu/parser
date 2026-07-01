import pytest

from contexts.shared.infrastructure.database.config import load_config


def test_prod_config_requires_strong_jwt_secret(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "not-empty")
    monkeypatch.setenv("JWT_SECRET", "short")

    with pytest.raises(ValueError, match="JWT_SECRET"):
        load_config("prod")


def test_prod_config_accepts_env_secrets(monkeypatch):
    monkeypatch.setenv("DB_PASSWORD", "not-empty")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)

    cfg = load_config("prod")

    assert cfg.DB_PASSWORD == "not-empty"
    assert cfg.SECRET_KEY == "x" * 32
