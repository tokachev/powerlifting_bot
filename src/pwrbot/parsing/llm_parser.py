"""LLM fallback parser: parse free-form text into a WorkoutPayload, and
canonicalize unknown exercise names via a small targeted prompt."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from pwrbot.domain.catalog import Catalog, normalize
from pwrbot.domain.models import WorkoutPayload
from pwrbot.llm.ollama_client import OllamaClient
from pwrbot.llm.prompt_loader import PromptLoader

# RU-root → muscle_group. Order matters: first substring match wins, so more
# specific roots (трицепс) come before shorter ones (трис) would — here all
# roots are distinct enough that order is stable.
_MUSCLE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("трицепс", "arms"),
    ("трис", "arms"),
    ("бицепс", "arms"),
    ("широч", "back"),
    ("спин", "back"),
    ("груд", "chest"),
    ("дельт", "shoulders"),
    ("плеч", "shoulders"),
    ("квадр", "legs"),
    ("ягодиц", "legs"),
    ("голен", "legs"),
    ("бедр", "legs"),
    ("пресс", "core"),
    ("кор", "core"),
)


def _detect_muscle_group(raw_name: str) -> str | None:
    """Return the muscle_group hinted by RU roots in raw_name, or None."""
    norm = normalize(raw_name)
    if not norm:
        return None
    for root, mg in _MUSCLE_KEYWORDS:
        if root in norm:
            return mg
    return None


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
        key_lines: list[str] = []
        for e in self._catalog.entries:
            mg = e.muscle_group or "?"
            key_lines.append(f"- {e.canonical_name} (muscle: {mg}, pattern: {e.movement_pattern})")
        keys = "\n".join(key_lines)
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

        # Safety net: if the raw input has a clear RU muscle-group cue, drop
        # anything from a different muscle_group (LLM sometimes picks by
        # equipment token "канат" → cable_row even though cable_row is back,
        # not a triceps move).
        # - canonical: always demote on mismatch — a confident wrong pick
        #   would be written straight to the payload without asking.
        # - suggestions: filter to matching muscle_group; if that wipes all
        #   of them, keep the unfiltered list (bad suggestions beat none —
        #   the user still gets a chance to skip).
        detected = _detect_muscle_group(raw_name)
        if detected is not None:
            def _matches(key: str) -> bool:
                entry = self._catalog.by_canonical(key)
                return entry is not None and entry.muscle_group == detected

            if canonical is not None and not _matches(canonical):
                canonical = None
            filtered_suggestions = [s for s in suggestions if _matches(s)]
            if filtered_suggestions:
                suggestions = filtered_suggestions
            # else: fall through with unfiltered suggestions

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
