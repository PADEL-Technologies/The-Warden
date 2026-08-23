# AI harness

This repo carries a graphify knowledge graph (`graphify-out/`) and Serena
project memories (`.serena/memories/`) for AI coding assistants. `.graphifyignore`
keeps the graph scoped to `warden/` source only — no docs/config noise.

- `make update-harness` — refresh the graph (code-only, no viz) and clear
  Serena's stale symbol cache. Safe to run anytime.
- `make install-hooks` — opt in to two git hooks:
  - `pre-commit` keeps `graphify-out/` out of code commits (unstages it when
    mixed with other paths).
  - `post-commit` does the same refresh automatically after each commit. It only
    runs when the commit touched `*.py`, and always lands the refreshed graph as
    its own separate commit (`chore(graphify): refresh graph`) on top of your
    code commit — all graphify changes, never mixed in.
