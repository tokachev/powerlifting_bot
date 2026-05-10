# Codex App-Server Setup

Codex is optional. With `CODEX_ENABLED=false`, pwrbot uses local Gemma only.

1. Make sure the host Codex CLI is logged in:

   ```bash
   codex login
   ```

2. Create or choose a WebSocket token file on the host:

   ```bash
   mkdir -p ~/.codex
   openssl rand -hex 32 > ~/.codex/codex-app-server-token
   chmod 600 ~/.codex/codex-app-server-token
   ```

3. Enable Codex in `.env`:

   ```env
   CODEX_ENABLED=true
   CODEX_TOKEN_FILE=/run/secrets/codex-app-server-token
   ```

   In Docker, `docker-compose.yml` sets `CODEX_WS_URL=ws://codex-app-server:4500`
   for the bot container.

4. Start the Dockerized app-server:

   ```bash
   docker compose --profile codex up -d --build codex-app-server
   ```

5. Check readiness from the host:

   ```bash
   curl -fsS http://127.0.0.1:4501/readyz
   ```

6. Start or recreate the bot:

   ```bash
   docker compose up -d --build pwrbot
   ```

Docker Compose mounts the host `~/.codex` directory into the Codex container so
the app-server can use the same ChatGPT-account auth as the host CLI. The bot
container still mounts only `~/.codex/codex-app-server-token` at
`/run/secrets/codex-app-server-token` to authenticate to the app-server.

The Codex container listens on port `4500` inside Docker. It is published as
`127.0.0.1:4501` on the host to avoid conflicting with a manually started
host-side `codex app-server` on `4500`.

If you run pwrbot directly on the host instead of Docker, set:

```env
CODEX_WS_URL=ws://host.docker.internal:4500
```
