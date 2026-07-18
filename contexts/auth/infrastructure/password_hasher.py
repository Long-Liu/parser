from __future__ import annotations

import bcrypt

from contexts.auth.domain.ports import PasswordHasher


class BCryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )

