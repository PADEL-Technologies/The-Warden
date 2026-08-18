# Suggested Commands

Run (bash/git-bash on Windows, matches CI):
```
uv sync
DISCORD_TOKEN=... uv run main.py
```

Checks (exact sequence CI runs, run all three before considering work done):
```
uv run ruff check .
uv run ruff format . && uv run ruff format --check .   # CI only runs --check
uv run pytest
```

Windows notes:
- This repo is developed in Git Bash per the session shell — standard unix
  command forms work (not cmd.exe/PowerShell syntax).
- `.venv/Scripts/` (not `.venv/bin/`) holds the venv executables, but `uv run`
  abstracts over this — prefer `uv run <cmd>` over invoking `.venv` directly.
