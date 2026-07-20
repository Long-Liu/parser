import pytest

from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.shared.domain.exceptions import AuthenticationError
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
    with pytest.raises(AuthenticationError):
        svc.verify(token)


def test_hash_and_check_password():
    hasher = BCryptPasswordHasher()
    hashed = hasher.hash("mypassword")
    assert hasher.verify("mypassword", hashed) is True
    assert hasher.verify("wrong", hashed) is False
