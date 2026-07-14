from __future__ import annotations

import os

import aiofiles

from contexts.parsing.application.file_storage import FileStorage, StoredFile
from contexts.shared.infrastructure.database.config import get_config


class LocalUploadFileStorage(FileStorage):
    def __init__(self, upload_dir: str | None = None) -> None:
        self._upload_dir_override = upload_dir

    @property
    def _upload_dir(self) -> str:
        return os.path.abspath(
            self._upload_dir_override or get_config("UPLOAD_DIR")
        )

    async def save(self, filename: str, body: bytes) -> StoredFile:
        os.makedirs(self._upload_dir, exist_ok=True)
        path = os.path.join(self._upload_dir, filename)
        try:
            async with aiofiles.open(path, "wb") as f:
                await f.write(body)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            raise
        return StoredFile(path=path, size=os.path.getsize(path))

    async def delete(self, stored_file: StoredFile) -> None:
        try:
            os.remove(stored_file.path)
        except OSError:
            pass

