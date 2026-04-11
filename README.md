# pwrbot — Local Telegram Training Diary Bot

Локальный single-user Telegram-бот для дневника тренировок. Детерминированный rules-engine делает анализ, локальная Gemma через Ollama используется только для:
1. парсинга свободного текста в структурированный JSON;
2. канонизации неизвестных имён упражнений;
3. коротких объяснений результатов анализа.

Никакого Anthropic API, облаков, SaaS и RAG.

## Стек
- Python 3.11+
- aiogram 3.x
- SQLite через aiosqlite
- Ollama (локально) + `gemma4:e4b`
- pydantic v2, httpx, structlog

## Быстрый старт

```bash
# 1. Ollama и модель
ollama pull gemma4:e4b
ollama serve &  # или запусти Ollama.app

# 2. Зависимости
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# 3. Конфиг
cp .env.example .env
# Заполни TELEGRAM_TOKEN

# 4. БД
python scripts/init_db.py

# 5. Тесты
pytest -q

# 6. Запуск
python -m pwrbot
```

## Run in Docker

Контейнеризирован только бот. Ollama остаётся на хосте — Metal/CUDA ускорение в контейнере под Docker Desktop недоступно, а модель уже хранится у пользователя.

**Пререквизиты:**
- Ollama запущена на хосте и доступна по `http://localhost:11434`
- `gemma4:e4b` уже pulled (`ollama pull gemma4:e4b`)
- На Linux Ollama должна слушать внешний интерфейс: `OLLAMA_HOST=0.0.0.0 ollama serve` (на macOS Docker Desktop не требуется)

**Запуск:**

```bash
cp .env.example .env
# Заполни TELEGRAM_TOKEN
mkdir -p data
docker compose up -d --build
docker compose logs -f pwrbot
```

`./data/pwrbot.db` создаётся при первом старте и переживает рестарты контейнера.

**Проверка что контейнер видит Ollama на хосте:**

```bash
docker compose exec pwrbot python -c \
  "import httpx; print(httpx.get('http://host.docker.internal:11434/api/tags').json())"
```

Должен вернуться JSON со списком моделей, где есть `gemma4:e4b`.

**Остановка:** `docker compose down`. БД остаётся в `./data/`.

## Команды бота

| Команда | Что делает |
|---|---|
| `/start` | Регистрирует пользователя |
| `/help` | Список команд |
| `/log <текст>` | Залогировать тренировку (можно просто отправить текст без команды) |
| `/today` | Тренировки за сегодня |
| `/lastworkout` | Последняя тренировка |
| `/week` | Сводка за 7 дней |
| `/analyze [7\|28]` | Полный анализ за окно (по умолчанию 7) |
| `/delete_last` | Удалить последнюю тренировку |
| `/edit_last <текст>` | Заменить последнюю тренировку |

После каждого успешного `/log` бот автоматически прогоняет 7-дневный анализ и возвращает сводку плюс findings одним сообщением.

## Формат ввода

Регекспы справляются с типичными форматами:
- `присед 4x5x100 rpe8`
- `жим лёжа 5 подходов по 8 80кг`
- `становая 3×3×140, разминка 60×10`
- несколько упражнений через запятую или перенос строки

Если регекспы не распознают строку, она уходит в LLM fallback с строгой JSON-схемой.

## Конфиг

- `config/settings.yaml` — окна анализа и все пороги правил. Меняй без перезапуска кода (только рестарт бота).
- `config/exercises.yaml` — каталог упражнений с алиасами и movement_pattern.
- `prompts/*.md` — LLM-промпты, каждый в отдельном файле.

## Проверка после запуска

1. `/start` — должен поприветствовать.
2. Отправь `присед 5x5x100` — вернёт распарсенную сводку + 7-дневный мини-анализ.
3. `/lastworkout` — покажет только что записанную тренировку.
4. `/analyze 28` — полный анализ за 28 дней.
5. `/delete_last` — удалит последнюю тренировку.

## Структура

```
src/pwrbot/
  bot/          aiogram handlers + middleware
  db/           schema.sql, aiosqlite connection, repo
  domain/       pydantic models, exercise catalog loader
  parsing/      regex first, LLM fallback, normalize
  llm/          Ollama httpx client, prompt loader
  rules/        volume/balance/flags + engine
  services/     ingest (parse→persist→analyze) + analyze
config/         settings.yaml, exercises.yaml
prompts/        parse_workout.md, canonicalize_exercise.md, explain_findings.md
tests/          pytest, in-memory sqlite, mocked Ollama
```
