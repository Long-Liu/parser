import pytest

from contexts.auth.domain.auth_service import hash_password, verify_password
from contexts.auth.domain.jwt_service import JwtService
from contexts.shared.domain.identifiers import UserId

TEST_SECRET = "test-secret-key-for-pytest-32-bytes"


def test_token_roundtrip():
    svc = JwtService(TEST_SECRET)
    token = svc.generate(user_id=UserId(1), username="admin")
    payload = svc.verify(token)
    assert payload["user_id"] == 1
    assert payload["username"] == "admin"


def test_token_expiry():
    svc = JwtService(TEST_SECRET, expiry_hours=-1)
    token = svc.generate(user_id=UserId(1), username="admin")
    with pytest.raises(Exception):
        svc.verify(token)


def test_hash_and_check_password():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrong", hashed) is False
