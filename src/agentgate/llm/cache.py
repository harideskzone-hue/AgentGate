import hashlib
import json
from pathlib import Path
from typing import Literal

from .types import Message, ModelAdapter, ModelResponse


class CacheMiss(Exception):
    pass


def cache_key(
    model: str,
    messages: list[Message],
    tools: list[dict] | None,
    temperature: float,
    salt: str,
) -> str:
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "tools": tools,
        "temperature": temperature,
        "salt": salt,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class CachingAdapter:
    def __init__(
        self,
        inner: ModelAdapter,
        directory: str | Path,
        mode: Literal["live", "record", "replay"] = "record",
        salt: str = "",
    ):
        self.inner = inner
        self.name = inner.name
        self.mode = mode
        self.salt = salt
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        key = cache_key(self.inner.name, messages, tools, temperature, self.salt)
        path = self.dir / f"{key}.json"
        if self.mode != "live" and path.exists():
            return ModelResponse.model_validate_json(
                path.read_text()
            ).model_copy(update={"cached": True})
        if self.mode == "replay":
            raise CacheMiss(key)
        resp = await self.inner.complete(messages, tools, temperature)
        if self.mode == "record":
            path.write_text(resp.model_dump_json())
        return resp
