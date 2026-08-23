# Docker

```bash
make docker-build
make docker-run   # reads DISCORD_TOKEN from .env
```

Multi-stage build (`Dockerfile`): dependencies are installed in a `builder`
stage, the runtime stage copies only the built venv, `warden/` and `main.py`
— no `uv`, no build tools, no audio/voice libs in the final image. Runs
headless as a non-root user, timezone pinned to `Asia/Jakarta`. The image
does not carry `migrations/` — migrations are applied by a separate process
before the bot starts.
