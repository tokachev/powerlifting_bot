"""Client for host-side Codex app-server over WebSocket."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException


class CodexUnavailableError(Exception):
    """Codex app-server is unavailable or returned a protocol error."""


class CodexClient:
    def __init__(
        self,
        *,
        ws_url: str,
        token_file_path: str | Path,
        model: str,
    ) -> None:
        self._ws_url = ws_url
        self._model = model
        self._next_id = 1
        self._init_error: str | None = None
        try:
            self._token = Path(token_file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            self._token = None
            self._init_error = f"failed to read Codex token: {exc}"
            return
        if not self._token:
            self._token = None
            self._init_error = "Codex token file is empty"

    async def explain(self, system: str, user: str, *, timeout_s: float) -> str:
        """Run one isolated Codex turn and return final assistant text."""
        if self._init_error is not None:
            raise CodexUnavailableError(self._init_error)
        try:
            async with asyncio.timeout(timeout_s):
                return await self._explain(system=system, user=user, timeout_s=timeout_s)
        except CodexUnavailableError:
            raise
        except (TimeoutError, OSError, WebSocketException, json.JSONDecodeError) as exc:
            raise CodexUnavailableError(str(exc) or type(exc).__name__) from exc

    async def _explain(self, system: str, user: str, *, timeout_s: float) -> str:
        headers = [("Authorization", f"Bearer {self._token}")]
        async with connect(
            self._ws_url,
            additional_headers=headers,
            open_timeout=timeout_s,
            ping_interval=None,
            proxy=None,
        ) as ws:
            await self._request(
                ws,
                "initialize",
                {
                    "clientInfo": {
                        "name": "pwrbot",
                        "version": "0.1.0",
                    }
                },
            )
            await ws.send(json.dumps({"method": "initialized"}))

            thread_result = await self._request(
                ws,
                "thread/start",
                {
                    "model": self._model,
                    "cwd": "/tmp",
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "serviceName": "pwrbot",
                    "developerInstructions": system,
                },
            )
            thread_id = self._extract_id(thread_result, "thread", "threadId")

            await self._request(
                ws,
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": user}],
                },
            )

            chunks: list[str] = []
            while True:
                raw = await self._read_frame(ws)
                method = raw.get("method")
                if isinstance(method, str) and "id" in raw:
                    await self._reply_method_not_found(ws, raw)
                    continue
                if method == "item/completed":
                    self._collect_agent_message(raw.get("params"), chunks)
                    continue
                if method == "turn/completed":
                    self._raise_if_turn_failed(raw.get("params"))
                    return "\n\n".join(chunk for chunk in chunks if chunk).strip()
                if method == "error":
                    raise CodexUnavailableError(self._format_error(raw.get("params")))

    async def _request(self, ws: Any, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._allocate_id()
        await ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
        while True:
            raw = await self._read_frame(ws)
            raw_method = raw.get("method")
            if isinstance(raw_method, str) and "id" in raw:
                await self._reply_method_not_found(ws, raw)
                continue
            if raw_method == "error":
                raise CodexUnavailableError(self._format_error(raw.get("params")))
            if raw.get("id") != request_id:
                continue
            if raw.get("error"):
                raise CodexUnavailableError(self._format_error(raw["error"]))
            result = raw.get("result")
            if not isinstance(result, dict):
                raise CodexUnavailableError(
                    f"{method} response missing object result"
                )
            return result

    async def _read_frame(self, ws: Any) -> dict[str, Any]:
        frame = await ws.recv()
        if isinstance(frame, bytes):
            frame = frame.decode("utf-8")
        data = json.loads(frame)
        if not isinstance(data, dict):
            raise CodexUnavailableError("Codex frame is not a JSON object")
        return data

    async def _reply_method_not_found(self, ws: Any, raw: dict[str, Any]) -> None:
        method = raw.get("method")
        await ws.send(
            json.dumps(
                {
                    "id": raw["id"],
                    "error": {
                        "code": -32601,
                        "message": f"method not found: {method}",
                    },
                }
            )
        )

    def _allocate_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id

    def _extract_id(
        self,
        result: dict[str, Any],
        object_key: str,
        legacy_key: str,
    ) -> str:
        obj = result.get(object_key)
        if isinstance(obj, dict):
            value = obj.get("id")
            if isinstance(value, str) and value:
                return value
        value = result.get(legacy_key)
        if isinstance(value, str) and value:
            return value
        raise CodexUnavailableError(
            f"response missing {object_key}.id/{legacy_key}"
        )

    def _collect_agent_message(self, params: Any, chunks: list[str]) -> None:
        if not isinstance(params, dict):
            return
        item = params.get("item")
        if not isinstance(item, dict):
            return
        if item.get("type") != "agentMessage":
            return
        phase = item.get("phase")
        if phase not in (None, "final_answer"):
            return
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())

    def _raise_if_turn_failed(self, params: Any) -> None:
        if not isinstance(params, dict):
            return
        turn = params.get("turn")
        if not isinstance(turn, dict):
            return
        status = turn.get("status")
        if status in (None, "completed", "inProgress"):
            return
        error = turn.get("error")
        if isinstance(error, dict):
            message = error.get("message") or str(error)
        else:
            message = str(error or status)
        raise CodexUnavailableError(f"turn {status}: {message}")

    def _format_error(self, error: Any) -> str:
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
            return json.dumps(error, ensure_ascii=False)
        if isinstance(error, str):
            return error
        return repr(error)
