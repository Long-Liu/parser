from __future__ import annotations

import asyncio
import json
from urllib.request import Request, urlopen

from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.shared.infrastructure.database.config import get_config


class HttpAIAnalysisProvider(AIAnalysisPort):
    """Optional provider adapter configured through ``ai_analysis`` config.

    The remote service receives the project metrics as JSON and returns the
    analysis response consumed by the UI. With no URL configured, the
    application service falls back to its deterministic domain analysis.
    """

    async def analyze(self, payload: dict) -> dict | None:
        url = get_config("AI_ANALYSIS_URL").strip()
        if not url:
            return None
        return await asyncio.to_thread(self._request, url, payload)

    @staticmethod
    def _request(url: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        api_key = get_config("AI_ANALYSIS_API_KEY").strip()
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
