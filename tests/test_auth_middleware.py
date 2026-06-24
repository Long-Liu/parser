import pytest
import time
from parser.middleware.auth import (
    generate_token, verify_token, hash_password, check_password
)


def test_token_roundtrip():
    token = generate_token(user_id=1, username="admin", secret="test_secret")
    payload = verify_token(token, secret="test_secret")
    assert payload["user_id"] == 1
    assert payload["username"] == "admin"


def test_token_expiry():
    token = generate_token(user_id=1, username="admin", secret="test_secret", expiry_seconds=-1)
    try:
        verify_token(token, secret="test_secret")
        assert False, "Should have raised"
    except Exception:
        pass


def test_hash_and_check_password():
    hashed = hash_password("mypassword")
    assert check_password("mypassword", hashed) is True
    assert check_password("wrong", hashed) is False
