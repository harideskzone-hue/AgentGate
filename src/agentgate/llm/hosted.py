import asyncio
import json
import os
import time
from typing import Any

import httpx

from .types import Message, ModelResponse, ToolCall, Usage


class HostedOpenAIAdapter:
    """Adapter for hosted OpenAI-compatible APIs (OpenAI, Gemini, Groq, Together, etc.)."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.model = model
        self.name = f"hosted:{model}"
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=timeout
        )
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @staticmethod
    def _to_wire(m: Message) -> dict[str, Any]:
        d: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            d["tool_calls"] = [
                {
                    "type": "function",
                    "function": {
                        "name": c.name,
                        "arguments": json.dumps(c.arguments),
                    },
                }
                for c in m.tool_calls
            ]
        return d

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [self._to_wire(m) for m in messages],
            "temperature": temperature,
        }
        if tools:
            body["tools"] = [
                {"type": "function", "function": t} if "function" not in t else t
                for t in tools
            ]

        start = time.perf_counter()
        attempt = 0
        while True:
            try:
                resp = await self._client.post("/chat/completions", json=body)
                if 500 <= resp.status_code < 600 or resp.status_code == 429:
                    attempt += 1
                    if attempt > self.max_retries:
                        resp.raise_for_status()
                    await asyncio.sleep(self.backoff_factor * (2 ** (attempt - 1)))
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.TransportError:
                attempt += 1
                if attempt > self.max_retries:
                    raise
                await asyncio.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        latency = time.perf_counter() - start
        choice = data["choices"][0]["message"]
        tool_calls = []
        for tc in choice.get("tool_calls") or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            tool_calls.append(ToolCall(name=fn.get("name", ""), arguments=args))

        usage_data = data.get("usage", {})
        return ModelResponse(
            message=Message(
                role="assistant",
                content=choice.get("content") or "",
                tool_calls=tool_calls,
            ),
            usage=Usage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            ),
            latency_s=latency,
        )
