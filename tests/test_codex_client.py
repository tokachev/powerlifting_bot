from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from websockets.asyncio.server import serve

from pwrbot.llm.codex_client import CodexClient, CodexUnavailableError


async def test_codex_client_explain_happy_path(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret-token", encoding="utf-8")
    requests: list[dict[str, Any]] = []
    auth_headers: list[str | None] = []

    async def handler(ws) -> None:
        auth_headers.append(ws.request.headers.get("Authorization"))
        async for message in ws:
            request = json.loads(message)
            requests.append(request)
            method = request.get("method")
            if method == "initialize":
                await ws.send(json.dumps({"id": request["id"], "result": {}}))
            elif method == "initialized":
                continue
            elif method == "thread/start":
                await ws.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"thread": {"id": "thread-1"}},
                        }
                    )
                )
            elif method == "turn/start":
                await ws.send(
                    json.dumps(
                        {
                            "id": request["id"],
                            "result": {"turn": {"id": "turn-1", "status": "inProgress"}},
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "method": "item/completed",
                            "params": {
                                "item": {
                                    "type": "agentMessage",
                                    "phase": "analysis",
                                    "text": "ignore me",
                                }
                            },
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "method": "item/completed",
                            "params": {
                                "item": {
                                    "type": "agentMessage",
                                    "phase": "final_answer",
                                    "text": "codex final",
                                }
                            },
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "method": "turn/completed",
                            "params": {
                                "turn": {"id": "turn-1", "status": "completed"}
                            },
                        }
                    )
                )

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = CodexClient(
            ws_url=f"ws://127.0.0.1:{port}",
            token_file_path=token_file,
            model="gpt-5-codex",
        )
        text = await client.explain("system", "user", timeout_s=1)

    assert text == "codex final"
    assert auth_headers == ["Bearer secret-token"]
    thread_start = next(r for r in requests if r.get("method") == "thread/start")
    assert thread_start["params"] == {
        "model": "gpt-5-codex",
        "cwd": "/tmp",
        "approvalPolicy": "never",
        "sandbox": "read-only",
        "serviceName": "pwrbot",
        "developerInstructions": "system",
    }
    turn_start = next(r for r in requests if r.get("method") == "turn/start")
    assert turn_start["params"] == {
        "threadId": "thread-1",
        "input": [{"type": "text", "text": "user"}],
    }


async def test_codex_client_timeout(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret-token", encoding="utf-8")

    async def handler(ws) -> None:
        await asyncio.sleep(1)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = CodexClient(
            ws_url=f"ws://127.0.0.1:{port}",
            token_file_path=token_file,
            model="gpt-5-codex",
        )
        with pytest.raises(CodexUnavailableError):
            await client.explain("system", "user", timeout_s=0.05)


async def test_codex_client_connection_refused(tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret-token", encoding="utf-8")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    client = CodexClient(
        ws_url=f"ws://127.0.0.1:{port}",
        token_file_path=token_file,
        model="gpt-5-codex",
    )
    with pytest.raises(CodexUnavailableError):
        await client.explain("system", "user", timeout_s=0.2)


async def test_codex_client_missing_token_file_reports_unavailable(tmp_path: Path) -> None:
    client = CodexClient(
        ws_url="ws://127.0.0.1:1",
        token_file_path=tmp_path / "missing-token",
        model="gpt-5-codex",
    )
    with pytest.raises(CodexUnavailableError, match="failed to read Codex token"):
        await client.explain("system", "user", timeout_s=0.2)
