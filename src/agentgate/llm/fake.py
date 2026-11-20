from .types import Message, ModelResponse


class FakeModel:
    def __init__(self, script: list[Message]):
        self.name = "fake"
        self._script = list(script)
        self.calls: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> ModelResponse:
        self.calls.append(list(messages))
        if not self._script:
            raise RuntimeError("FakeModel script exhausted")
        return ModelResponse(message=self._script.pop(0))
