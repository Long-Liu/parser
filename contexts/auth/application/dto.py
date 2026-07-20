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
    department: str = ""
