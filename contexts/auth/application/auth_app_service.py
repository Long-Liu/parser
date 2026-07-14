from __future__ import annotations

import logging

from contexts.shared.domain.exceptions import AuthenticationError, ConflictError, ValidationError
from contexts.shared.domain.event_publisher import EventPublisher
from contexts.shared.application.transaction import TransactionManager, TransactionalService, transactional
from contexts.auth.domain.user import User
from contexts.auth.application.security import PasswordHasher, TokenService
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.repositories import UserRepository
from contexts.auth.application.dto import LoginCommand, LoginResult, RegisterCommand

logger = logging.getLogger("parser.auth")


class AuthApplicationService(TransactionalService):
    def __init__(self, user_repo: UserRepository, auth_service: AuthenticationService,
                 jwt_service: TokenService,
                 password_hasher: PasswordHasher,
                 event_publisher: EventPublisher | None = None,
                 transaction_manager: TransactionManager | None = None) -> None:
        super().__init__(transaction_manager)
        self._users = user_repo
        self._auth = auth_service
        self._jwt = jwt_service
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher

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
