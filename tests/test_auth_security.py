"""Auth security hardening: change-password, logout + token blacklist,
and the open-registration switch. Unit-style with in-memory fakes (no DB)."""

from __future__ import annotations

import json as jsonlib
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sanic import Sanic
from sanic.response import json

from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.authorization_app_service import (
    AuthorizationApplicationService,
)
from contexts.auth.application.dto import LoginCommand
from contexts.auth.application.login_throttle import LoginThrottler
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.user import User
from contexts.auth.infrastructure.jwt_service import JwtService
from contexts.auth.infrastructure.password_hasher import BCryptPasswordHasher
from contexts.auth.interface.auth_controller import AuthController
from contexts.auth.interface.auth_middleware import require_auth
from contexts.auth.interface.request_services import RequestServices
from contexts.shared.domain.exceptions import (
    AuthenticationError,
    DomainError,
    ValidationError,
)
from tests.asgi_client import get as _asgi_get, post as _asgi_post
from contexts.shared.domain.identifiers import UserId
from contexts.shared.infrastructure.config import AuthConfig, Settings
from contexts.shared.interface.base_controller import error_to_response

TEST_SECRET = "test-secret-key-for-pytest-32-bytes"
OLD_PASSWORD = "oldpassword1"
NEW_PASSWORD = "newpassword2"

_hasher = BCryptPasswordHasher()
_old_hash: str | None = None


def _hash_old() -> str:
    # bcrypt(12) is slow; hash once per test session.
    global _old_hash
    if _old_hash is None:
        _old_hash = _hasher.hash(OLD_PASSWORD)
    assert _old_hash is not None
    return _old_hash


class FakeUserRepository:
    def __init__(self):
        self.users: dict[int, User] = {
            1: User(user_id=UserId(1), username="alice", password_hash=_hash_old()),
            2: User(user_id=UserId(2), username="admin", password_hash=_hash_old()),
        }
        self.permissions: dict[int, set[str]] = {1: set(), 2: {"user:manage"}}

    async def find_by_id(self, user_id):
        return self.users.get(user_id.value)

    async def find_by_username(self, username):
        return next((u for u in self.users.values() if u.username == username), None)

    async def save(self, user):
        # noinspection PyUnreachableCode
        if user.id is None:
            user.id = UserId(max(self.users, default=0) + 1)
        self.users[user.id.value] = user

    async def get_permissions(self, user_id):
        return self.permissions.get(user_id.value, set())


class FakeTokenRevocationRepository:
    """In-memory mirror of the documented blacklist semantics."""

    def __init__(self):
        self.entries: list[tuple[str, int, datetime, datetime]] = []

    async def revoke(self, *, jti, user_id, expires_at):
        self.entries.append((jti, user_id.value, expires_at, datetime.now(UTC)))

    async def revoke_all_for_user(self, *, user_id, expires_at):
        marker = f"user:{user_id.value}"
        self.entries = [e for e in self.entries if e[0] != marker]
        self.entries.append((marker, user_id.value, expires_at, datetime.now(UTC)))

    async def is_revoked(self, *, jti, user_id, issued_at):
        marker = f"user:{user_id.value}"
        now = datetime.now(UTC)
        for e_jti, _uid, e_expires, e_revoked in self.entries:
            if e_expires <= now:
                continue
            if jti and e_jti == jti:
                return True
            if e_jti == marker and issued_at is not None and e_revoked.timestamp() >= issued_at:
                return True
        return False


@pytest.fixture
def stack():
    repo = FakeUserRepository()
    jwt_svc = JwtService(TEST_SECRET)
    revocations = FakeTokenRevocationRepository()
    # noinspection PyTypeChecker
    auth_svc = AuthApplicationService(
        repo,
        AuthenticationService(_hasher),
        jwt_svc,
        _hasher,
        None,
        None,
        revocations,
    )
    # noinspection PyTypeChecker
    authz = AuthorizationApplicationService(repo, jwt_svc, revocations)
    return SimpleNamespace(
        repo=repo,
        jwt=jwt_svc,
        revocations=revocations,
        auth=auth_svc,
        authz=authz,
    )


def _request(*, settings=None, services=None, body=None, headers=None):
    return SimpleNamespace(
        json=body or {},
        headers=headers or {},
        args={},
        form={},
        app=SimpleNamespace(ctx=SimpleNamespace(settings=settings, services=services)),
        ctx=SimpleNamespace(),
    )


# ── JWT claims ────────────────────────────────────────────────────────


