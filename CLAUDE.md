# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

pwrbot — single-user Telegram training diary bot. Parses Russian free-text workout logs, persists to SQLite, runs a deterministic rules engine (volume/balance/recovery flags), and uses local Ollama (Gemma 4) only as fallback for parsing, exercise canonicalization, and natural-language explanations. No cloud LLM APIs.

There's also a React dashboard (FastAPI backend + Vite/React frontend) served on :8000.

## Commands

```bash
# Setup
pip install -e '.[dev]'

# Run all tests
pytest

# Run single test file / single test
pytest tests/test_regex_parser.py
pytest tests/test_regex_parser.py::test_nrw_basic -v

# Lint
ruff check src/ tests/
ruff check --fix src/ tests/

# Run bot
python -m pwrbot

# Run dashboard API (FastAPI)
python -m pwrbot.api

# Dashboard frontend dev
cd dashboard && npm run dev

# Docker (bot only needs host Ollama running)
docker compose up -d --build
```

## Architecture

### Data flow: user message → response

```
Telegram message
  → ParsingPipeline (parsing/pipeline.py)
      1. preprocess: extract header-date, group lines into LogicalBlocks
      2. regex_parser: deterministic pattern matching (6 ordered patterns)
      3. LLM fallback: Ollama chat_json with pydantic schema as format constraint
      4. normalize: catalog resolution + warmup-by-weight rule
      5. LLM canonicalize: for names not in catalog
  → IngestService (services/ingest.py)
      - if unresolved exercises → PendingClarification (FSM state, user picks)
      - else → persist to SQLite + auto-run 7-day analysis
  → AnalyzeService (services/analyze.py)
      - loads 28d history, runs rules engine, LLM explains findings
  → formatted Telegram reply
```

### Key design decisions

- **Weight storage**: grams (int) at the DB/repo boundary, kg (float) in domain models. Conversion in `parsing/normalize.py:kg_to_g`.
- **Timestamps**: unix seconds (int) everywhere in DB. `performed_at` can be overridden by a date-header in user message text.
- **Warmup detection**: weight-based rule is the single source of truth (`normalize.py:apply_warmup_by_weight`). LLM/regex `is_warmup` flags are overwritten for weighted sets. Only bodyweight sets (weight=0) preserve the original flag.
- **Hard set classification**: RPE >= 7.0 when available; else intensity >= 75% of rolling-best weight over 28d; else all working sets count as hard.
- **Regex pattern order matters**: `_PATTERN_BUILDERS` list in `regex_parser.py` — `RE_N_STAR_R` must be last to avoid eating weights from `3x8 80` patterns.

### Layers

| Layer | Path | Notes |
|-------|------|-------|
| Bot handlers | `bot/handlers/` | aiogram 3 routers, FSM for clarification flow |
| Parsing | `parsing/` | regex_parser, preprocess (LogicalBlocks), llm_parser, normalize, pipeline |
| Domain | `domain/` | pydantic models (WorkoutPayload is also the LLM output schema), exercise Catalog |
| Rules engine | `rules/` | volume, balance, flags — pure functions, no I/O |
| Services | `services/` | ingest (parse→persist→analyze), analyze, reporting (dashboard aggregations) |
| DB | `db/` | aiosqlite, repo.py (CRUD), schema.sql |
| LLM | `llm/` | OllamaClient (httpx, retry-once), PromptLoader, LLMParser |
| API | `api/` | FastAPI dashboard backend, serves React SPA from `dashboard/dist` |
| Config | `config.py` | env via pydantic-settings (Settings), YAML via pydantic (YamlConfig) |

### Config system

- **Env vars** (`.env`): `TELEGRAM_TOKEN`, `OLLAMA_URL`, `DB_PATH`, etc. — loaded into `Settings` (pydantic-settings).
- **`config/settings.yaml`**: analysis windows, thresholds, LLM model. Loaded into frozen `YamlConfig`.
- **`config/exercises.yaml`**: exercise catalog. Keys = `canonical_name` (snake_case English). Aliases are Russian free-text variants. `movement_pattern` is required, `target_group`/`muscle_group` optional.

### Test conventions

- In-memory SQLite via `conftest.py:conn` fixture (async, schema bootstrapped).
- Ollama is never called in tests — LLM parser is mocked or set to None.
- `asyncio_mode = "auto"` — all async test functions run without explicit marks.
- `REPO_ROOT = Path(__file__).resolve().parent.parent` available in conftest for loading real config files.

### Dashboard

- Backend: FastAPI app in `api/main.py`, reads same SQLite DB in autocommit/read-only mode.
- Frontend: React + TypeScript + Vite + Tailwind + Recharts in `dashboard/`.
- Aggregation logic in `services/reporting.py` — KPSh (total reps), intensity, per-muscle/pattern breakdowns.
- CORS allows localhost:5173 (Vite dev) and connects to API at :8000.
