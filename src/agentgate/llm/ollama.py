import asyncio
import time
from typing import Any

import httpx

from .types import Message, ModelResponse, ToolCall, Usage


class OllamaAdapter:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.model = model
        self.name = f"ollama:{model}"
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @staticmethod
    def _to_wire(m: Message) -> dict[str, Any]:
        d: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            d["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}}
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
            "stream": False,
            "messages": [self._to_wire(m) for m in messages],
            "options": {"temperature": temperature},
        }
        if tools:
            body["tools"] = tools

        start = time.perf_counter()
        attempt = 0
        while True:
            try:
                resp = await self._client.post("/api/chat", json=body)
                if 500 <= resp.status_code < 600:
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

        msg = data["message"]
        calls = [
            ToolCall(
                name=c["function"]["name"],
                arguments=c["function"].get("arguments", {}),
            )
            for c in (msg.get("tool_calls") or [])
        ]
        return ModelResponse(
            message=Message(
                role="assistant",
                content=msg.get("content", ""),
                tool_calls=calls,
            ),
            usage=Usage(
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            ),
            latency_s=latency,
        )
