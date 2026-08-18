# Tech Stack

- Python >=3.14 (pinned via `.python-version`), package manager `uv`.
- `discord.py` (`discord-py>=2.7.1`) — commands use the hybrid-command
  pattern (`@commands.hybrid_command()`), not the plain `@commands.command()`.
- Dev deps (uv dependency-group `dev`): `pytest>=8`, `ruff>=0.9`.
- No build-system in `pyproject.toml` — app is never packaged (explicit
  `ponytail` comment in `pyproject.toml`), run directly via `uv run main.py`.
- ruff lint selects: `E, F, I, UP, B`.
- CI (`.github/workflows/ci.yml`, ubuntu-latest): `uv sync` → `ruff check .`
  → `ruff format --check .` → `pytest`, on every push/PR.