def test_jwt_carries_jti_and_iat(stack):
    token = stack.jwt.generate(UserId(1), "alice")
    payload = stack.jwt.verify(token)
    assert payload["jti"]
    assert isinstance(payload["iat"], int)


# ── change-password ───────────────────────────────────────────────────


async def _change_password_app(stack):
    """Real Sanic app wiring the decorated change-password route."""
    # noinspection PyTypeChecker
    controller = AuthController(stack.auth, user_svc=None)
    app = Sanic(f"auth_change_pw_{id(stack)}")
    app.asgi = True
    # noinspection PyTypeChecker
    app.ctx.services = RequestServices(authorization=stack.authz, project_access=None)
    app.add_route(controller.change_password, "/auth/change-password", methods=["POST"])
    app.finalize()
    app.signalize(allow_fail_builtin=False)
    return app


async def _login_app(stack, throttler: LoginThrottler | None = None):
    """Real Sanic app wiring the login route with brute-force protection."""
    # noinspection PyTypeChecker
    controller = AuthController(
        stack.auth,
        user_svc=None,
        login_throttler=throttler or LoginThrottler(max_failures=3),
    )
    app = Sanic(f"auth_login_{id(stack)}")
    app.asgi = True
    # noinspection PyTypeChecker
    app.ctx.services = RequestServices(authorization=stack.authz, project_access=None)

    @app.exception(DomainError)
    async def _on_domain_error(_request, exception: DomainError):
        return error_to_response(exception)

    app.add_route(controller.login, "/auth/login", methods=["POST"])
    app.finalize()
    app.signalize(allow_fail_builtin=False)
    return app


