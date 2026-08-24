# Configuration

Everything comes from environment variables (or `.env` for `make docker-run`).
There is no `guild_settings` table: one bot instance per community, and env vars
mean the "not configured yet" branch never has to exist. `guild_id` is still stored
on every row, so the multi-guild door stays open.

| Variable               | Default      | Purpose                                                |
| ---------------------- | ------------ | ------------------------------------------------------ |
| `DISCORD_TOKEN`        | — (required) | Bot token                                              |
| `DATABASE_URL`         | — (required) | Postgres DSN, e.g. `postgres://user:pass@host:5432/db` |
| `ONBOARDING_ENABLED`   | `true`       | Load the onboarding feature at all                     |
| `REGISTRATION_ENABLED` | `true`       | Load the registration feature at all                   |
| `LOG_LEVEL`            | `INFO`       | Root log level for `warden.*` — see [Logging](#logging) |

Flags read as true for `1`, `true`, `yes` (case-insensitive).

`.env.example` carries every variable with dummy values — copy it to `.env`.

## Registration

When `REGISTRATION_ENABLED` is true these are **required**. They are read with
`os.environ[...]`, so a missing one fails at startup rather than going quiet when
the first person clicks a button (`warden/config.py`).

| Variable                         | Purpose                                                         |
| -------------------------------- | --------------------------------------------------------------- |
| `REGISTRATION_LOCKET_CHANNEL_ID` | Public channel holding the *Onboard Me* message                  |
| `REGISTRATION_REPORT_CHANNEL_ID` | Where review cards are posted                                    |
| `REGISTRATION_VERIFIER_ROLE_ID`  | Role allowed to approve/reject                                   |
| `REGISTRATION_MAHASISWA_ROLE_ID` | Granted on approval, type `mahasiswa`                            |
| `REGISTRATION_ALUMNI_ROLE_ID`    | Granted on approval, type `alumni`                               |
| `REGISTRATION_PRODI_ROLES`       | `d3-ti:333,d3-tk:444` — the keys are the prodi options in the form |

`REGISTRATION_PRODI_ROLES` is a `key:role_id` list, not JSON — quoting and escaping
JSON in `.env`/`docker-compose.yml` costs more than it buys. Roles are matched by
**id, not name**: role names get renamed and a name-based mapping would stop working
without a single error.

The keys are what the form offers and what lands in `registrations.prodi`, so they
are also the nickname prefix (upper-cased). A prodi key that is missing from the
mapping at approval time **fails the approve** with an explicit ephemeral rather
than silently granting only the mahasiswa role.

## Server permissions this assumes

| Who                    | Permission                                            |
| ---------------------- | ----------------------------------------------------- |
| Bot                    | `Manage Threads`, `Manage Roles`, `Manage Nicknames`   |
| Bot                    | its role must sit **above** every role it grants       |
| `@everyone`            | **revoke** `Change Nickname`                           |
| Verifier role          | **no** `Manage Threads` — the bot does `add_user`      |
| `#registration-report` | restrict who can see it (second layer, not the guard)  |

Locking down nicknames is a permission, not code. Revoke `Change Nickname` from
`@everyone`; the bot keeps `Manage Nicknames` and can still set them. An
`on_member_update` listener that reverts nicknames would be the bot fighting the
user on every member update, and would mostly hit mods renaming someone on purpose.

Two failures that look like success if the setup is wrong, both caught and reported
to the verifier:

1. The bot's role sits below a target role → `add_roles` raises `Forbidden`. The
   approval is still recorded; the verifier is told to fix the role order.
2. The person left the server before a verifier decided → the roles land on their
   next join instead, via `on_member_join`.

## Logging

One JSON object per line on stdout, nothing else: no file, no log channel. The
formatter lives in `warden/log.py` and is installed from `main.py` before the bot
starts; `run(..., log_handler=None)` keeps discord.py from installing its own.

```json
{"ts":"2026-08-24T15:04:05.123+07:00","level":"INFO","logger":"warden.features.registration.services.registration_service","message":"registration: approved","registration_id":42,"guild_id":5,"user_id":9,"state":"approved","reviewed_by":3}
```

`message` stays a human sentence; anything passed as `extra=` is flattened to the
top level, which is what makes a run queryable — `docker logs warden | jq 'select(.registration_id==42)'`
reads one registration as a single thread. Before the row exists the thread is
`user_id`. Timestamps are local time (`TZ=Asia/Jakarta` in the `Dockerfile`) with
the offset written out, so they stay unambiguous read from anywhere.

| Level     | What lands there                                                       |
| --------- | ---------------------------------------------------------------------- |
| `DEBUG`   | Handler/view entry, service calls, repository operation names, **PII**  |
| `INFO`    | State changes: snapshot taken, form submitted, approved, rejected       |
| `WARNING` | Permission denied, prodi missing from the mapping, channel not found    |

`LOG_LEVEL` applies to `warden.*`. The `discord` logger is pinned to `WARNING` in
code — its `DEBUG` is gateway and heartbeat traffic that buries everything else.

**`LOG_LEVEL=DEBUG` prints PII.** `nama`, `nama_panggilan`, `nim`, `angkatan`,
`prodi`, `linkedin` and `reject_reason` are only ever passed to `log.debug()`, so
at `INFO` they are never rendered at all — the level is the enforcement, there is
no scrubbing filter. Raising to `DEBUG` in production is a temporary move while
investigating, not a permanent setting. Repository calls log the operation name
rather than SQL and params for the same reason: an `INSERT INTO registrations`
statement carries the whole form.

Tracebacks are **not** in the JSON output — the formatter ignores `exc_info`, and
there is no `on_app_command_error`. Both are deliberate and both are pending.
