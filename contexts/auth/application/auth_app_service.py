from __future__ import annotations

import logging
from collections.abc import Callable

from contexts.shared.domain.exceptions import AuthenticationError, ConflictError, ValidationError
from contexts.shared.domain.unit_of_work import UnitOfWork
from contexts.auth.domain.user import User
from contexts.auth.domain.auth_service import AuthenticationService, hash_password
from contexts.auth.domain.jwt_service import JwtService
from contexts.auth.domain.repositories import UserRepository
from contexts.auth.application.dto import LoginCommand, LoginResult, RegisterCommand

logger = logging.getLogger("parser.auth")


class AuthApplicationService:
    def __init__(self, user_repo: UserRepository, auth_service: AuthenticationService,
                 jwt_service: JwtService,
                 uow_factory: Callable[[], UnitOfWork]) -> None:
        self._users = user_repo
        self._auth = auth_service
        self._jwt = jwt_service
        self._uow_factory = uow_factory

    async def login(self, cmd: LoginCommand) -> LoginResult:
        if not cmd.username or not cmd.password:
            raise AuthenticationError("username and password are required")
        user = await self._users.find_by_username(cmd.username)
        if not user:
            raise AuthenticationError("invalid credentials")
        self._auth.verify_credentials(user, cmd.password)
        if user.id is None:
            raise AuthenticationError("invalid credentials")
        token = self._jwt.generate(user.id, user.username)
        return LoginResult(token=token, user_id=user.id.value,
                           username=user.username, real_name=user.real_name)

    async def register(self, cmd: RegisterCommand) -> dict:
        if not cmd.username or not cmd.password:
            raise ValidationError("username and password are required")
        if len(cmd.password) < 8:
            raise ValidationError("password must be at least 8 characters")
        existing = await self._users.find_by_username(cmd.username)
        if existing:
            raise ConflictError("username already exists")
        hashed = hash_password(cmd.password)
        user = User.create(user_id=None, username=cmd.username, password_hash=hashed,
                           real_name=cmd.real_name, email=cmd.email, phone=cmd.phone)
        async with self._uow_factory() as uow:
            await self._users.save(user)
            await uow.commit()
        if user.id is None:
            raise RuntimeError("user repository did not assign an id")
        return {"id": user.id.value, "username": cmd.username}
