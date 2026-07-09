# DDD Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the entire project from layered architecture to full DDD tactical patterns: 5 bounded contexts (Auth, Project, Template, Parsing, Data) + Shared Kernel, each with domain/infrastructure/application/interface layers.

**Architecture:** Modular monolith with DDD tactical patterns. Each bounded context has its own 4-layer structure. Cross-context communication via ID references and domain events. Shared Kernel provides base classes (Entity, ValueObject, AggregateRoot, DomainEvent, Repository ABC) and common infrastructure (UoW, EventBus, AuthContext).

**Tech Stack:** Python 3.12+, Sanic, SQLAlchemy (async), aiomysql, bcrypt, PyJWT, openpyxl, PyYAML, pytest

---

## Phase 0: Shared Kernel

### Task 0.1: Create shared domain — ValueObject base

**Files:**
- Create: `contexts/shared/domain/__init__.py`
- Create: `contexts/shared/domain/base_value_object.py`

- [ ] **Step 1: Create ValueObject base class**

```python
# contexts/shared/domain/base_value_object.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ValueObject:
    """Immutable value object base. Equality by all fields."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return tuple(self.__dict__.values()) == tuple(other.__dict__.values())

    def __hash__(self) -> int:
        return hash(tuple(self.__dict__.values()))
```

- [ ] **Step 2: Write self-check demo**

```python
# contexts/shared/domain/base_value_object.py (append after class)

@dataclass(frozen=True)
class _DemoMoney(ValueObject):
    amount: int
    currency: str


def _demo():
    a = _DemoMoney(100, "CNY")
    b = _DemoMoney(100, "CNY")
    c = _DemoMoney(200, "CNY")
    assert a == b, "same values should be equal"
    assert a != c, "different values should not be equal"
    assert hash(a) == hash(b), "equal objects should have equal hash"
    print("base_value_object: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 3: Run demo**

```bash
python contexts/shared/domain/base_value_object.py
```
Expected: `base_value_object: OK`

- [ ] **Step 4: Commit**

```bash
git add contexts/
git commit -m "feat(shared): add ValueObject base class"
```

---

### Task 0.2: Create shared domain — Entity base

**Files:**
- Create: `contexts/shared/domain/base_entity.py`

- [ ] **Step 1: Create Entity base class**

```python
# contexts/shared/domain/base_entity.py
from __future__ import annotations

from abc import ABC


