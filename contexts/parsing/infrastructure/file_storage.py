from __future__ import annotations

import os
from contextlib import suppress

import aiofiles

from contexts.parsing.application.file_storage import FileStorage, StoredFile
from contexts.shared.infrastructure.config import UploadConfig


class LocalUploadFileStorage(FileStorage):
    def __init__(self, config: UploadConfig, upload_dir: str | None = None) -> None:
        self._upload_dir = os.path.abspath(
            upload_dir or config.dir
        )

    async def save(self, filename: str, body: bytes) -> StoredFile:
        os.makedirs(self._upload_dir, exist_ok=True)
        path = os.path.join(self._upload_dir, filename)
        try:
            async with aiofiles.open(path, "wb") as f:
                await f.write(body)
        except Exception:
            with suppress(OSError):
                os.remove(path)
            raise
        return StoredFile(path=path, size=os.path.getsize(path))

    async def delete(self, stored_file: StoredFile) -> None:
        with suppress(OSError):
            os.remove(stored_file.path)
