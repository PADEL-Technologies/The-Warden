# Core

Discord bot, single package `warden/`. Entry point: `main.py` (reads
`DISCORD_TOKEN` from env, no config module — see `ponytail` comment there).

## Source map
- `warden/bot.py` — `Warden(commands.Bot)`, loads every feature package via
  `feature_modules()` (introspects `warden/features/` with `pkgutil`, no
  manual registry) and calls `tree.sync()` in `setup_hook`.
- `warden/features/<name>/` — one feature per folder, see `mem:conventions`
  for the mandatory internal layout.
- `.serena/`, `.claude/`, `graphify-out/` — AI tooling, not app code.
  `graphify-out/` is the committed knowledge-graph output of the graphify
  skill (see `.graphifyignore` for what's excluded from it — non-code files
  only, keep it code-scoped).

For tech stack/versions: `mem:tech_stack`.
For dev/test/lint commands (Windows-specific forms noted): `mem:suggested_commands`.
For code style and the feature-folder pattern: `mem:conventions`.
For what "done" means on a task: `mem:task_completion`.
