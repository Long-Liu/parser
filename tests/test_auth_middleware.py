import pytest

from contexts.auth.interface.auth_middleware import generate_token, verify_token, hash_password, check_password

TEST_SECRET = "test-secret-key-for-pytest-32-bytes"


def test_token_roundtrip():
    token = generate_token(user_id=1, username="admin", secret=TEST_SECRET)
    payload = verify_token(token, secret=TEST_SECRET)
    assert payload["user_id"] == 1
    assert payload["username"] == "admin"


def test_token_expiry():
    token = generate_token(user_id=1, username="admin", secret=TEST_SECRET, expiry_hours=-1)
    with pytest.raises(Exception):
        verify_token(token, secret=TEST_SECRET)


def test_hash_and_check_password():
    hashed = hash_password("mypassword")
    assert check_password("mypassword", hashed) is True
    assert check_password("wrong", hashed) is False
