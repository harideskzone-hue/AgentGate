import httpx
import pytest

from agentgate.llm.cache import CacheMiss, CachingAdapter, cache_key
from agentgate.llm.fake import FakeModel
from agentgate.llm.hosted import HostedOpenAIAdapter
from agentgate.llm.ollama import OllamaAdapter
from agentgate.llm.types import Message

MSGS = [Message(role="user", content="hello")]


def test_cache_key_stable_and_sensitive():
    a = cache_key("m", MSGS, None, 0.0, "")
    assert a == cache_key("m", MSGS, None, 0.0, "")
    assert a != cache_key("m", MSGS, None, 0.7, "")
    assert a != cache_key("m", MSGS, None, 0.0, "repeat-2")
    assert a != cache_key("other", MSGS, None, 0.0, "")


async def test_record_then_replay(tmp_path):
    fake = FakeModel([Message(role="assistant", content="hi")])
    rec = CachingAdapter(fake, tmp_path, mode="record")
    first = await rec.complete(MSGS)
    assert first.cached is False

    rep = CachingAdapter(FakeModel([]), tmp_path, mode="replay")
    second = await rep.complete(MSGS)
    assert second.cached is True
    assert second.message.content == "hi"


async def test_replay_miss_raises(tmp_path):
    rep = CachingAdapter(FakeModel([]), tmp_path, mode="replay")
    with pytest.raises(CacheMiss):
        await rep.complete(MSGS)


async def test_ollama_parses_tool_calls():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "lookup", "arguments": {"id": 42}}}
                    ],
                },
                "prompt_eval_count": 10,
                "eval_count": 5,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://x"
    )
    adapter = OllamaAdapter("m", client=client)
    resp = await adapter.complete(MSGS)
    assert resp.message.tool_calls[0].name == "lookup"
    assert resp.message.tool_calls[0].arguments == {"id": 42}
    assert resp.usage.input_tokens == 10 and resp.usage.output_tokens == 5


async def test_ollama_retries_on_5xx_and_succeeds():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={"error": "service unavailable"})
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "recovered"},
                "prompt_eval_count": 8,
                "eval_count": 4,
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://x"
    )
    adapter = OllamaAdapter(
        "m", client=client, max_retries=3, backoff_factor=0.01
    )
    resp = await adapter.complete(MSGS)
    assert resp.message.content == "recovered"
    assert attempts == 3


async def test_ollama_no_retry_on_4xx():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"error": "bad request"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://x"
    )
    adapter = OllamaAdapter(
        "m", client=client, max_retries=3, backoff_factor=0.01
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await adapter.complete(MSGS)
    assert exc_info.value.response.status_code == 400
    assert attempts == 1


async def test_hosted_openai_adapter_tool_calls_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "calling tool",
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"query": "antigravity"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 7},
            },
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.openai.com/v1"
    )
    adapter = HostedOpenAIAdapter("gpt-4o-mini", api_key="test-key", client=client)
    resp = await adapter.complete(MSGS)
    assert resp.message.content == "calling tool"
    assert len(resp.message.tool_calls) == 1
    assert resp.message.tool_calls[0].name == "search"
    assert resp.message.tool_calls[0].arguments == {"query": "antigravity"}
    assert resp.usage.input_tokens == 15
    assert resp.usage.output_tokens == 7


async def test_hosted_openai_no_retry_on_400():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"error": {"message": "Invalid model"}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.openai.com/v1"
    )
    adapter = HostedOpenAIAdapter("test", api_key="key", client=client, max_retries=3, backoff_factor=0.01)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await adapter.complete(MSGS)
    assert exc_info.value.response.status_code == 400
    assert attempts == 1