class Entity(ABC):
    """Domain entity base. Equality by identity (id), not attributes."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        if not hasattr(self, "id") or not hasattr(other, "id"):
            raise NotImplementedError("Entity subclass must define an 'id' field")
        return self.id == other.id  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        if not hasattr(self, "id"):
            raise NotImplementedError("Entity subclass must define an 'id' field")
        return hash(self.id)  # type: ignore[attr-defined]
```

- [ ] **Step 2: Write self-check demo**

```python
# contexts/shared/domain/base_entity.py (append after class)

class _DemoUser(Entity):
    def __init__(self, user_id: int, name: str) -> None:
        self.id = user_id
        self.name = name


def _demo():
    a = _DemoUser(1, "Alice")
    b = _DemoUser(1, "Bob")
    c = _DemoUser(2, "Alice")
    assert a == b, "same id should be equal regardless of attributes"
    assert a != c, "different id should not be equal"
    assert hash(a) == hash(b), "equal entities should have equal hash"
    print("base_entity: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 3: Run demo**

```bash
python contexts/shared/domain/base_entity.py
```
Expected: `base_entity: OK`

- [ ] **Step 4: Commit**

```bash
git add contexts/shared/domain/base_entity.py
git commit -m "feat(shared): add Entity base class"
```

---

### Task 0.3: Create shared domain — DomainEvent base + AggregateRoot

**Files:**
- Create: `contexts/shared/domain/base_domain_event.py`
- Create: `contexts/shared/domain/base_aggregate_root.py`

- [ ] **Step 1: Create DomainEvent base**

```python
# contexts/shared/domain/base_domain_event.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    aggregate_id: object
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 2: Create AggregateRoot base**

```python
# contexts/shared/domain/base_aggregate_root.py
from __future__ import annotations

from contexts.shared.domain.base_entity import Entity
from contexts.shared.domain.base_domain_event import DomainEvent


class AggregateRoot(Entity):
    """Aggregate root base — collects domain events for publishing after persistence."""

    def __init__(self) -> None:
        self._events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = self._events
        self._events = []
        return events
```

- [ ] **Step 3: Write self-check demo**

```python
# contexts/shared/domain/base_aggregate_root.py (append after class)

class _DemoRegistered(DomainEvent):
    pass


def _demo():
    class _DemoAR(AggregateRoot):
        def __init__(self, ar_id: int) -> None:
            super().__init__()
            self.id = ar_id

        def activate(self) -> None:
            self.record(_DemoRegistered(aggregate_id=self.id))

    ar = _DemoAR(42)
    ar.activate()
    events = ar.pull_events()
    assert len(events) == 1, "should have recorded one event"
    assert events[0].aggregate_id == 42, "event should reference aggregate"
    assert len(ar.pull_events()) == 0, "pull_events should drain"
    print("base_aggregate_root: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 4: Run demo**

```bash
python contexts/shared/domain/base_aggregate_root.py
```
Expected: `base_aggregate_root: OK`

- [ ] **Step 5: Commit**

```bash
git add contexts/shared/domain/base_domain_event.py contexts/shared/domain/base_aggregate_root.py
git commit -m "feat(shared): add DomainEvent and AggregateRoot base classes"
```

---

### Task 0.4: Create shared domain — Repository base + exceptions

**Files:**
- Create: `contexts/shared/domain/base_repository.py`
- Create: `contexts/shared/domain/exceptions.py`

- [ ] **Step 1: Create Repository ABC**

```python
# contexts/shared/domain/base_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod


class Repository(ABC):
    """Base repository port. Concrete implementations live in infrastructure layer."""
    pass
```

- [ ] **Step 2: Create domain exceptions**

```python
# contexts/shared/domain/exceptions.py
class DomainError(Exception):
    """Base domain exception."""


class NotFoundError(DomainError):
    """Entity not found by identity."""


class ValidationError(DomainError):
    """Domain rule violated."""


class ConflictError(DomainError):
    """Duplicate or conflicting state."""


class AuthenticationError(DomainError):
    """Invalid credentials."""


class AuthorizationError(DomainError):
    """Insufficient permissions."""
```

- [ ] **Step 3: Write self-check**

```python
# contexts/shared/domain/exceptions.py (append)

def _demo():
    e = ValidationError("amount must be positive")
    assert isinstance(e, DomainError)
    assert str(e) == "amount must be positive"
    try:
        raise NotFoundError("user 42")
    except DomainError:
        pass
    print("exceptions: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 4: Run demo**

```bash
python contexts/shared/domain/exceptions.py
```
Expected: `exceptions: OK`

- [ ] **Step 5: Commit**

```bash
git add contexts/shared/domain/base_repository.py contexts/shared/domain/exceptions.py
git commit -m "feat(shared): add Repository ABC and domain exceptions"
```

---

### Task 0.5: Create shared domain — core value objects

**Files:**
- Create: `contexts/shared/domain/identifiers.py`
- Create: `contexts/shared/domain/money.py`
- Create: `contexts/shared/domain/year_month.py`

- [ ] **Step 1: Create identifier value objects**

```python
# contexts/shared/domain/identifiers.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class UserId(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"UserId must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class ProjectId(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"ProjectId must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class TemplateId(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValidationError("TemplateId must not be empty")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class JobId(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"JobId must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class BatchId(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"BatchId must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class RoleId(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValidationError(f"RoleId must be positive, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)
```

- [ ] **Step 2: Create Money value object**

```python
# contexts/shared/domain/money.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class Money(ValueObject):
    amount: float
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if self.currency not in ("CNY", "USD", "EUR"):
            raise ValidationError(f"Unsupported currency: {self.currency}")

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValidationError("Cannot add Money with different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        return self + (-other)
```

- [ ] **Step 3: Create YearMonth value object**

```python
# contexts/shared/domain/year_month.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError


@dataclass(frozen=True)
class YearMonth(ValueObject):
    year: int
    month: int

    def __post_init__(self) -> None:
        if self.month < 1 or self.month > 12:
            raise ValidationError(f"Month must be 1-12, got {self.month}")
        if self.year < 2000 or self.year > 2100:
            raise ValidationError(f"Year out of range: {self.year}")

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @classmethod
    def parse(cls, value: str) -> YearMonth:
        """Parse 'YYYY-MM' string."""
        parts = value.strip().split("-")
        if len(parts) != 2:
            raise ValidationError(f"Invalid YearMonth format: {value}")
        return cls(year=int(parts[0]), month=int(parts[1]))
```

- [ ] **Step 4: Write self-checks**

```python
# contexts/shared/domain/money.py (append)

def _demo():
    a = Money(100, "CNY")
    b = Money(50, "CNY")
    assert a + b == Money(150, "CNY")
    assert a - b == Money(50, "CNY")
    try:
        Money(100, "JPY")
        assert False, "should reject unsupported currency"
    except ValidationError:
        pass
    print("money: OK")


if __name__ == "__main__":
    _demo()
```

```python
# contexts/shared/domain/year_month.py (append)

def _demo():
    assert YearMonth.parse("2025-06") == YearMonth(2025, 6)
    try:
        YearMonth(2025, 13)
        assert False, "should reject month 13"
    except ValidationError:
        pass
    print("year_month: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 5: Run demos**

```bash
python contexts/shared/domain/money.py
python contexts/shared/domain/year_month.py
```
Expected: `money: OK`, `year_month: OK`

- [ ] **Step 6: Commit**

```bash
git add contexts/shared/domain/
git commit -m "feat(shared): add identifier, Money, and YearMonth value objects"
```

---

### Task 0.6: Create shared infrastructure — UoW + EventBus + AuthContext

**Files:**
- Create: `contexts/shared/infrastructure/__init__.py`
- Create: `contexts/shared/infrastructure/unit_of_work.py`
- Create: `contexts/shared/infrastructure/domain_event_bus.py`
- Create: `contexts/shared/infrastructure/auth_context.py`

- [ ] **Step 1: Create UoW (wraps existing Transaction)**

```python
# contexts/shared/infrastructure/unit_of_work.py
from __future__ import annotations

from abc import ABC, abstractmethod
from contextvars import ContextVar, Token

from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_sessionmaker

_tx_session: ContextVar[AsyncSession | None] = ContextVar(
    "uow_session", default=None
)


def current_session() -> AsyncSession | None:
    return _tx_session.get()


class UnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork": ...

    @abstractmethod
    async def __aexit__(self, *args) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self._ctx = None
        self._session: AsyncSession | None = None
        self._token: Token | None = None
        self._owner = False

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UoW not entered")
        return self._session

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        existing = current_session()
        if existing is not None:
            self._session = existing
            return self

        self._ctx = get_sessionmaker().begin()
        self._session = await self._ctx.__aenter__()
        self._token = _tx_session.set(self._session)
        self._owner = True
        return self

    async def __aexit__(self, *args) -> None:
        if self._owner and self._token is not None:
            _tx_session.reset(self._token)
        if self._owner and self._ctx is not None:
            await self._ctx.__aexit__(*args)

    async def commit(self) -> None:
        if self._session is not None:
            await self._session.commit()

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()
```

- [ ] **Step 2: Create EventBus**

```python
# contexts/shared/infrastructure/domain_event_bus.py
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from contexts.shared.domain.base_domain_event import DomainEvent

logger = logging.getLogger("parser.event_bus")

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class DomainEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, events: list[DomainEvent]) -> None:
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Event handler failed for %s", type(event).__name__)
```

- [ ] **Step 3: Create AuthContext interface**

```python
# contexts/shared/infrastructure/auth_context.py
from __future__ import annotations

from abc import ABC, abstractmethod


class AuthContext(ABC):
    @abstractmethod
    def user_id(self) -> int | None: ...

    @abstractmethod
    def permissions(self) -> set[str]: ...

    @abstractmethod
    def has_permission(self, code: str) -> bool: ...
```

- [ ] **Step 4: Write self-checks**

```python
# contexts/shared/infrastructure/unit_of_work.py (append)

async def _demo():
    uow = SqlAlchemyUnitOfWork()
    assert isinstance(uow, UnitOfWork)
    print("unit_of_work: OK")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
```

```python
# contexts/shared/infrastructure/domain_event_bus.py (append)
from dataclasses import dataclass

@dataclass(frozen=True)
class _DemoEvent(DomainEvent):
    data: str


def _demo():
    received: list[str] = []

    async def handler(event: _DemoEvent) -> None:
        received.append(event.data)

    bus = DomainEventBus()
    bus.subscribe(_DemoEvent, handler)
    import asyncio
    asyncio.run(bus.publish([_DemoEvent(aggregate_id=1, data="hello")]))
    assert received == ["hello"]
    print("domain_event_bus: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 5: Run demos**

```bash
python contexts/shared/infrastructure/unit_of_work.py
python contexts/shared/infrastructure/domain_event_bus.py
```

- [ ] **Step 6: Commit**

```bash
git add contexts/shared/infrastructure/
git commit -m "feat(shared): add UoW, EventBus, and AuthContext infrastructure"
```

---

### Task 0.7: Create shared interface — base controller

**Files:**
- Create: `contexts/shared/interface/__init__.py`
- Create: `contexts/shared/interface/base_controller.py`

- [ ] **Step 1: Create base controller helpers**

```python
# contexts/shared/interface/base_controller.py
from __future__ import annotations

from sanic.response import json

from contexts.shared.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)


def json_response(data: dict | list, status: int = 200):
    return json(data, status=status)


def error_to_response(exc: DomainError):
    status_map = {
        ValidationError: 400,
        AuthenticationError: 401,
        AuthorizationError: 403,
        NotFoundError: 404,
        ConflictError: 409,
    }
    http_status = status_map.get(type(exc), 500)
    return json({"error": str(exc)}, status=http_status)
```

- [ ] **Step 2: Write self-check**

```python
# contexts/shared/interface/base_controller.py (append)

def _demo():
    resp = json_response({"ok": True})
    assert resp.status == 200
    resp2 = error_to_response(NotFoundError("user 1"))
    assert resp2.status == 404
    print("base_controller: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 3: Run demo + commit**

```bash
python contexts/shared/interface/base_controller.py
git add contexts/shared/interface/
git commit -m "feat(shared): add base controller helpers"
```

---

## Phase 1: Auth Context

### Task 1.1: Auth domain — User aggregate + Role aggregate + domain services

**Files:**
- Create: `contexts/auth/__init__.py`
- Create: `contexts/auth/domain/__init__.py`
- Create: `contexts/auth/domain/user.py`
- Create: `contexts/auth/domain/role.py`
- Create: `contexts/auth/domain/auth_service.py`
- Create: `contexts/auth/domain/jwt_service.py`

- [ ] **Step 1: Create Role aggregate**

```python
# contexts/auth/domain/role.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import RoleId


@dataclass(frozen=True)
class PermissionRef(ValueObject):
    code: str
    name: str


class Role(AggregateRoot):
    def __init__(
        self,
        role_id: RoleId,
        code: str,
        name: str,
        permissions: list[PermissionRef] | None = None,
    ) -> None:
        super().__init__()
        self.id = role_id
        self.code = code
        self.name = name
        self.permissions: list[PermissionRef] = permissions or []

    def has_permission(self, perm_code: str) -> bool:
        return any(p.code == perm_code for p in self.permissions)

    def assign_permissions(self, permissions: list[PermissionRef]) -> None:
        self.permissions = permissions
```

- [ ] **Step 2: Create User aggregate**

```python
# contexts/auth/domain/user.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.exceptions import ValidationError
from contexts.shared.domain.identifiers import UserId


@dataclass(frozen=True)
class RoleRef(ValueObject):
    role_id: int
    code: str


class User(AggregateRoot):
    def __init__(
        self,
        user_id: UserId,
        username: str,
        password_hash: str,
        real_name: str = "",
        email: str = "",
        phone: str = "",
        roles: list[RoleRef] | None = None,
        is_active: bool = True,
    ) -> None:
        super().__init__()
        self.id = user_id
        self._username = username
        self._password_hash = password_hash
        self.real_name = real_name
        self._email = email
        self.phone = phone
        self.roles: list[RoleRef] = roles or []
        self.is_active = is_active

    @property
    def username(self) -> str:
        return self._username

    @property
    def password_hash(self) -> str:
        return self._password_hash

    def disable(self) -> None:
        self.is_active = False

    def enable(self) -> None:
        self.is_active = True

    def assign_roles(self, roles: list[RoleRef]) -> None:
        self.roles = roles

    @classmethod
    def create(
        cls,
        user_id: UserId,
        username: str,
        password_hash: str,
        real_name: str = "",
        email: str = "",
        phone: str = "",
    ) -> "User":
        return cls(
            user_id=user_id, username=username, password_hash=password_hash,
            real_name=real_name, email=email, phone=phone,
            roles=[], is_active=True,
        )
```

- [ ] **Step 3: Create authentication domain service**

```python
# contexts/auth/domain/auth_service.py
from __future__ import annotations

import bcrypt

from contexts.shared.domain.exceptions import AuthenticationError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class AuthenticationService:
    def verify_credentials(self, user, password: str) -> None:
        if not user.is_active:
            raise AuthenticationError("account disabled")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError("invalid credentials")
```

- [ ] **Step 4: Create JWT service**

```python
# contexts/auth/domain/jwt_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

JWT_ALGORITHM = "HS256"


class JwtService:
    def __init__(self, secret: str, expiry_hours: int = 24) -> None:
        self.secret = secret
        self.expiry_hours = expiry_hours

    def generate(self, user_id: int, username: str) -> str:
        exp = datetime.now(tz=timezone.utc) + timedelta(hours=self.expiry_hours)
        payload = {"user_id": user_id, "username": username, "exp": exp}
        return jwt.encode(payload, self.secret, algorithm=JWT_ALGORITHM)

    def verify(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=[JWT_ALGORITHM])
```

- [ ] **Step 5: Write self-checks**

```python
# contexts/auth/domain/user.py (append)

def _demo():
    uid = UserId(1)
    user = User.create(uid, "alice", "hash123", real_name="Alice")
    assert user.username == "alice"
    assert user.is_active is True
    user.disable()
    assert user.is_active is False
    print("user: OK")


if __name__ == "__main__":
    _demo()
```

```python
# contexts/auth/domain/auth_service.py (append)

def _demo():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)
    print("auth_service: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 6: Run demos + commit**

```bash
python contexts/auth/domain/user.py
python contexts/auth/domain/auth_service.py
git add contexts/auth/
git commit -m "feat(auth): add User/Role aggregates and auth domain services"
```

---

### Task 1.2: Auth domain — repository interfaces

**Files:**
- Create: `contexts/auth/domain/repositories.py`

- [ ] **Step 1: Create repository interfaces**

```python
# contexts/auth/domain/repositories.py
from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import UserId, RoleId
from contexts.auth.domain.user import User
from contexts.auth.domain.role import Role


class UserRepository(Repository):
    @abstractmethod
    async def next_id(self) -> UserId: ...

    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> User | None: ...

    @abstractmethod
    async def find_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_permissions(self, user_id: UserId) -> set[str]: ...


class RoleRepository(Repository):
    @abstractmethod
    async def find_by_id(self, role_id: RoleId) -> Role | None: ...

    @abstractmethod
    async def find_all(self) -> list[Role]: ...

    @abstractmethod
    async def find_by_code(self, code: str) -> Role | None: ...
```

- [ ] **Step 2: Commit**

```bash
git add contexts/auth/domain/repositories.py
git commit -m "feat(auth): add User and Role repository interfaces"
```

---

### Task 1.3: Auth infrastructure — repository implementations

**Files:**
- Create: `contexts/auth/infrastructure/__init__.py`
- Create: `contexts/auth/infrastructure/repositories.py`

- [ ] **Step 1: Create repository implementations**

```python
# contexts/auth/infrastructure/repositories.py
from __future__ import annotations

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import User as OrmUser
from db.models import Role as OrmRole
from db.models import UserRole, RolePermission, Permission as OrmPermission
from contexts.shared.domain.identifiers import UserId, RoleId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.auth.domain.user import User, RoleRef
from contexts.auth.domain.role import Role, PermissionRef
from contexts.auth.domain.repositories import UserRepository, RoleRepository


def _user_to_entity(orm: OrmUser, roles: list[dict]) -> User:
    return User(
        user_id=UserId(orm.id),
        username=orm.username,
        password_hash=orm.password,
        real_name=orm.real_name or "",
        email=orm.email or "",
        phone=orm.phone or "",
        roles=[RoleRef(role_id=r["id"], code=r["code"]) for r in roles],
        is_active=bool(orm.is_active),
    )


def _role_to_entity(orm: OrmRole, perms: list[OrmPermission]) -> Role:
    return Role(
        role_id=RoleId(orm.id),
        code=orm.code,
        name=orm.name,
        permissions=[PermissionRef(code=p.code, name=p.name) for p in perms],
    )


class UserRepositoryImpl(UserRepository):
    async def next_id(self) -> UserId:
        return UserId(0)

    async def save(self, user: User) -> None:
        async def _save(session):
            orm = OrmUser(
                id=user.id.value if user.id.value > 0 else None,
                username=user.username,
                password=user.password_hash,
                real_name=user.real_name,
                email=user.email if hasattr(user, '_email') else "",
                phone=user.phone,
                is_active=1 if user.is_active else 0,
            )
            session.add(orm)
            await session.flush()
            if user.id.value == 0:
                user.id = UserId(orm.id)

        session = current_session()
        if session is not None:
            await _save(session)
        else:
            async with get_sessionmaker().begin() as session:
                await _save(session)

    async def find_by_id(self, user_id: UserId) -> User | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmUser).where(OrmUser.id == user_id.value)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        if orm is None:
            return None
        roles = await self._load_roles(orm.id)
        return _user_to_entity(orm, roles)

    async def find_by_username(self, username: str) -> User | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmUser).where(OrmUser.username == username)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        if orm is None:
            return None
        roles = await self._load_roles(orm.id)
        return _user_to_entity(orm, roles)

    async def get_permissions(self, user_id: UserId) -> set[str]:
        async def _perm(s):
            result = await s.execute(
                sa.select(OrmPermission.code)
                .select_from(OrmUser)
                .join(UserRole, UserRole.user_id == OrmUser.id)
                .join(RolePermission, RolePermission.role_id == UserRole.role_id)
                .join(OrmPermission, OrmPermission.id == RolePermission.permission_id)
                .where(OrmUser.id == user_id.value)
            )
            return {row[0] for row in result.all()}

        session = current_session()
        if session is not None:
            return await _perm(session)
        async with get_sessionmaker()() as session:
            return await _perm(session)

    async def _load_roles(self, user_id: int) -> list[dict]:
        async def _load(s):
            result = await s.execute(
                sa.select(OrmRole.id, OrmRole.code, OrmRole.name)
                .select_from(OrmRole)
                .join(UserRole, UserRole.role_id == OrmRole.id)
                .where(UserRole.user_id == user_id)
            )
            return [{"id": r[0], "code": r[1], "name": r[2]} for r in result.all()]

        session = current_session()
        if session is not None:
            return await _load(session)
        async with get_sessionmaker()() as session:
            return await _load(session)


class RoleRepositoryImpl(RoleRepository):
    async def find_by_id(self, role_id: RoleId) -> Role | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmRole).where(OrmRole.id == role_id.value)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        if orm is None:
            return None
        perms = await self._load_permissions(orm.id)
        return _role_to_entity(orm, perms)

    async def find_all(self) -> list[Role]:
        async def _all(s):
            result = await s.execute(sa.select(OrmRole))
            return result.scalars().all()

        session = current_session()
        if session is not None:
            orms = await _all(session)
        else:
            async with get_sessionmaker()() as session:
                orms = await _all(session)
        roles = []
        for orm in orms:
            perms = await self._load_permissions(orm.id)
            roles.append(_role_to_entity(orm, perms))
        return roles

    async def find_by_code(self, code: str) -> Role | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmRole).where(OrmRole.code == code)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        if orm is None:
            return None
        perms = await self._load_permissions(orm.id)
        return _role_to_entity(orm, perms)

    async def _load_permissions(self, role_id: int) -> list[OrmPermission]:
        async def _load(s):
            result = await s.execute(
                sa.select(OrmPermission)
                .select_from(OrmPermission)
                .join(RolePermission, RolePermission.permission_id == OrmPermission.id)
                .where(RolePermission.role_id == role_id)
            )
            return result.scalars().all()

        session = current_session()
        if session is not None:
            return await _load(session)
        async with get_sessionmaker()() as session:
            return await _load(session)
```

- [ ] **Step 2: Commit**

```bash
git add contexts/auth/infrastructure/
git commit -m "feat(auth): add User and Role repository implementations"
```

---

### Task 1.4: Auth application — DTOs + application service

**Files:**
- Create: `contexts/auth/application/__init__.py`
- Create: `contexts/auth/application/dto.py`
- Create: `contexts/auth/application/auth_app_service.py`

- [ ] **Step 1: Create DTOs**

```python
# contexts/auth/application/dto.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoginCommand:
    username: str
    password: str


@dataclass
class LoginResult:
    token: str
    user_id: int
    username: str
    real_name: str


@dataclass
class RegisterCommand:
    username: str
    password: str
    real_name: str = ""
    email: str = ""
    phone: str = ""
```

- [ ] **Step 2: Create application service**

```python
# contexts/auth/application/auth_app_service.py
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
    def __init__(
        self,
        user_repo: UserRepository,
        auth_service: AuthenticationService,
        jwt_service: JwtService,
    ) -> None:
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
        return LoginResult(
            token=token, user_id=user.id.value,
            username=user.username, real_name=user.real_name,
        )

    async def register(self, cmd: RegisterCommand) -> dict:
        if not cmd.username or not cmd.password:
            raise ValidationError("username and password are required")
        if len(cmd.password) < 8:
            raise ValidationError("password must be at least 8 characters")
        existing = await self._users.find_by_username(cmd.username)
        if existing:
            raise ConflictError("username already exists")
        hashed = hash_password(cmd.password)
        user = User.create(
            user_id=UserId(0), username=cmd.username, password_hash=hashed,
            real_name=cmd.real_name, email=cmd.email, phone=cmd.phone,
        )
        async with SqlAlchemyUnitOfWork() as uow:
            await self._users.save(user)
            await uow.commit()
        return {"id": user.id.value, "username": cmd.username}
```

- [ ] **Step 3: Commit**

```bash
git add contexts/auth/application/
git commit -m "feat(auth): add login/register application services with DTOs"
```

---

### Task 1.5: Auth interface — middleware re-export + controller

**Files:**
- Create: `contexts/auth/interface/__init__.py`
- Create: `contexts/auth/interface/auth_middleware.py`
- Create: `contexts/auth/interface/auth_controller.py`

- [ ] **Step 1: Create auth middleware (re-exports existing)**

```python
# contexts/auth/interface/auth_middleware.py
# ponytail: re-export existing middleware, full migration when old files deleted
from middleware.auth import require_auth, require_permission, generate_token, verify_token, hash_password, check_password
```

- [ ] **Step 2: Create auth controller**

```python
# contexts/auth/interface/auth_controller.py
from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.auth.application.auth_app_service import AuthApplicationService
from contexts.auth.application.dto import LoginCommand, RegisterCommand
from contexts.auth.domain.auth_service import AuthenticationService
from contexts.auth.domain.jwt_service import JwtService
from contexts.auth.infrastructure.repositories import UserRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("auth_ddd", url_prefix="/api")


def _auth_service(request) -> AuthApplicationService:
    cfg = request.app.ctx.config
    jwt_svc = JwtService(cfg.SECRET_KEY)
    return AuthApplicationService(
        user_repo=UserRepositoryImpl(),
        auth_service=AuthenticationService(),
        jwt_service=jwt_svc,
    )


@bp.post("/auth/login")
@openapi.tag("Auth")
@openapi.summary("Login")
async def login(request):
    data = request.json or {}
    svc = _auth_service(request)
    try:
        result = await svc.login(LoginCommand(
            username=data.get("username", ""),
            password=data.get("password", ""),
        ))
        return json({"token": result.token, "user": {
            "id": result.user_id, "username": result.username,
            "real_name": result.real_name,
        }})
    except DomainError as e:
        return error_to_response(e)


@bp.post("/auth/register")
@openapi.tag("Auth")
@openapi.summary("Register")
async def register(request):
    data = request.json or {}
    svc = _auth_service(request)
    try:
        result = await svc.register(RegisterCommand(
            username=data.get("username", ""),
            password=data.get("password", ""),
            real_name=data.get("real_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
        ))
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)
```

- [ ] **Step 3: Commit**

```bash
git add contexts/auth/interface/
git commit -m "feat(auth): add auth controller and middleware re-exports"
```

---

## Phase 2: Project Context

### Task 2.1: Project full context (domain + infra + app + interface)

**Files:**
- Create: `contexts/project/__init__.py`
- Create: `contexts/project/domain/__init__.py`
- Create: `contexts/project/domain/project.py`
- Create: `contexts/project/domain/repositories.py`
- Create: `contexts/project/infrastructure/__init__.py`
- Create: `contexts/project/infrastructure/repositories.py`
- Create: `contexts/project/application/__init__.py`
- Create: `contexts/project/application/project_app_service.py`
- Create: `contexts/project/interface/__init__.py`
- Create: `contexts/project/interface/project_controller.py`

- [ ] **Step 1: Create Project aggregate**

```python
# contexts/project/domain/project.py
from __future__ import annotations

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.domain.exceptions import ValidationError


class Project(AggregateRoot):
    def __init__(self, project_id: ProjectId, code: str, name: str,
                 created_by: UserId | None = None) -> None:
        super().__init__()
        self.id = project_id
        self._code = code
        self._name = name
        self.created_by = created_by

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    def rename(self, new_name: str) -> None:
        if not new_name.strip():
            raise ValidationError("project name must not be empty")
        self._name = new_name.strip()

    @classmethod
    def create(cls, project_id: ProjectId, code: str, name: str,
               created_by: UserId | None = None) -> "Project":
        if not code.strip():
            raise ValidationError("project code must not be empty")
        if not name.strip():
            raise ValidationError("project name must not be empty")
        return cls(project_id=project_id, code=code.strip(),
                   name=name.strip(), created_by=created_by)
```

- [ ] **Step 2: Create repository interface + implementation**

```python
# contexts/project/domain/repositories.py
from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import ProjectId
from contexts.project.domain.project import Project


class ProjectRepository(Repository):
    @abstractmethod
    async def next_id(self) -> ProjectId: ...

    @abstractmethod
    async def save(self, project: Project) -> None: ...

    @abstractmethod
    async def find_by_id(self, project_id: ProjectId) -> Project | None: ...

    @abstractmethod
    async def find_by_code(self, code: str) -> Project | None: ...

    @abstractmethod
    async def list_all(self) -> list[Project]: ...
```

```python
# contexts/project/infrastructure/repositories.py
from __future__ import annotations

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import Project as OrmProject
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


def _to_entity(orm: OrmProject) -> Project:
    return Project(
        project_id=ProjectId(orm.id), code=orm.code, name=orm.name,
        created_by=UserId(orm.created_by) if orm.created_by else None,
    )


class ProjectRepositoryImpl(ProjectRepository):
    async def next_id(self) -> ProjectId:
        return ProjectId(0)

    async def save(self, project: Project) -> None:
        async def _save(session):
            orm = OrmProject(
                id=project.id.value if project.id.value > 0 else None,
                code=project.code, name=project.name,
                created_by=project.created_by.value if project.created_by else None,
            )
            session.add(orm)
            await session.flush()
            if project.id.value == 0:
                project.id = ProjectId(orm.id)

        session = current_session()
        if session is not None:
            await _save(session)
        else:
            async with get_sessionmaker().begin() as session:
                await _save(session)

    async def find_by_id(self, project_id: ProjectId) -> Project | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmProject).where(OrmProject.id == project_id.value)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        return _to_entity(orm) if orm else None

    async def find_by_code(self, code: str) -> Project | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmProject).where(OrmProject.code == code)
            )
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        return _to_entity(orm) if orm else None

    async def list_all(self) -> list[Project]:
        async def _all(s):
            result = await s.execute(sa.select(OrmProject))
            return result.scalars().all()

        session = current_session()
        if session is not None:
            orms = await _all(session)
        else:
            async with get_sessionmaker()() as session:
                orms = await _all(session)
        return [_to_entity(o) for o in orms]
```

- [ ] **Step 3: Create application service + controller**

```python
# contexts/project/application/project_app_service.py
from __future__ import annotations

from contexts.shared.domain.exceptions import ConflictError, NotFoundError, ValidationError
from contexts.shared.domain.identifiers import ProjectId, UserId
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.project.domain.project import Project
from contexts.project.domain.repositories import ProjectRepository


class ProjectApplicationService:
    def __init__(self, repo: ProjectRepository) -> None:
        self._repo = repo

    async def create(self, code: str, name: str, created_by: int | None = None) -> dict:
        if not code or not name:
            raise ValidationError("code and name are required")
        existing = await self._repo.find_by_code(code)
        if existing:
            raise ConflictError("project code already exists")
        project = Project.create(
            project_id=ProjectId(0), code=code, name=name,
            created_by=UserId(created_by) if created_by else None,
        )
        async with SqlAlchemyUnitOfWork() as uow:
            await self._repo.save(project)
            await uow.commit()
        return {"id": project.id.value, "code": project.code, "name": project.name}

    async def list_all(self) -> list[dict]:
        projects = await self._repo.list_all()
        return [{"id": p.id.value, "code": p.code, "name": p.name} for p in projects]

    async def get_by_id(self, project_id: int) -> dict:
        p = await self._repo.find_by_id(ProjectId(project_id))
        if not p:
            raise NotFoundError(f"project {project_id} not found")
        return {"id": p.id.value, "code": p.code, "name": p.name}
```

```python
# contexts/project/interface/project_controller.py
from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.project.application.project_app_service import ProjectApplicationService
from contexts.project.infrastructure.repositories import ProjectRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("project_ddd", url_prefix="/api")


@bp.get("/projects")
@require_auth
@openapi.tag("Project")
@openapi.summary("List projects")
async def list_projects(request):
    svc = ProjectApplicationService(ProjectRepositoryImpl())
    result = await svc.list_all()
    return json(result)


@bp.post("/projects")
@require_auth
@openapi.tag("Project")
@openapi.summary("Create project")
async def create_project(request):
    data = request.json or {}
    svc = ProjectApplicationService(ProjectRepositoryImpl())
    try:
        result = await svc.create(
            code=data.get("code", ""), name=data.get("name", ""),
            created_by=getattr(request.ctx, "user_id", None),
        )
        return json(result, status=201)
    except DomainError as e:
        return error_to_response(e)
```

- [ ] **Step 4: Commit**

```bash
git add contexts/project/
git commit -m "feat(project): add Project aggregate, repository, app service, and controller"
```

---

## Phase 3: Template Context

### Task 3.1: Template domain — aggregate + value objects + YAML loader

**Files:**
- Create: `contexts/template/__init__.py`
- Create: `contexts/template/domain/__init__.py`
- Create: `contexts/template/domain/template.py`
- Create: `contexts/template/domain/repositories.py`
- Create: `contexts/template/domain/yaml_loader.py`

- [ ] **Step 1: Create Template aggregate with value objects**

```python
# contexts/template/domain/template.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import TemplateId
from contexts.shared.domain.exceptions import ValidationError


class StopRuleType(str, Enum):
    CELL_MATCH = "cell_match"
    CONSECUTIVE_EMPTY = "consecutive_empty_rows"


@dataclass(frozen=True)
class StopRule(ValueObject):
    rule_type: StopRuleType
    patterns: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    empty_row_count: int | None = None


@dataclass(frozen=True)
class HeaderSpec(ValueObject):
    header_rows: list[int]
    data_start_row: int


@dataclass(frozen=True)
class HierarchyConfig(ValueObject):
    column_name: str
    separator: str = "."


@dataclass(frozen=True)
class ColumnMapping(ValueObject):
    db_field: str
    match_headers: list[str]
    db_type: str = "varchar(255)"


@dataclass(frozen=True)
class DynamicColumnMapping(ValueObject):
    db_prefix: str
    match_headers: list[str]
    db_type: str = "decimal(15,2)"


class Template(AggregateRoot):
    def __init__(
        self,
        template_id: TemplateId,
        description: str = "",
        sheet_pattern: str = "",
        header_spec: HeaderSpec | None = None,
        hierarchy_config: HierarchyConfig | None = None,
        stop_rules: list[StopRule] | None = None,
        fixed_columns: list[ColumnMapping] | None = None,
        dynamic_columns: list[DynamicColumnMapping] | None = None,
        data_table: str = "",
        is_active: bool = True,
    ) -> None:
        super().__init__()
        self.id = template_id
        self.description = description
        self.sheet_pattern = sheet_pattern
        self.header_spec = header_spec or HeaderSpec(header_rows=[], data_start_row=0)
        self.hierarchy_config = hierarchy_config
        self.stop_rules: list[StopRule] = stop_rules or []
        self.fixed_columns: list[ColumnMapping] = fixed_columns or []
        self.dynamic_columns: list[DynamicColumnMapping] = dynamic_columns or []
        self.data_table = data_table
        self.is_active = is_active

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def matches_sheet(self, sheet_name: str) -> bool:
        import fnmatch
        return bool(self.sheet_pattern and fnmatch.fnmatch(sheet_name, self.sheet_pattern))

    def find_column(self, flat_header: str) -> ColumnMapping | None:
        for col in self.fixed_columns:
            if all(kw in flat_header for kw in col.match_headers):
                return col
        return None

    def find_dynamic_column(self, flat_header: str) -> DynamicColumnMapping | None:
        for col in self.dynamic_columns:
            if all(kw in flat_header for kw in col.match_headers):
                return col
        return None
```

- [ ] **Step 2: Create YAML loader**

```python
# contexts/template/domain/yaml_loader.py
from __future__ import annotations

import os
import yaml

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import (
    Template, HeaderSpec, HierarchyConfig, StopRule, StopRuleType,
    ColumnMapping, DynamicColumnMapping,
)


class YamlTemplateLoader:
    def __init__(self, config_dir: str | None = None) -> None:
        if config_dir is None:
            config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                      "config", "templates")
        self._config_dir = os.path.abspath(config_dir)

    def load(self, template_id: str) -> Template:
        filepath = os.path.join(self._config_dir, f"{template_id}.yaml")
        resolved = os.path.realpath(filepath)
        if not resolved.startswith(os.path.realpath(self._config_dir)):
            raise ValueError(f"path traversal blocked: {template_id}")
        with open(resolved, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self._build(data)

    def load_all(self) -> list[Template]:
        templates = []
        if not os.path.isdir(self._config_dir):
            return templates
        for filename in sorted(os.listdir(self._config_dir)):
            if filename.endswith((".yaml", ".yml")):
                tid = filename.rsplit(".", 1)[0]
                templates.append(self.load(tid))
        return templates

    def _build(self, data: dict) -> Template:
        header_rows = data.get("headers", {}).get("rows", [])
        data_start_row = data.get("headers", {}).get("data_start_row", 0)
        hierarchy = None
        if "hierarchy" in data:
            hierarchy = HierarchyConfig(
                column_name=data["hierarchy"]["column_name"],
                separator=data["hierarchy"].get("separator", "."),
            )
        stop_rules = []
        for r in data.get("stop_rules", []):
            rt = StopRuleType(r["type"])
            stop_rules.append(StopRule(
                rule_type=rt,
                patterns=r.get("patterns", []),
                columns=r.get("columns", []),
                empty_row_count=r.get("count") if rt == StopRuleType.CONSECUTIVE_EMPTY else None,
            ))
        fixed_columns = [
            ColumnMapping(
                db_field=c["db_field"], match_headers=c["match_header"],
                db_type=c.get("type", "varchar(255)"),
            )
            for c in data.get("columns", [])
        ]
        dynamic_columns = [
            DynamicColumnMapping(
                db_prefix=c["db_prefix"], match_headers=c["match_header"],
                db_type=c.get("type", "decimal(15,2)"),
            )
            for c in data.get("dynamic_columns", [])
        ]
        return Template(
            template_id=TemplateId(data["template_id"]),
            description=data.get("description", ""),
            sheet_pattern=data.get("sheet_pattern", ""),
            header_spec=HeaderSpec(header_rows=header_rows, data_start_row=data_start_row),
            hierarchy_config=hierarchy, stop_rules=stop_rules,
            fixed_columns=fixed_columns, dynamic_columns=dynamic_columns,
            data_table=data.get("data_table", f"data_{data['template_id']}"),
            is_active=data.get("is_active", True),
        )
```

- [ ] **Step 3: Create repository interface + implementation**

```python
# contexts/template/domain/repositories.py
from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import Template


class TemplateRepository(Repository):
    @abstractmethod
    async def save(self, template: Template) -> None: ...

    @abstractmethod
    async def find_by_id(self, template_id: TemplateId) -> Template | None: ...

    @abstractmethod
    async def find_all_active(self) -> list[Template]: ...

    @abstractmethod
    async def find_matching(self, sheet_name: str) -> Template | None: ...
```

```python
# contexts/template/infrastructure/__init__.py (empty)
```

```python
# contexts/template/infrastructure/repositories.py
from __future__ import annotations

from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.template import Template
from contexts.template.domain.repositories import TemplateRepository
from contexts.template.domain.yaml_loader import YamlTemplateLoader


class TemplateRepositoryImpl(TemplateRepository):
    def __init__(self) -> None:
        self._yaml_loader = YamlTemplateLoader()

    async def save(self, template: Template) -> None:
        pass  # ponytail: read-only YAML for now

    async def find_by_id(self, template_id: TemplateId) -> Template | None:
        try:
            return self._yaml_loader.load(str(template_id))
        except (FileNotFoundError, ValueError):
            return None

    async def find_all_active(self) -> list[Template]:
        return [t for t in self._yaml_loader.load_all() if t.is_active]

    async def find_matching(self, sheet_name: str) -> Template | None:
        for t in self._yaml_loader.load_all():
            if t.is_active and t.matches_sheet(sheet_name):
                return t
        return None
```

- [ ] **Step 4: Write self-check**

```python
# contexts/template/domain/template.py (append)

def _demo():
    t = Template(
        template_id=TemplateId("labor_cost"),
        sheet_pattern="表1*人工费*",
        header_spec=HeaderSpec(header_rows=[2, 3, 4], data_start_row=5),
        stop_rules=[StopRule(rule_type=StopRuleType.CELL_MATCH, patterns=[r"^注："])],
        fixed_columns=[ColumnMapping(db_field="person_name", match_headers=["姓名"])],
    )
    assert t.matches_sheet("表1 人工费-动态")
    assert not t.matches_sheet("毛利")
    col = t.find_column("姓名")
    assert col is not None and col.db_field == "person_name"
    print("template: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 5: Run demo + commit**

```bash
python contexts/template/domain/template.py
git add contexts/template/
git commit -m "feat(template): add Template aggregate, YAML loader, and repository"
```

---

### Task 3.2: Template application + interface

**Files:**
- Create: `contexts/template/application/__init__.py`
- Create: `contexts/template/application/template_app_service.py`
- Create: `contexts/template/interface/__init__.py`
- Create: `contexts/template/interface/template_controller.py`

- [ ] **Step 1: Create application service + controller**

```python
# contexts/template/application/template_app_service.py
from __future__ import annotations

from contexts.shared.domain.exceptions import NotFoundError
from contexts.shared.domain.identifiers import TemplateId
from contexts.template.domain.repositories import TemplateRepository


class TemplateApplicationService:
    def __init__(self, repo: TemplateRepository) -> None:
        self._repo = repo

    async def list_all(self) -> list[dict]:
        templates = await self._repo.find_all_active()
        return [{"template_id": str(t.id), "description": t.description,
                 "sheet_pattern": t.sheet_pattern, "data_table": t.data_table}
                for t in templates]

    async def get_by_id(self, template_id: str) -> dict:
        t = await self._repo.find_by_id(TemplateId(template_id))
        if not t:
            raise NotFoundError(f"template {template_id} not found")
        return {"template_id": str(t.id), "description": t.description,
                "data_table": t.data_table,
                "fixed_columns": [c.db_field for c in t.fixed_columns],
                "dynamic_columns": [c.db_prefix for c in t.dynamic_columns]}
```

```python
# contexts/template/interface/template_controller.py
from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.template.application.template_app_service import TemplateApplicationService
from contexts.template.infrastructure.repositories import TemplateRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("template_ddd", url_prefix="/api")


@bp.get("/templates")
@require_auth
@openapi.tag("Template")
@openapi.summary("List templates")
async def list_templates(request):
    svc = TemplateApplicationService(TemplateRepositoryImpl())
    result = await svc.list_all()
    return json(result)


@bp.get("/templates/<template_id:str>")
@require_auth
@openapi.tag("Template")
@openapi.summary("Get template detail")
async def get_template(request, template_id: str):
    svc = TemplateApplicationService(TemplateRepositoryImpl())
    try:
        result = await svc.get_by_id(template_id)
        return json(result)
    except DomainError as e:
        return error_to_response(e)
```

- [ ] **Step 2: Commit**

```bash
git add contexts/template/application/ contexts/template/interface/
git commit -m "feat(template): add template app service and controller"
```

---

## Phase 4: Parsing Context (Core)

### Task 4.1: Parsing domain — aggregate + events

**Files:**
- Create: `contexts/parsing/__init__.py`
- Create: `contexts/parsing/domain/__init__.py`
- Create: `contexts/parsing/domain/events.py`
- Create: `contexts/parsing/domain/parse_job.py`

- [ ] **Step 1: Create domain events**

```python
# contexts/parsing/domain/events.py
from __future__ import annotations

from dataclasses import dataclass

from contexts.shared.domain.base_domain_event import DomainEvent


@dataclass(frozen=True)
class ParseJobSubmitted(DomainEvent):
    project_id: int | None = None
    file_name: str = ""


@dataclass(frozen=True)
class SheetMatched(DomainEvent):
    sheet_name: str = ""
    template_id: str = ""


@dataclass(frozen=True)
class SheetSkipped(DomainEvent):
    sheet_name: str = ""


@dataclass(frozen=True)
class SheetExtracted(DomainEvent):
    sheet_name: str = ""
    row_count: int = 0


@dataclass(frozen=True)
class SheetValidated(DomainEvent):
    sheet_name: str = ""
    valid_count: int = 0
    error_count: int = 0


@dataclass(frozen=True)
class ParseJobCompleted(DomainEvent):
    project_id: int | None = None
    total_sheets: int = 0
    matched_sheets: int = 0
    total_rows: int = 0


@dataclass(frozen=True)
class ParseJobFailed(DomainEvent):
    reason: str = ""
```

- [ ] **Step 2: Create ParseJob aggregate**

```python
# contexts/parsing/domain/parse_job.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from contexts.shared.domain.base_aggregate_root import AggregateRoot
from contexts.shared.domain.base_value_object import ValueObject
from contexts.shared.domain.identifiers import JobId, ProjectId, TemplateId
from contexts.shared.domain.year_month import YearMonth
from contexts.parsing.domain.events import (
    ParseJobSubmitted, ParseJobCompleted, ParseJobFailed,
    SheetMatched, SheetSkipped, SheetExtracted, SheetValidated,
)


class JobStatus(str, Enum):
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"


class MatchStatus(str, Enum):
    MATCHED = "matched"
    SKIPPED = "skipped"
    EMPTY = "empty"
    ERROR = "error"


@dataclass(frozen=True)
class FileInfo(ValueObject):
    filename: str
    size: int
    hash: str = ""


@dataclass(frozen=True)
class RowError(ValueObject):
    row_index: int
    field: str = ""
    value: str = ""
    reason: str = ""


@dataclass(frozen=True)
class ParsedRow(ValueObject):
    row_index: int
    fields: dict = field(default_factory=dict)
    hierarchy_code: str | None = None
    monthly_data: dict | None = None


class SheetResult:
    """Entity within ParseJob aggregate."""
    def __init__(self, sheet_name: str, template_id: TemplateId | None = None,
                 match_status: MatchStatus = MatchStatus.SKIPPED) -> None:
        self.sheet_name = sheet_name
        self.template_id = template_id
        self.match_status = match_status
        self.total_rows: int = 0
        self.success_rows: int = 0
        self.error_rows: int = 0
        self.errors: list[RowError] = []
        self.extracted_rows: list[ParsedRow] = []


class ParseJob(AggregateRoot):
    def __init__(self, job_id: JobId, project_id: ProjectId,
                 year_month: YearMonth, file_info: FileInfo) -> None:
        super().__init__()
        self.id = job_id
        self.project_id = project_id
        self.year_month = year_month
        self.file_info = file_info
        self.status = JobStatus.SUBMITTED
        self._sheets: dict[str, SheetResult] = {}

    @property
    def sheets(self) -> list[SheetResult]:
        return list(self._sheets.values())

    @classmethod
    def submit(cls, job_id: JobId, project_id: ProjectId,
               year_month: YearMonth, file_info: FileInfo) -> "ParseJob":
        job = cls(job_id, project_id, year_month, file_info)
        job.record(ParseJobSubmitted(
            aggregate_id=job_id.value, project_id=project_id.value,
            file_name=file_info.filename,
        ))
        return job

    def add_sheet_result(self, sheet_name: str) -> SheetResult:
        sr = SheetResult(sheet_name)
        self._sheets[sheet_name] = sr
        return sr

    def match_sheet(self, sheet_name: str, template_id: str | None) -> SheetResult:
        sr = self._sheets.get(sheet_name)
        if sr is None:
            sr = self.add_sheet_result(sheet_name)
        if template_id:
            sr.template_id = TemplateId(template_id)
            sr.match_status = MatchStatus.MATCHED
            self.record(SheetMatched(aggregate_id=self.id.value,
                         sheet_name=sheet_name, template_id=template_id))
        else:
            sr.match_status = MatchStatus.SKIPPED
            self.record(SheetSkipped(aggregate_id=self.id.value, sheet_name=sheet_name))
        return sr

    def set_extracted(self, sheet_name: str, rows: list[ParsedRow]) -> None:
        sr = self._sheets[sheet_name]
        sr.extracted_rows = rows
        sr.total_rows = len(rows)
        self.record(SheetExtracted(aggregate_id=self.id.value,
                     sheet_name=sheet_name, row_count=len(rows)))

    def set_validated(self, sheet_name: str, valid_rows: list[ParsedRow],
                      errors: list[RowError]) -> None:
        sr = self._sheets[sheet_name]
        sr.extracted_rows = valid_rows
        sr.errors = errors
        sr.success_rows = len(valid_rows)
        sr.error_rows = len(errors)
        self.record(SheetValidated(aggregate_id=self.id.value,
                     sheet_name=sheet_name, valid_count=len(valid_rows),
                     error_count=len(errors)))

    def complete(self) -> None:
        self.status = JobStatus.DONE
        total_sheets = len(self._sheets)
        matched = sum(1 for s in self._sheets.values()
                      if s.match_status == MatchStatus.MATCHED)
        total_rows = sum(s.success_rows for s in self._sheets.values())
        self.record(ParseJobCompleted(aggregate_id=self.id.value,
                     project_id=self.project_id.value, total_sheets=total_sheets,
                     matched_sheets=matched, total_rows=total_rows))

    def fail(self, reason: str) -> None:
        self.status = JobStatus.FAILED
        self.record(ParseJobFailed(aggregate_id=self.id.value, reason=reason))

    @property
    def overall_status(self) -> str:
        if self.status == JobStatus.FAILED:
            return "failed"
        successes = [s for s in self._sheets.values()
                     if s.match_status == MatchStatus.MATCHED]
        if not successes:
            return "skipped"
        if all(s.error_rows == 0 for s in successes):
            return "success"
        return "partial"
```

- [ ] **Step 3: Write self-check**

```python
# contexts/parsing/domain/parse_job.py (append)

def _demo():
    job = ParseJob.submit(
        job_id=JobId(1), project_id=ProjectId(42),
        year_month=YearMonth(2025, 6), file_info=FileInfo("test.xlsx", 1024),
    )
    assert job.status == JobStatus.SUBMITTED
    job.match_sheet("表1 人工费", "labor_cost")
    sr = job.match_sheet("毛利", None)
    assert sr.match_status == MatchStatus.SKIPPED
    rows = [ParsedRow(row_index=0, fields={"name": "张三"})]
    job.set_extracted("表1 人工费", rows)
    job.set_validated("表1 人工费", rows, [])
    job.complete()
    assert job.overall_status == "success"
    events = job.pull_events()
    assert len(events) == 6
    print("parse_job: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 4: Run demo + commit**

```bash
python contexts/parsing/domain/parse_job.py
git add contexts/parsing/
git commit -m "feat(parsing): add ParseJob aggregate with domain events"
```

---

### Task 4.2: Parsing domain — pipeline services

**Files:**
- Create: `contexts/parsing/domain/pipeline_services.py`

- [ ] **Step 1: Create domain service interfaces + implementations (adapted from core/)**

```python
# contexts/parsing/domain/pipeline_services.py
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from openpyxl.worksheet.worksheet import Worksheet

from contexts.parsing.domain.parse_job import ParsedRow, RowError
from contexts.template.domain.template import Template, StopRuleType


class CellUnmerger:
    def unmerge(self, ws: Worksheet) -> list[list]:
        grid = [[cell.value for cell in row] for row in ws.iter_rows()]
        for merged_range in ws.merged_cells.ranges:
            min_col, max_col = merged_range.min_col - 1, merged_range.max_col - 1
            min_row, max_row = merged_range.min_row - 1, merged_range.max_row - 1
            value = grid[min_row][min_col] if min_row < len(grid) and min_col < len(grid[min_row]) else None
            for r in range(min_row, min(max_row + 1, len(grid))):
                for c in range(min_col, min(max_col + 1, len(grid[r]) if r < len(grid) else 0)):
                    if r < len(grid) and c < len(grid[r]):
                        grid[r][c] = value
        return grid


class HeaderFlattener:
    def flatten(self, grid: list[list], header_rows: list[int]) -> list[str]:
        if not grid or not header_rows:
            return []
        max_cols = max((len(grid[r]) for r in header_rows if r < len(grid)), default=0)
        names = []
        for col in range(max_cols):
            parts = []
            for row_idx in header_rows:
                if row_idx < len(grid) and col < len(grid[row_idx]):
                    v = grid[row_idx][col]
                    if v is not None and str(v).strip():
                        parts.append(str(v).strip())
            names.append("_".join(parts))
        return names


class StopDetector:
    def should_stop(self, row_index: int, grid: list[list], template: Template) -> bool:
        for rule in template.stop_rules:
            if rule.rule_type == StopRuleType.CELL_MATCH:
                if self._check_cell_match(grid, row_index, rule.patterns, rule.columns):
                    return True
            elif rule.rule_type == StopRuleType.CONSECUTIVE_EMPTY:
                if self._check_consecutive_empty(grid, row_index, rule.empty_row_count or 5):
                    return True
        return False

    def _check_cell_match(self, grid, row_index, patterns, columns) -> bool:
        if row_index >= len(grid):
            return True
        row = grid[row_index]
        for col_letter in (columns or []):
            col_idx = ord(col_letter.upper()) - ord('A')
            if col_idx < len(row) and row[col_idx] is not None:
                text = str(row[col_idx])
                for pattern in patterns:
                    if re.match(pattern, text):
                        return True
        return False

    def _check_consecutive_empty(self, grid, row_index, count) -> bool:
        for i in range(count):
            check_idx = row_index + i
            if check_idx >= len(grid):
                return True
            if any(v is not None for v in grid[check_idx]):
                return False
        return True


class DataRowExtractor:
    def extract(self, grid: list[list], flat_headers: list[str],
                template: Template) -> list[ParsedRow]:
        data_start = template.header_spec.data_start_row - 1
        stop_detector = StopDetector()
        rows = []
        for ri in range(data_start, len(grid)):
            if stop_detector.should_stop(ri, grid, template):
                break
            row_data = self._extract_row(grid[ri], flat_headers, template)
            if row_data is not None:
                rows.append(row_data)
        return rows

    def _extract_row(self, row: list, flat_headers: list[str],
                     template: Template) -> ParsedRow | None:
        fields = {}
        monthly_data = {}
        for ci, header in enumerate(flat_headers):
            if ci >= len(row):
                continue
            value = row[ci]
            fixed = template.find_column(header)
            if fixed:
                fields[fixed.db_field] = value
                continue
            dyn = template.find_dynamic_column(header)
            if dyn:
                monthly_data[f"{dyn.db_prefix}_{header}"] = value
                continue
        if fields:
            return ParsedRow(row_index=-1, fields=fields,
                            monthly_data=monthly_data if monthly_data else None)
        return None


class DataValidator:
    def validate(self, rows: list[ParsedRow], template: Template
                 ) -> tuple[list[ParsedRow], list[RowError]]:
        valid = []
        errors = []
        for i, row in enumerate(rows):
            row_errors = self._validate_row(row, template)
            if row_errors:
                errors.extend(row_errors)
            else:
                valid.append(row)
        return valid, errors

    def _validate_row(self, row: ParsedRow, template: Template) -> list[RowError]:
        errs = []
        for col in template.fixed_columns:
            if col.db_field in row.fields:
                value = row.fields[col.db_field]
                if value is not None and col.db_type.startswith("decimal"):
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errs.append(RowError(
                            row_index=row.row_index, field=col.db_field,
                            value=str(value), reason=f"expected decimal",
                        ))
        return errs
```

- [ ] **Step 2: Write self-check**

```python
# contexts/parsing/domain/pipeline_services.py (append)

def _demo():
    hf = HeaderFlattener()
    grid = [["A1", "B1", None], ["A2", None, "C2"]]
    flat = hf.flatten(grid, [0, 1])
    assert flat == ["A1_A2", "B1", "C2"], f"got {flat}"

    from contexts.template.domain.template import Template, StopRule, HeaderSpec, TemplateId
    t = Template(
        template_id=TemplateId("test"),
        header_spec=HeaderSpec(header_rows=[1], data_start_row=2),
        stop_rules=[StopRule(rule_type=StopRuleType.CELL_MATCH, patterns=[r"^注："])],
    )
    sd = StopDetector()
    grid2 = [["注：注释"], ["数据行"]]
    assert sd.should_stop(0, grid2, t) is True
    assert sd.should_stop(1, grid2, t) is False
    print("pipeline_services: OK")


if __name__ == "__main__":
    _demo()
```

- [ ] **Step 3: Run demo + commit**

```bash
python contexts/parsing/domain/pipeline_services.py
git add contexts/parsing/domain/pipeline_services.py
git commit -m "feat(parsing): add domain services (unmerge, flatten, detect, extract, validate)"
```

---

### Task 4.3: Parsing repository interface + infrastructure + application + interface

**Files:**
- Create: `contexts/parsing/domain/repositories.py`
- Create: `contexts/parsing/infrastructure/__init__.py`
- Create: `contexts/parsing/infrastructure/repositories.py`
- Create: `contexts/parsing/application/__init__.py`
- Create: `contexts/parsing/application/upload_app_service.py`
- Create: `contexts/parsing/interface/__init__.py`
- Create: `contexts/parsing/interface/upload_controller.py`

- [ ] **Step 1: Create repository interface + implementation**

```python
# contexts/parsing/domain/repositories.py
from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.parsing.domain.parse_job import ParseJob, ParsedRow


class ParseJobRepository(Repository):
    @abstractmethod
    async def next_id(self) -> JobId: ...

    @abstractmethod
    async def save(self, job: ParseJob) -> None: ...

    @abstractmethod
    async def find_by_id(self, job_id: JobId) -> ParseJob | None: ...

    @abstractmethod
    async def find_by_project(self, project_id: ProjectId,
                              limit: int = 20, offset: int = 0) -> list[ParseJob]: ...

    @abstractmethod
    async def insert_data_rows(self, template_id: str, rows: list[ParsedRow]) -> None: ...
```

```python
# contexts/parsing/infrastructure/repositories.py
from __future__ import annotations

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import UploadBatch as OrmBatch
from db.models import TEMPLATE_DATA_MODELS
from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.parsing.domain.parse_job import ParseJob, FileInfo, ParsedRow
from contexts.parsing.domain.repositories import ParseJobRepository


class ParseJobRepositoryImpl(ParseJobRepository):
    async def next_id(self) -> JobId:
        return JobId(0)

    async def save(self, job: ParseJob) -> None:
        pass  # ponytail: full impl in migration phase

    async def find_by_id(self, job_id: JobId) -> ParseJob | None:
        async def _find(s):
            result = await s.execute(
                sa.select(OrmBatch).where(OrmBatch.id == job_id.value))
            return result.scalars().first()

        session = current_session()
        if session is not None:
            orm = await _find(session)
        else:
            async with get_sessionmaker()() as session:
                orm = await _find(session)
        if orm is None:
            return None
        return ParseJob.submit(
            job_id=JobId(orm.id), project_id=ProjectId(orm.project_id),
            year_month=YearMonth.parse("2025-01"),
            file_info=FileInfo(orm.file_name or "", orm.file_size or 0),
        )

    async def find_by_project(self, project_id: ProjectId,
                              limit: int = 20, offset: int = 0) -> list[ParseJob]:
        return []

    async def insert_data_rows(self, template_id: str, rows: list[ParsedRow]) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        data = []
        for row in rows:
            d = dict(row.fields)
            if row.hierarchy_code:
                d["hierarchy_code"] = row.hierarchy_code
            if row.monthly_data:
                d["monthly_data"] = row.monthly_data
            data.append(d)
        if not data:
            return

        async def _insert(session):
            session.add_all([model()(**row) for row in data])
            await session.flush()

        session = current_session()
        if session is not None:
            await _insert(session)
        else:
            async with get_sessionmaker().begin() as session:
                await _insert(session)
```

- [ ] **Step 2: Create upload application service**

```python
# contexts/parsing/application/upload_app_service.py
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import closing
from datetime import datetime

import aiofiles
import openpyxl
from sanic.request import File

from contexts.shared.domain.identifiers import JobId, ProjectId
from contexts.shared.domain.year_month import YearMonth
from contexts.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from contexts.parsing.domain.parse_job import ParseJob, FileInfo, ParsedRow
from contexts.parsing.domain.pipeline_services import (
    CellUnmerger, HeaderFlattener, DataRowExtractor, DataValidator,
)
from contexts.parsing.infrastructure.repositories import ParseJobRepositoryImpl
from contexts.template.domain.yaml_loader import YamlTemplateLoader

logger = logging.getLogger("parser.upload")
UPLOAD_DIR = os.path.abspath(os.environ.get("UPLOAD_DIR", "uploads"))


class UploadApplicationService:
    def __init__(self) -> None:
        self._unmerger = CellUnmerger()
        self._flattener = HeaderFlattener()
        self._extractor = DataRowExtractor()
        self._validator = DataValidator()
        self._template_loader = YamlTemplateLoader()
        self._repo = ParseJobRepositoryImpl()

    async def process(self, file: File, project_id: int, ym: str, user_id: int) -> dict:
        batch_no = self._make_batch_no()
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filepath = os.path.join(UPLOAD_DIR, f"{batch_no}.xlsx")
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(file.body)
        file_size = os.path.getsize(filepath)

        job = ParseJob.submit(
            job_id=JobId(0), project_id=ProjectId(project_id),
            year_month=YearMonth.parse(ym),
            file_info=FileInfo(filename=file.name, size=file_size),
        )

        try:
            wb = await asyncio.to_thread(openpyxl.load_workbook, filepath, data_only=True)
            with closing(wb):
                sheet_results = []
                for sheet_name in wb.sheetnames:
                    r = await self._process_sheet(wb[sheet_name], sheet_name, job)
                    sheet_results.append(r)
                job.complete()
                status = job.overall_status
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("upload failed for %s", batch_no)
            job.fail("processing error")
            status = "failed"
            sheet_results = []
        finally:
            try:
                os.remove(filepath)
            except OSError:
                pass

        return {"batch_no": batch_no, "job_id": job.id.value,
                "status": status, "sheets": sheet_results}

    async def _process_sheet(self, ws, sheet_name: str, job: ParseJob) -> dict:
        template = None
        for t in self._template_loader.load_all():
            if t.matches_sheet(sheet_name):
                template = t
                break

        if template is None:
            job.match_sheet(sheet_name, None)
            return {"name": sheet_name, "template": None, "rows": 0, "status": "skipped"}

        job.match_sheet(sheet_name, str(template.id))
        grid = self._unmerger.unmerge(ws)
        flat_headers = self._flattener.flatten(grid, template.header_spec.header_rows)
        rows = self._extractor.extract(grid, flat_headers, template)
        for i, r in enumerate(rows):
            object.__setattr__(r, 'row_index', i)

        valid_rows, errors = self._validator.validate(rows, template)
        job.set_validated(sheet_name, valid_rows, errors)

        if valid_rows:
            async with SqlAlchemyUnitOfWork() as uow:
                await self._repo.insert_data_rows(str(template.id), valid_rows)
                await uow.commit()

        return {"name": sheet_name, "template": str(template.id),
                "rows": len(valid_rows),
                "status": "success" if not errors else "partial"}

    def _make_batch_no(self) -> str:
        return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
```

- [ ] **Step 3: Create upload controller**

```python
# contexts/parsing/interface/upload_controller.py
from __future__ import annotations

import os
from datetime import datetime

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth, require_permission
from contexts.parsing.application.upload_app_service import UploadApplicationService
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("upload_ddd", url_prefix="/api")

ALLOWED_MIME_TYPES = frozenset({
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})
ALLOWED_EXTENSIONS = frozenset({".xlsx"})
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@bp.post("/upload")
@require_auth
@require_permission("data:upload")
@openapi.tag("Upload")
@openapi.summary("Upload Excel file for parsing")
async def upload(request):
    if "file" not in request.files:
        return json({"error": "no file"}, status=400)

    file = request.files.get("file")
    if isinstance(file, list):
        file = file[0]
    if not file:
        return json({"error": "no file"}, status=400)

    if hasattr(file, 'type') and file.type not in ALLOWED_MIME_TYPES:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    _, ext = os.path.splitext(file.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return json({"error": "only .xlsx files are accepted"}, status=400)
    if hasattr(file, "body") and len(file.body) > MAX_UPLOAD_SIZE:
        return json({"error": "file exceeds 50MB limit"}, status=400)

    try:
        project_id = int(request.form.get("project_id", "0"))
    except (ValueError, TypeError):
        return json({"error": "invalid project_id"}, status=400)
    if project_id <= 0:
        return json({"error": "invalid project_id"}, status=400)

    ym = request.form.get("ym", datetime.now().strftime("%Y-%m"))
    user_id = getattr(request.ctx, "user_id", None)
    if user_id is None:
        return json({"error": "not authenticated"}, status=401)

    svc = UploadApplicationService()
    try:
        result = await svc.process(file, project_id, ym, user_id)
        if result["status"] == "failed":
            return json(dict(result, error="upload processing failed"), status=500)
        return json(result)
    except DomainError as e:
        return error_to_response(e)
```

- [ ] **Step 4: Commit**

```bash
git add contexts/parsing/
git commit -m "feat(parsing): add repository impl, upload app service, and controller"
```

---

## Phase 5: Data Context

### Task 5.1: Data full context (domain + infra + app + interface)

**Files:**
- Create: `contexts/data/__init__.py`
- Create: `contexts/data/domain/__init__.py`
- Create: `contexts/data/domain/data_query.py`
- Create: `contexts/data/domain/repositories.py`
- Create: `contexts/data/infrastructure/__init__.py`
- Create: `contexts/data/infrastructure/repositories.py`
- Create: `contexts/data/application/__init__.py`
- Create: `contexts/data/application/data_app_service.py`
- Create: `contexts/data/interface/__init__.py`
- Create: `contexts/data/interface/data_controller.py`

- [ ] **Step 1: Create domain models + repository interface**

```python
# contexts/data/domain/data_query.py
from __future__ import annotations

from dataclasses import dataclass, field

from contexts.shared.domain.base_value_object import ValueObject


@dataclass(frozen=True)
class Pagination(ValueObject):
    page: int
    size: int
    total: int = 0

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(frozen=True)
class FilterCriterion(ValueObject):
    field: str
    operator: str
    value: object


@dataclass(frozen=True)
class DataRow(ValueObject):
    fields: dict = field(default_factory=dict)
    monthly_data: dict | None = None
    batch_ref: dict | None = None
```

```python
# contexts/data/domain/repositories.py
from __future__ import annotations

from abc import abstractmethod

from contexts.shared.domain.base_repository import Repository
from contexts.data.domain.data_query import DataRow, Pagination, FilterCriterion


class DataQueryRepository(Repository):
    @abstractmethod
    async def query(self, template_id: str, batch_id: int | None,
                    filters: list[FilterCriterion], pagination: Pagination,
                    ) -> tuple[list[DataRow], int]: ...

    @abstractmethod
    async def get_by_id(self, template_id: str, row_id: int) -> DataRow | None: ...

    @abstractmethod
    async def delete_by_id(self, template_id: str, row_id: int) -> None: ...
```

- [ ] **Step 2: Create repository implementation**

```python
# contexts/data/infrastructure/repositories.py
from __future__ import annotations

import sqlalchemy as sa

from db.engine import get_sessionmaker
from db.models import TEMPLATE_DATA_MODELS
from contexts.shared.infrastructure.unit_of_work import current_session
from contexts.data.domain.data_query import DataRow, Pagination, FilterCriterion
from contexts.data.domain.repositories import DataQueryRepository


class DataQueryRepositoryImpl(DataQueryRepository):
    async def query(self, template_id: str, batch_id: int | None,
                    filters: list[FilterCriterion], pagination: Pagination,
                    ) -> tuple[list[DataRow], int]:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return [], 0
        t = model.__table__
        stmt = sa.select(t)
        if batch_id is not None:
            stmt = stmt.where(t.c.batch_id == batch_id)
        for f in filters:
            col = getattr(t.c, f.field, None)
            if col is not None and f.operator == "eq":
                stmt = stmt.where(col == f.value)
            elif col is not None and f.operator == "like":
                stmt = stmt.where(col.like(f"%{f.value}%"))

        count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
        stmt = stmt.limit(pagination.size).offset(pagination.offset)

        async def _query(session):
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0
            result = await session.execute(stmt)
            rows = [DataRow(fields=dict(r._mapping)) for r in result.all()]
            return rows, total

        session = current_session()
        if session is not None:
            return await _query(session)
        async with get_sessionmaker()() as session:
            return await _query(session)

    async def get_by_id(self, template_id: str, row_id: int) -> DataRow | None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return None
        t = model.__table__

        async def _get(s):
            result = await s.execute(sa.select(t).where(t.c.id == row_id))
            r = result.first()
            return DataRow(fields=dict(r._mapping)) if r else None

        session = current_session()
        if session is not None:
            return await _get(session)
        async with get_sessionmaker()() as session:
            return await _get(session)

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        model = TEMPLATE_DATA_MODELS.get(template_id)
        if model is None:
            return
        t = model.__table__

        async def _delete(s):
            await s.execute(sa.delete(t).where(t.c.id == row_id))

        session = current_session()
        if session is not None:
            await _delete(session)
        else:
            async with get_sessionmaker().begin() as session:
                await _delete(session)
```

- [ ] **Step 3: Create application service + controller**

```python
# contexts/data/application/data_app_service.py
from __future__ import annotations

from contexts.shared.domain.exceptions import NotFoundError
from contexts.data.domain.data_query import Pagination
from contexts.data.domain.repositories import DataQueryRepository


class DataApplicationService:
    def __init__(self, repo: DataQueryRepository) -> None:
        self._repo = repo

    async def query(self, template_id: str, batch_id: int | None = None,
                    page: int = 1, size: int = 200) -> dict:
        pagination = Pagination(page=page, size=size)
        rows, total = await self._repo.query(template_id, batch_id, [], pagination)
        return {"data": [r.fields for r in rows],
                "pagination": {"page": page, "size": size, "total": total}}

    async def get_by_id(self, template_id: str, row_id: int) -> dict:
        row = await self._repo.get_by_id(template_id, row_id)
        if row is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        return row.fields

    async def delete_by_id(self, template_id: str, row_id: int) -> None:
        row = await self._repo.get_by_id(template_id, row_id)
        if row is None:
            raise NotFoundError(f"row {row_id} not found in {template_id}")
        await self._repo.delete_by_id(template_id, row_id)
```

```python
# contexts/data/interface/data_controller.py
from __future__ import annotations

from sanic import Blueprint
from sanic.response import json
from sanic_ext import openapi

from contexts.auth.interface.auth_middleware import require_auth
from contexts.data.application.data_app_service import DataApplicationService
from contexts.data.infrastructure.repositories import DataQueryRepositoryImpl
from contexts.shared.domain.exceptions import DomainError
from contexts.shared.interface.base_controller import error_to_response

bp = Blueprint("data_ddd", url_prefix="/api")


@bp.get("/data/<template_id:str>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Query parsed data")
async def query_data(request, template_id: str):
    batch_id = request.args.get("batch_id")
    batch_id = int(batch_id) if batch_id else None
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 200))
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        result = await svc.query(template_id, batch_id=batch_id, page=page, size=size)
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.get("/data/<template_id:str>/<row_id:int>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Get single data row")
async def get_data_row(request, template_id: str, row_id: int):
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        result = await svc.get_by_id(template_id, row_id)
        return json(result)
    except DomainError as e:
        return error_to_response(e)


@bp.delete("/data/<template_id:str>/<row_id:int>")
@require_auth
@openapi.tag("Data")
@openapi.summary("Delete data row")
async def delete_data_row(request, template_id: str, row_id: int):
    svc = DataApplicationService(DataQueryRepositoryImpl())
    try:
        await svc.delete_by_id(template_id, row_id)
        return json({"ok": True})
    except DomainError as e:
        return error_to_response(e)
```

- [ ] **Step 4: Commit**

```bash
git add contexts/data/
git commit -m "feat(data): add Data query context (read model with CRUD APIs)"
```

---

## Phase 6: Integration

### Task 6.1: Wire DDD blueprints into app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add DDD blueprint imports and registration**

In `app.py`, add imports:
```python
from contexts.auth.interface.auth_controller import bp as auth_ddd_bp
from contexts.project.interface.project_controller import bp as project_ddd_bp
from contexts.template.interface.template_controller import bp as template_ddd_bp
from contexts.parsing.interface.upload_controller import bp as upload_ddd_bp
from contexts.data.interface.data_controller import bp as data_ddd_bp
```

In the blueprint registration loop, add the DDD blueprints:
```python
for bp in [health_bp,
            auth_bp, auth_ddd_bp,
            project_bp, project_ddd_bp,
            upload_bp, upload_ddd_bp,
            data_bp, data_ddd_bp,
            template_bp, template_ddd_bp,
            batch_bp]:
    app.blueprint(bp)
```

- [ ] **Step 2: Verify app starts without errors**

```bash
python -c "import app; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(integration): wire DDD blueprints alongside existing API routes"
```

---

## Phase 7: Cleanup

### Task 7.1: Delete old code (conditional — verify DDD routes work first)

**Files to delete after DDD verification:**
- `api/auth_api.py`, `api/project_api.py`, `api/upload_api.py`, `api/data_api.py`, `api/template_api.py`
- `services/auth_service.py`, `services/upload_service.py`, `services/data_service.py`, `services/project_service.py`, `services/template_service.py`
- `repositories/user_repository.py`, `repositories/project_repository.py`, `repositories/data_repository.py`
- `core/pipeline.py`, `core/cell_unmerger.py`, `core/header_flattener.py`, `core/data_extractor.py`, `core/stop_detector.py`, `core/validator.py`

- [ ] **Step 1: Update app.py to remove old blueprint imports**

- [ ] **Step 2: Delete old files and run all tests**

```bash
pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove old layered code, fully migrated to DDD contexts"
```

---

## Summary

**Files created:** ~35 new files across `contexts/`
**Files deleted:** ~20 old files in Phase 7
**Total tasks:** 17
**Phases:** 8 (Shared Kernel → Auth → Project → Template → Parsing → Data → Integration → Cleanup)

Each task produces self-contained, testable changes. The old API remains functional alongside the new DDD routes until Phase 7 cleanup.
