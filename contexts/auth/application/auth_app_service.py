from __future__ import annotations

import logging

from contexts.shared.domain.exceptions import AuthenticationError, ConflictError, ValidationError
from contexts.shared.domain.identifiers import UserId
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.auth.domain.user import User
from contexts.auth.domain.auth_service import AuthenticationService, hash_password
from contexts.auth.domain.jwt_service import JwtService
from contexts.auth.domain.repositories import UserRepository
from contexts.auth.application.dto import LoginCommand, LoginResult, RegisterCommand

logger = logging.getLogger("parser.auth")


class AuthApplicationService:
    def __init__(self, user_repo: UserRepository, auth_service: AuthenticationService,
                 jwt_service: JwtService) -> None:
        self._users = user_repo
        self._auth = auth_service
        self._jwt = jwt_service

    async def login(self, cmd: LoginCommand) -> LoginResult:
        if not cmd.username or not cmd.password:
            raise AuthenticationError("username and password are required")
        user = await self._users.find_by_username(cmd.username)
        if not user:
            raise AuthenticationError("invalid credentials")
        self._auth.verify_credentials(user, cmd.password)
        token = self._jwt.generate(user.id.value, user.username)
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
        user = User.create(user_id=UserId(0), username=cmd.username, password_hash=hashed,
                           real_name=cmd.real_name, email=cmd.email, phone=cmd.phone)
        async with SqlAlchemyUnitOfWork() as uow:
            await self._users.save(user)
            await uow.commit()
        return {"id": user.id.value, "username": cmd.username}
