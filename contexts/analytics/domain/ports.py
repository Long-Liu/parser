from __future__ import annotations

from abc import ABC, abstractmethod


class AIAnalysisPort(ABC):
    @abstractmethod
    async def analyze(self, payload: dict) -> dict | None: ...
