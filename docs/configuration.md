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
| `MODERATION_ENABLED`   | `true`       | Load the moderation feature at all                     |
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

## Moderation

`MODERATION_ADMIN_ROLE_IDS` is **required** when `MODERATION_ENABLED` is true and
read with `os.environ[...]`: without it nobody could register a keyword and nobody
would be exempt from the filter, so the bot fails at startup rather than running
mute.

| Variable                         | Default    | Purpose                                                    |
| -------------------------------- | ---------- | ---------------------------------------------------------- |
| `MODERATION_ADMIN_ROLE_IDS`      | — required | `111,222` — may run `/keyword`, `/regex`, `/label`          |
| `MODERATION_IGNORED_CHANNEL_IDS` | empty      | `333,444` — messages here are never inspected               |
| `MODERATION_WARNING_DELETE_AFTER`| `15`       | Seconds before the public warning deletes itself            |

`MODERATION_ADMIN_ROLE_IDS` does double duty: those roles are also **exempt from
the filter**. That is one variable rather than two, and it means a mod quoting a
judol link while discussing a case does not trip the filter they maintain.

The channel list is an **exemption** list, not an allowlist — every channel is
watched unless it is named here, so a newly created channel is covered by default
instead of being silently unmonitored.

Command access is the app owner (`bot.is_owner()`, which reads the application
owner from the Developer Portal and therefore survives a change of server
ownership) **or** any of those roles. A rejected attempt gets an ephemeral reply
and a `WARNING` line carrying `user_id`.

See [Moderation feature](moderation.md) for the labels and how matching works.

### Privacy: this feature stores chat messages

`moderation_hits.content` holds the **full text of every flagged message**,
permanently, and there is no TTL. That is deliberate — the table is the training
corpus for the fastText phase, and an automatic purge would delete the data before
it can be used. It is also the sharpest data-retention decision in this repo, so
it should be a conscious one:

- Only messages that **matched** a keyword or regex rule are stored. Clean
  messages are never written; a message with no match costs no database call.
- Anyone with database access can read it. Restrict Postgres accordingly — the
  Discord permission model does not apply here.
- Deleting one person's history is a direct statement, there is no command for it:
  ```sql
  DELETE FROM moderation_hit_matches WHERE hit_id IN
      (SELECT id FROM moderation_hits WHERE author_id = <user_id>);
  DELETE FROM moderation_hits WHERE author_id = <user_id>;
  ```

Unlike registration PII, this is **not** gated behind `LOG_LEVEL=DEBUG` — the
message text is in the database at every log level. Repository calls still log
operation names rather than SQL and params, for the same reason as elsewhere: an
`INSERT INTO moderation_hits` statement carries the whole message.

## Server permissions this assumes

| Who                    | Permission                                            |
| ---------------------- | ----------------------------------------------------- |
| Bot                    | `Manage Threads`, `Manage Roles`, `Manage Nicknames`   |
| Bot                    | `Manage Messages` — moderation deletes flagged messages |
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
| `ERROR`   | Unhandled exceptions, with `exc_type`, `exc_message` and `traceback`    |

`LOG_LEVEL` applies to `warden.*`. The `discord` logger is pinned to `WARNING` in
code — its `DEBUG` is gateway and heartbeat traffic that buries everything else.

**`LOG_LEVEL=DEBUG` prints PII.** `nama`, `nama_panggilan`, `nim`, `angkatan`,
`prodi`, `linkedin` and `reject_reason` are only ever passed to `log.debug()`, so
at `INFO` they are never rendered at all — the level is the enforcement, there is
no scrubbing filter. Raising to `DEBUG` in production is a temporary move while
investigating, not a permanent setting. Repository calls log the operation name
rather than SQL and params for the same reason: an `INSERT INTO registrations`
statement carries the whole form.

One exception to the rule above: `exc_message` and `traceback` can carry PII at
`ERROR`, outside the `DEBUG` gate. asyncpg puts `DETAIL` inside the exception
message, so a `registrations_nim_approved` violation prints the NIM and a
`registrations_shape` violation prints the whole failing row. That is a deliberate
trade — stripping `DETAIL` would remove the one line worth reading at 2am, and the
crash line already carries `user_id`. Tracebacks never include local variables.

## Errors

Unhandled exceptions land in the JSON as `exc_type`, `exc_message` and `traceback`
(a single string — `jq -r .traceback` prints it readable). No warden code catches
them; discord.py already logs every surface with `exc_info`, and the formatter
renders it:

| Surface                                   | Logger                    |
| ----------------------------------------- | ------------------------- |
| Buttons, select menus                     | `discord.ui.view`         |
| Modals                                    | `discord.ui.modal`        |
| `!registration post`, `!onboard existing` | `discord.ext.commands.bot`|
| `on_member_join`, `on_guild_join`         | `discord.client`          |
| The hourly sweep                          | `discord.ext.tasks`       |
| `on_message`, `on_message_edit`           | `discord.client`          |
| `/keyword`, `/regex`, `/label`            | `discord.app_commands.tree` |

Errors that warden catches itself are logged **without** `exc_info` — the message
already names the cause and `extra=` carries the IDs. That keeps
`jq 'select(.traceback)'` meaning "nothing handled this", not "something happened".

An exception in the hourly sweep that is not a network error stops the loop for
good; discord.py does not retry those and nothing restarts it. The bot keeps
running, the sweep does not. That is why the sweep prints a line every hour even
when it deletes nothing.

Still pending: the user gets no reply when a button or modal raises — Discord shows
"This interaction failed" and nothing else. Fixing that means overriding `on_error`,
which is also where `user_id` would join the crash line.

The moderation cog closes that gap for itself with `cog_app_command_error`, which
turns a rejected permission check into an ephemeral reply plus a `WARNING`. It only
covers that cog; there is still no bot-wide `on_app_command_error`.
