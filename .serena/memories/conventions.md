# Conventions

## Feature-folder pattern (mandatory for any new feature)
One feature = one folder under `warden/features/`, e.g. `ping/`:
```
warden/features/<name>/
    __init__.py                    wiring only: setup(bot) builds deps, adds the cog
    handlers/<name>_handler.py     the Cog — Discord in, Discord out, no business logic
    services/protocol.py           Protocol the handler depends on (typed interface)
    services/<name>_service.py     concrete implementation of the protocol
```
- The folder is auto-discovered by `feature_modules()` in `warden/bot.py`
  (via `pkgutil.iter_modules`) — there is no registry to edit. The only
  hard requirement is an `async def setup(bot)` in the feature's
  `__init__.py` that does `await bot.add_cog(...)`.
- Handlers take services as constructor args, typed against the `Protocol`
  in `services/protocol.py` — keeps the service unit-testable without
  booting a bot. Service classes do NOT inherit the Protocol; they just
  structurally match it (duck typing via `typing.Protocol`).
- Slash/hybrid commands: use `@commands.hybrid_command()`, not
  `@commands.command()` (the ping feature was migrated from the latter).

## Style
- `# ponytail: <reason>` comments mark deliberate simplifications with a
  named ceiling (e.g. "token read straight from env, add config module at
  3+ settings") — read these before "fixing" what looks like missing
  abstraction; they're intentional and name the upgrade trigger.
- Full type hints on all public functions/methods (params + return).
- No docstrings except where genuinely non-obvious (e.g.
  `feature_modules()` has one explaining the auto-discovery contract).