async def test_change_password_endpoint_allows_self_service(stack):
    """Any authenticated user may rotate their own password (not admin-only)."""
    app = await _change_password_app(stack)
    token = stack.jwt.generate(UserId(1), "alice")  # no user:manage
    code, _body = await _asgi_post(
        app,
        "/auth/change-password",
        {"old_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        token,
    )
    assert code == 200
    assert _hasher.verify(NEW_PASSWORD, stack.repo.users[1].password_hash)


async def test_change_password_endpoint_allows_user_manage_admin(stack):
    app = await _change_password_app(stack)
    token = stack.jwt.generate(UserId(2), "admin")  # has user:manage
    code, _body = await _asgi_post(
        app,
        "/auth/change-password",
        {"old_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        token,
    )
    assert code == 200
    assert _hasher.verify(NEW_PASSWORD, stack.repo.users[2].password_hash)


async def test_change_password_success_revokes_all_existing_tokens(stack):
    token_a = stack.jwt.generate(UserId(1), "alice")
    token_b = stack.jwt.generate(UserId(1), "alice")  # second session
    ctx = await stack.authz.authenticate(token_a)
    assert ctx.user_id == 1

    await stack.auth.change_password(
        user_id=1,
        old_password=OLD_PASSWORD,
        new_password=NEW_PASSWORD,
    )

    assert _hasher.verify(NEW_PASSWORD, stack.repo.users[1].password_hash)
    # Both pre-change tokens are dead, including one from another session.
    with pytest.raises(AuthenticationError, match="revoked"):
        await stack.authz.authenticate(token_a)
    with pytest.raises(AuthenticationError, match="revoked"):
        await stack.authz.authenticate(token_b)
    # JWT iat has second granularity and the blacklist cutoff is
    # "issued at/before the revocation instant", so a token minted in the
    # same second as the password change would still look stale. Wait out
    # that one-second window before re-login (a non-issue in real usage).
    time.sleep(1.1)
    # Re-login with the new password yields a working token.
    result = await stack.auth.login(LoginCommand(username="alice", password=NEW_PASSWORD))
    assert (await stack.authz.authenticate(result.token)).user_id == 1


async def test_change_password_wrong_old_password(stack):
    with pytest.raises(AuthenticationError, match="invalid credentials"):
        await stack.auth.change_password(
            user_id=1,
            old_password="wrong-old-pw",
            new_password=NEW_PASSWORD,
        )
    assert _hasher.verify(OLD_PASSWORD, stack.repo.users[1].password_hash)


async def test_change_password_short_new_password(stack):
    with pytest.raises(ValidationError, match="at least 8"):
        await stack.auth.change_password(
            user_id=1,
            old_password=OLD_PASSWORD,
            new_password="short",
        )
    assert _hasher.verify(OLD_PASSWORD, stack.repo.users[1].password_hash)


async def test_change_password_revoked_token_hits_middleware_401(stack):
    token = stack.jwt.generate(UserId(1), "alice")
    await stack.auth.change_password(
        user_id=1,
        old_password=OLD_PASSWORD,
        new_password=NEW_PASSWORD,
    )

    # The auth decorator locates the request via isinstance(sanic Request),
    # so exercise it through a real app + ASGI call (same style as
    # tests/test_endpoint_smoke.py).
    app = Sanic("auth_revoked_smoke")
    app.asgi = True
    # noinspection PyTypeChecker
    app.ctx.services = RequestServices(authorization=stack.authz, project_access=None)

    @app.get("/protected")
    @require_auth
    async def protected(_request):
        return json({"ok": True})

    app.finalize()
    app.signalize(allow_fail_builtin=False)

    code, body = await _asgi_get(app, "/protected", token)
    assert code == 401
    assert "revoked" in jsonlib.loads(body)["error"]




# ── logout ────────────────────────────────────────────────────────────


async def test_logout_revokes_only_the_presented_token(stack):
    token_a = stack.jwt.generate(UserId(1), "alice")
    token_b = stack.jwt.generate(UserId(1), "alice")
    claims_a = stack.jwt.verify(token_a)

    await stack.auth.logout(
        user_id=1,
        token_jti=claims_a["jti"],
        token_exp=claims_a["exp"],
    )

    with pytest.raises(AuthenticationError, match="revoked"):
        await stack.authz.authenticate(token_a)
    # The other session is untouched.
    assert (await stack.authz.authenticate(token_b)).user_id == 1


# ── registration switch ───────────────────────────────────────────────


def _settings(allow_open: bool) -> Settings:
    return Settings(auth=AuthConfig(allow_open_register=allow_open))


async def test_register_open_allows_anonymous(stack):
    # noinspection PyTypeChecker
    controller = AuthController(stack.auth, user_svc=None)
    request = _request(
        settings=_settings(True),
        body={"username": "bob", "password": "password123"},
    )
    response = await controller.register(request)
    assert response.status == 201
    assert jsonlib.loads(response.body)["username"] == "bob"


async def test_register_closed_rejects_anonymous_401(stack):
    # noinspection PyTypeChecker
    controller = AuthController(stack.auth, user_svc=None)
    request = _request(
        settings=_settings(False),
        body={"username": "bob", "password": "password123"},
    )
    response = await controller.register(request)
    assert response.status == 401


async def test_register_closed_rejects_non_admin_403(stack):
    # noinspection PyTypeChecker
    controller = AuthController(stack.auth, user_svc=None)
    # noinspection PyTypeChecker
    services = RequestServices(authorization=stack.authz, project_access=None)
    token = stack.jwt.generate(UserId(1), "alice")  # no user:manage
    request = _request(
        settings=_settings(False),
        services=services,
        body={"username": "bob", "password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await controller.register(request)
    assert response.status == 403


async def test_register_closed_allows_user_manage_admin(stack):
    # noinspection PyTypeChecker
    controller = AuthController(stack.auth, user_svc=None)
    # noinspection PyTypeChecker
    services = RequestServices(authorization=stack.authz, project_access=None)
    token = stack.jwt.generate(UserId(2), "admin")
    request = _request(
        settings=_settings(False),
        services=services,
        body={"username": "bob", "password": "password123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await controller.register(request)
    assert response.status == 201


# ── login brute-force protection ─────────────────────────────────────


async def _fail_logins(app, count: int, username: str = "alice") -> None:
    """Post ``count`` wrong-password logins, each rejected with 401."""
    for _ in range(count):
        code, _ = await _asgi_post(app, "/auth/login", {"username": username, "password": "wrong"})
        assert code == 401


async def test_login_locks_out_after_repeated_failures(stack):
    app = await _login_app(stack)
    await _fail_logins(app, 3)
    # Locked out: correct password is rejected with 429 until the cooldown.
    code, body = await _asgi_post(app, "/auth/login", {"username": "alice", "password": OLD_PASSWORD})
    assert code == 429
    assert "too many failed" in jsonlib.loads(body)["error"]


async def test_successful_login_resets_lockout(stack):
    app = await _login_app(stack)
    await _fail_logins(app, 2)
    # Successful login below the threshold clears the failure counter.
    code, _ = await _asgi_post(app, "/auth/login", {"username": "alice", "password": OLD_PASSWORD})
    assert code == 200
    await _fail_logins(app, 3)
    code, _ = await _asgi_post(app, "/auth/login", {"username": "alice", "password": OLD_PASSWORD})
    assert code == 429
