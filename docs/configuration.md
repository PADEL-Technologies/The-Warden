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

Flags read as true for `1`, `true`, `yes` (case-insensitive).

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
