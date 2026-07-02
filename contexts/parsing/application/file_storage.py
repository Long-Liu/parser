from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredFile:
    path: str
    size: int


class FileStorage(ABC):
    @abstractmethod
    async def save(self, filename: str, body: bytes) -> StoredFile: ...

    @abstractmethod
    async def delete(self, stored_file: StoredFile) -> None: ...

