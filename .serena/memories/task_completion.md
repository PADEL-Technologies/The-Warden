# Task Completion Checklist

Run before considering any code change done (mirrors CI exactly):
```
uv run ruff check .
uv run ruff format .
uv run pytest
```
All three must pass with no errors/failures. `tests/` is declared as
`testpaths` in `pyproject.toml` but may not exist yet for every feature —
check before assuming test coverage exists.
