FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user (fixed UID for predictable bind-mount ownership)
RUN useradd --create-home --uid 1000 --shell /bin/bash pwrbot

WORKDIR /app

# Install deps first — maximises layer caching when only src changes
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config/ ./config/
COPY prompts/ ./prompts/

RUN pip install --no-cache-dir -e . \
    && mkdir -p /app/data \
    && chown -R pwrbot:pwrbot /app

USER pwrbot

# Declared so running the image without compose still gets a persistent anon volume.
# docker-compose overrides this with a bind-mount.
VOLUME ["/app/data"]

# Cheap liveness check — verifies the package is importable inside the running container.
# aiogram long-polling has no HTTP surface, so no network check is possible.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import pwrbot" || exit 1

CMD ["python", "-m", "pwrbot"]
