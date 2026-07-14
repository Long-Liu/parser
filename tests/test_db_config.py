import pytest

from contexts.shared.infrastructure.config import load_config


def test_prod_config_rejects_empty_db_password():
    with pytest.raises(ValueError, match="db.password"):
        load_config("prod")


def test_local_config_loads_with_defaults():
    cfg = load_config("local")

    assert cfg.app.env == "local"
    assert cfg.db.host == "127.0.0.1"
    assert cfg.db.port == 3306
    assert isinstance(cfg.debug, bool)
