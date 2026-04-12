from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field

from pwrbot.llm.ollama_client import LLMParseError, OllamaClient


class _DummyModel(BaseModel):
    name: str
    n: int = Field(ge=0)


def _ollama_reply(content: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}}


async def test_chat_json_happy_path() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode()))
        return httpx.Response(200, json=_ollama_reply('{"name": "x", "n": 3}'))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma3:4b", client=http, max_retries=1
        )
        result = await client.chat_json(
            system="sys", user="usr", schema_model=_DummyModel
        )
    assert result == _DummyModel(name="x", n=3)
    assert len(calls) == 1
    # schema was passed as `format`
    assert "properties" in calls[0]["format"]
    assert calls[0]["options"]["temperature"] == 0.0


async def test_chat_json_retries_on_invalid_then_succeeds() -> None:
    responses = [
        _ollama_reply("not json at all"),
        _ollama_reply('{"name": "ok", "n": 1}'),
    ]
    idx = {"i": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        r = responses[idx["i"]]
        idx["i"] += 1
        return httpx.Response(200, json=r)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma3:4b", client=http, max_retries=1
        )
        result = await client.chat_json(
            system="sys", user="usr", schema_model=_DummyModel
        )
    assert result.name == "ok"
    assert idx["i"] == 2


async def test_chat_json_raises_after_two_failures() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ollama_reply("still broken"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma3:4b", client=http, max_retries=1
        )
        with pytest.raises(LLMParseError):
            await client.chat_json(
                system="sys", user="usr", schema_model=_DummyModel
            )


async def test_chat_json_schema_validation_retry() -> None:
    # first response parses as JSON but fails pydantic validation (n < 0)
    responses = [
        _ollama_reply('{"name": "x", "n": -1}'),
        _ollama_reply('{"name": "x", "n": 2}'),
    ]
    idx = {"i": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        r = responses[idx["i"]]
        idx["i"] += 1
        return httpx.Response(200, json=r)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma3:4b", client=http, max_retries=1
        )
        result = await client.chat_json(
            system="sys", user="usr", schema_model=_DummyModel
        )
    assert result.n == 2


# ── chat_vision_json ──────────────────────────────────────────────


async def test_chat_vision_json_happy_path() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode()))
        return httpx.Response(200, json=_ollama_reply('{"name": "squat", "n": 5}'))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma4:e4b", client=http, max_retries=1
        )
        result = await client.chat_vision_json(
            system="sys",
            user="usr",
            images=["AAAA", "BBBB"],
            schema_model=_DummyModel,
        )
    assert result == _DummyModel(name="squat", n=5)
    assert len(calls) == 1
    # Images in user message
    assert calls[0]["messages"][1]["images"] == ["AAAA", "BBBB"]
    # JSON schema as format
    assert "properties" in calls[0]["format"]


async def test_chat_vision_json_retries_on_invalid() -> None:
    responses = [
        _ollama_reply("not json"),
        _ollama_reply('{"name": "ok", "n": 1}'),
    ]
    idx = {"i": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        r = responses[idx["i"]]
        idx["i"] += 1
        return httpx.Response(200, json=r)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma4:e4b", client=http, max_retries=1
        )
        result = await client.chat_vision_json(
            system="sys",
            user="usr",
            images=["img"],
            schema_model=_DummyModel,
        )
    assert result.name == "ok"
    assert idx["i"] == 2


async def test_chat_vision_json_model_override() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content.decode()))
        return httpx.Response(200, json=_ollama_reply('{"name": "x", "n": 0}'))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma4:e4b", client=http
        )
        await client.chat_vision_json(
            system="sys",
            user="usr",
            images=["img"],
            schema_model=_DummyModel,
            model_override="llava:13b",
        )
    assert calls[0]["model"] == "llava:13b"


async def test_chat_vision_json_raises_after_failures() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ollama_reply("broken"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = OllamaClient(
            base_url="http://fake", model="gemma4:e4b", client=http, max_retries=1
        )
        with pytest.raises(LLMParseError):
            await client.chat_vision_json(
                system="sys",
                user="usr",
                images=["img"],
                schema_model=_DummyModel,
            )
