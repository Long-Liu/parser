from __future__ import annotations

import asyncio
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from contexts.analytics.domain.ports import AIAnalysisPort
from contexts.shared.infrastructure.config import AiAnalysisConfig

# 系统角色指令：限定输出为纯 JSON（配合 response_format=json_object）。
_SYSTEM_PROMPT = (
    "你是电力工程造价数据分析专家。根据给定的项目经营指标 JSON 数据，"
    "生成专业的中文经营分析报告。你必须只返回一个 JSON 对象，"
    "不要包含任何 JSON 以外的文字、注释或 Markdown 代码块标记。"
)

# 单项目分析：输出契约与后端本地 fallback 对齐，UI 直接消费。
_PROJECT_USER_PROMPT = (
    "以下是单个工程项目的经营指标：\n{payload}\n"
    "请返回 JSON 对象，结构必须为：\n"
    '{"health": "healthy|warning", '
    '"summary": "总体经营评估（一段话，引用关键数字）", '
    '"insights": [{"type": "profit|progress|writeoff", "title": "洞察标题", "message": "洞察内容"}], '
    '"recommendations": ["具体建议1", "具体建议2", "具体建议3"]}\n'
    "health 取值为 healthy 或 warning；summary、insights、recommendations 均为中文。"
)

# 多项目对比分析：五章报告，与 UI 对比报告 tab 对齐。
_COMPARE_USER_PROMPT = (
    "以下是多个工程项目的横向对比指标：\n{payload}\n"
    "请返回 JSON 对象，结构必须为：\n"
    '{"chapters": [{"key": "overview", "title": "中文标题", "content": "中文分析段落"}, '
    '{"key": "progress", "title": "中文标题", "content": "中文分析段落"}, '
    '{"key": "cost", "title": "中文标题", "content": "中文分析段落"}, '
    '{"key": "profit", "title": "中文标题", "content": "中文分析段落"}, '
    '{"key": "rating", "title": "中文标题", "content": "中文分析段落"}]}\n'
    "chapters 必须恰好五章，key 依次为 overview、progress、cost、profit、rating，内容均为中文。"
)


class HttpAIAnalysisProvider(AIAnalysisPort):
    """OpenAI-compatible chat-completions adapter (DeepSeek and similar).

    The project metrics are serialized into the user message; the model is
    instructed to reply with a single JSON object matching the application's
    analysis contract. With no URL/key configured, ``analyze`` returns None
    and the application service falls back to its deterministic analysis.
    """

    def __init__(self, config: AiAnalysisConfig) -> None:
        self._url = config.url.strip()
        self._api_key = config.api_key.strip()
        self._model = (config.model or "deepseek-chat").strip()

    async def analyze(self, payload: dict) -> dict | None:
        if not self._url or not self._api_key:
            return None
        return await asyncio.to_thread(self._request, self._url, self._api_key, self._model, payload)

    @staticmethod
    def _request(url: str, api_key: str, model: str, payload: dict) -> dict:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("AI analysis provider URL must use HTTP or HTTPS")

        prompt = _COMPARE_USER_PROMPT if payload.get("type") == "project_comparison" else _PROJECT_USER_PROMPT
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt.replace("{payload}", json.dumps(payload, ensure_ascii=False))},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        # The URL is restricted to HTTP(S) above; Bandit's generic B310 warning
        # cannot infer that validation.
        with urlopen(request, timeout=60) as response:  # nosec B310
            result = json.loads(response.read().decode("utf-8"))
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"AI provider returned an unexpected response: {str(result)[:200]}") from exc
        parsed_content = json.loads(content)
        if not isinstance(parsed_content, dict):
            raise ValueError("AI analysis provider must return a JSON object")
        return parsed_content
