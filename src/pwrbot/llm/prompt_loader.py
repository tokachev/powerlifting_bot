"""Load prompt templates from prompts/*.md and substitute {placeholder} variables.

Uses regex-based substitution that only touches `{identifier}` patterns (word chars
only). This lets prompt files contain literal JSON examples like
`{"canonical_name": "bench_press"}` without breaking the loader — Python's
built-in `str.format_map` would otherwise interpret those as format specifiers
and blow up at runtime.
"""

from __future__ import annotations

import re
from pathlib import Path

# Matches {identifier} where identifier is a valid Python-style name.
# Intentionally does NOT match things like {"key": "value"} or {1,2}.
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class PromptLoader:
    def __init__(self, prompts_dir: Path) -> None:
        self._dir = prompts_dir
        self._cache: dict[str, str] = {}

    def _read(self, name: str) -> str:
        if name not in self._cache:
            self._cache[name] = (self._dir / f"{name}.md").read_text(encoding="utf-8")
        return self._cache[name]

    def render(self, name: str, /, **vars: str) -> str:
        """Render a template by name with the given variables.

        `name` is positional-only so it doesn't collide with a user-provided
        `name=...` variable in the template.
        """
        tmpl = self._read(name)

        def _sub(m: re.Match[str]) -> str:
            key = m.group(1)
            if key in vars:
                return vars[key]
            return m.group(0)  # leave unknown placeholders intact

        return _PLACEHOLDER.sub(_sub, tmpl)
