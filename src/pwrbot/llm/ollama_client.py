"""Minimal Ollama httpx client with JSON-mode structured output and retry-once logic.

Uses Ollama's `/api/chat` endpoint with the `format` parameter set to a JSON Schema.
Gemma3 models support this. On malformed JSON or pydantic validation failure we retry
once with an error-context appended to the prompt. A second failure raises LLMParseError.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from pwrbot.logging_setup import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base for LLM-related failures."""


class LLMParseError(LLMError):
    """Two attempts failed to produce schema-valid JSON."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: int = 60,
        max_retries: int = 1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat_json(
        self,
        *,
        system: str,
        user: str,
        schema_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Call /api/chat with `format=<schema>` and validate the response against schema_model.

        On ValidationError or JSON decode failure, retry up to self._max_retries times,
        appending the previous raw output and error to the user message.
        """
        schema = schema_model.model_json_schema()
        last_error: str | None = None
        last_raw: str | None = None

        for attempt in range(self._max_retries + 1):
            user_msg = user
            if last_error is not None:
                user_msg = (
                    f"{user}\n\n"
                    f"Предыдущий ответ был невалидным: {last_error}\n"
                    f"Предыдущий raw-вывод: {last_raw}\n"
                    f"Верни корректный JSON по схеме."
                )

            payload: dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "format": schema,
                "stream": False,
                "options": {"temperature": temperature},
            }

            log.debug(
                "ollama_chat_request",
                model=self._model,
                attempt=attempt,
                schema_title=schema.get("title", ""),
            )
            resp = await self._client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            raw = resp.json().get("message", {}).get("content", "")
            last_raw = raw

            try:
                data = json.loads(raw)
                return schema_model.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                log.warning(
                    "ollama_parse_failed",
                    attempt=attempt,
                    error=last_error,
                    raw_preview=raw[:200],
                )
                continue

        raise LLMParseError(
            f"LLM failed to return valid {schema_model.__name__} JSON after "
            f"{self._max_retries + 1} attempts. Last error: {last_error}"
        )

    async def chat_vision(
        self,
        *,
        system: str,
        user: str,
        images: list[str],
        temperature: float = 0.2,
        model_override: str | None = None,
    ) -> str:
        """Call /api/chat with base64-encoded images and return free-text response.

        Images are passed in the user message via the Ollama ``images`` field.
        """
        model = model_override or self._model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user, "images": images},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        log.debug("ollama_vision_request", model=model, n_images=len(images))
        resp = await self._client.post(
            f"{self._base_url}/api/chat", json=payload
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
