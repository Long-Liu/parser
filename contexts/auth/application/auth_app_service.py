from __future__ import annotations

import logging
from datetime import datetime, timezone

from contexts.shared.domain.exceptions import AuthenticationError, ConflictError, ValidationError
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.application.transaction import TransactionManager, TransactionalService, transactional
from contexts.shared.domain.identifiers import UserId
from contexts.auth.domain.password import Password
from contexts.auth.domain.user import User
from contexts.auth.domain.ports import PasswordHasher, TokenService
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.repositories import TokenRevocationRepository, UserRepository
from contexts.auth.application.dto import LoginCommand, LoginResult, RegisterCommand

logger = logging.getLogger("parser.auth")


class AuthApplicationService(TransactionalService):
    def __init__(self, user_repo: UserRepository, auth_service: AuthenticationService,
                 jwt_service: TokenService,
                 password_hasher: PasswordHasher,
                 event_publisher: EventPublisher | None = None,
                 transaction_manager: TransactionManager | None = None,
                 token_revocations: TokenRevocationRepository | None = None) -> None:
        super().__init__(transaction_manager)
        self._users = user_repo
        self._auth = auth_service
        self._jwt = jwt_service
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher
        self._token_revocations = token_revocations

    async def login(self, cmd: LoginCommand) -> LoginResult:
        if not cmd.username or not cmd.password:
            raise AuthenticationError("username and password are required")
        user = await self._users.find_by_username(cmd.username)
        # Always run password verify to prevent username enumeration via timing.
        # When user doesn't exist, verify against a dummy hash so the bcrypt cost
        # is identical to the "user exists, wrong password" path.
        if user is not None:
            self._auth.verify_credentials(user, cmd.password)
        else:
            self._password_hasher.verify(
                cmd.password,
                "$2b$12$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
            raise AuthenticationError("invalid credentials")
        if user.id is None:
            raise AuthenticationError("invalid credentials")
        token = self._jwt.generate(user.id, user.username)
        return LoginResult(token=token, user_id=user.id.value,
                           username=user.username, real_name=user.real_name)

    @transactional
    async def register(self, cmd: RegisterCommand) -> dict:
        if not cmd.username or not cmd.password:
            raise ValidationError("username and password are required")
        if len(cmd.password) < 8:
            raise ValidationError("password must be at least 8 characters")
        existing = await self._users.find_by_username(cmd.username)
        if existing:
            raise ConflictError("username already exists")
        hashed = self._password_hasher.hash(cmd.password)
        user = User.create(user_id=None, username=cmd.username, password_hash=hashed,
                           real_name=cmd.real_name, email=cmd.email, phone=cmd.phone,
                           department=cmd.department)
        await self._users.save(user)
        if user.id is None:
            raise RuntimeError("user repository did not assign an id")
        if self._event_publisher:
            await self._event_publisher.publish(user.pull_events())
        return {"id": user.id.value, "username": cmd.username}

    @transactional
    async def change_password(self, *, user_id: int, old_password: str,
                              new_password: str) -> None:
        """Self-service password change; invalidates all existing tokens.

        Error semantics mirror login: a wrong old password raises
        AuthenticationError (401); a non-compliant new password raises
        ValidationError (400) via the Password value object.
        """
        if not old_password or not new_password:
            raise ValidationError("old_password and new_password are required")
        user = await self._users.find_by_id(UserId(user_id))
        if user is None:
            raise AuthenticationError("invalid credentials")
        self._auth.verify_credentials(user, old_password)
        user.reset_password(self._password_hasher.hash(str(Password(new_password))))
        await self._users.save(user)
        if self._event_publisher:
            await self._event_publisher.publish(user.pull_events())
        # User-wide revocation: blacklists every token of this user whose iat
        # is at/before now — the current token included, so no per-jti entry
        # is needed here. The entry lives until all pre-change tokens would
        # have expired anyway (now + max token lifetime).
        if self._token_revocations is not None:
            horizon = datetime.now(timezone.utc) + self._jwt.max_lifetime()
            await self._token_revocations.revoke_all_for_user(
                user_id=UserId(user_id), expires_at=horizon,
            )

    async def logout(self, *, user_id: int, token_jti: str | None = None,
                     token_exp: int | float | None = None) -> None:
        """Blacklist the presented token until its natural expiry."""
        if self._token_revocations is None or not token_jti:
            # Tokens minted before jti support cannot be blacklisted
            # individually; they expire naturally within max_lifetime().
            return
        if token_exp:
            expires_at = datetime.fromtimestamp(float(token_exp), tz=timezone.utc)
        else:
            expires_at = datetime.now(timezone.utc) + self._jwt.max_lifetime()
        await self._token_revocations.revoke(
            jti=token_jti, user_id=UserId(user_id), expires_at=expires_at,
        )
