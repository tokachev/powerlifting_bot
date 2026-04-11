"""LLM fallback parser: parse free-form text into a WorkoutPayload, and
canonicalize unknown exercise names via a small targeted prompt."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from pwrbot.domain.catalog import Catalog
from pwrbot.domain.models import WorkoutPayload
from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader


class CanonicalizeResult(BaseModel):
    """Public result of canonicalize(): either a confident pick, or up to 3
    suggestions when the LLM isn't sure. Never both populated."""

    canonical_name: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class _CanonResponse(BaseModel):
    """Raw LLM response shape — what the second prompt returns."""

    canonical_name: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class LLMParser:
    def __init__(
        self,
        client: OllamaClient,
        prompts: PromptLoader,
        catalog: Catalog,
    ) -> None:
        self._client = client
        self._prompts = prompts
        self._catalog = catalog

    async def parse_text(self, user_text: str) -> WorkoutPayload:
        schema_json = json.dumps(
            WorkoutPayload.model_json_schema(), ensure_ascii=False
        )
        now_iso = datetime.now(UTC).isoformat()
        tmpl = self._prompts.render(
            "parse_workout",
            schema_json=schema_json,
            user_text=user_text,
            now_iso=now_iso,
        )
        system, _, user = tmpl.partition("USER:")
        system = system.replace("SYSTEM:", "").strip()
        user = user.strip() or tmpl
        return await self._client.chat_json(
            system=system, user=user, schema_model=WorkoutPayload
        )

    async def canonicalize(self, raw_name: str) -> CanonicalizeResult:
        """Resolve a raw exercise name via LLM. Returns either a confident
        canonical name OR a list of up to 3 suggested catalog keys the user
        should pick from. Hallucinated keys (not in the catalog) are filtered out.
        """
        keys = "\n".join(f"- {k}" for k in self._catalog.canonical_names)
        tmpl = self._prompts.render(
            "canonicalize_exercise", raw_name=raw_name, catalog_keys=keys
        )
        system, _, user = tmpl.partition("USER:")
        system = system.replace("SYSTEM:", "").strip()
        user = user.strip() or tmpl
        resp = await self._client.chat_json(
            system=system, user=user, schema_model=_CanonResponse
        )

        valid_keys = set(self._catalog.canonical_names)
        canonical = resp.canonical_name if resp.canonical_name in valid_keys else None
        # Preserve LLM order, dedupe, filter to valid catalog keys, drop the canonical
        # pick from the suggestion list, cap at 3.
        seen: set[str] = set()
        suggestions: list[str] = []
        for s in resp.suggestions:
            if s in valid_keys and s not in seen and s != canonical:
                seen.add(s)
                suggestions.append(s)
            if len(suggestions) >= 3:
                break
        return CanonicalizeResult(canonical_name=canonical, suggestions=suggestions)

    async def explain(
        self, metrics: dict, flags: list, window_days: int
    ) -> str:
        """Free-form explanation. Not JSON — we return the raw string from /api/chat."""
        tmpl = self._prompts.render(
            "explain_findings",
            metrics_json=json.dumps(metrics, ensure_ascii=False),
            flags_json=json.dumps(flags, ensure_ascii=False),
            window_days=str(window_days),
        )
        system, _, user = tmpl.partition("USER:")
        system = system.replace("SYSTEM:", "").strip()
        user = user.strip() or tmpl
        # Plain-text call: we use httpx directly via the client's underlying session.
        resp = await self._client._client.post(
            f"{self._client._base_url}/api/chat",
            json={
                "model": self._client._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "").strip()
