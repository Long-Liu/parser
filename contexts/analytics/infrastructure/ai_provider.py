from __future__ import annotations

import asyncio
import json
from urllib.request import Request, urlopen

from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.shared.infrastructure.config import AiAnalysisConfig


class HttpAIAnalysisProvider(AIAnalysisPort):
    """Optional provider adapter configured through ``ai_analysis`` config.

    The remote service receives the project metrics as JSON and returns the
    analysis response consumed by the UI. With no URL configured, the
    application service falls back to its deterministic domain analysis.
    """

    def __init__(self, config: AiAnalysisConfig) -> None:
        self._url = config.url.strip()
        self._api_key = config.api_key.strip()

    async def analyze(self, payload: dict) -> dict | None:
        if not self._url:
            return None
        return await asyncio.to_thread(self._request, self._url, self._api_key, payload)

    @staticmethod
    def _request(url: str, api_key: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = Request(
            url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("AI analysis provider must return a JSON object")
        return result
