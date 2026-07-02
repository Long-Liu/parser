from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadedFile:
    name: str
    body: bytes
    content_type: str = ""

