# Database & migrations

PostgreSQL via `asyncpg`. Migrations are managed by
[goose](https://github.com/pressly/goose) — plain SQL files in `migrations/` with
`-- +goose Up` / `-- +goose Down` sections. Runs are recorded in goose's
`goose_db_version` table.

Install the goose binary once
([releases](https://github.com/pressly/goose/releases), or `make goose-install`
which pins `v3.24.3`).

```bash
make db                            # docker compose up -d: postgres:18-alpine on localhost:5432 (warden/warden)
export DATABASE_URL=postgres://warden:warden@localhost:5432/warden
make migrate-up                    # apply pending migrations
make migrate-status                # what is applied
make migration NAME=add_left_at    # scaffold a new migration (goose create -s)
```

The app itself never runs migrations — apply them as a separate step (or in CI)
before starting the bot.

## Tests against a real database

Tests that need Postgres read `WARDEN_TEST_DATABASE_URL` and are skipped when it is
unset:

```bash
make db
goose -dir migrations postgres postgres://warden:warden@localhost:5432/warden up
WARDEN_TEST_DATABASE_URL=postgres://warden:warden@localhost:5432/warden uv run pytest
```

## Schema

No foreign keys, by design — the repository layer owns referential integrity (e.g.
`save(force=True)` deletes junction rows before parent rows). All primary keys are
`BIGINT GENERATED ALWAYS AS IDENTITY`.

### Onboarding (`20260822000000_init.sql`)

```
roles.id      <- member_roles.role_id
members.id    <- member_roles.member_id
```

`onboardings` holds one row per guild: when it was snapshotted, by whom (`NULL` =
automatic on guild join), and the member count.

### Registration (`20260823000000_registration.sql`)

One row per **attempt**, not per person. Nullable columns with the per-type shape
enforced by a `CHECK`:

```sql
CONSTRAINT registrations_shape CHECK (
    state = 'open'
 OR (nama IS NOT NULL AND nama_panggilan IS NOT NULL AND angkatan IS NOT NULL
     AND ((type = 'mahasiswa' AND nim IS NOT NULL AND prodi IS NOT NULL)
       OR (type = 'alumni'    AND linkedin IS NOT NULL)))
);
```

A row is created as `open` the moment the button is clicked, before the form exists,
so the per-type shape only kicks in after submit.

Integrity is the database's job, not an `if` in the service — two verifiers can
click approve at nearly the same moment, and a check in code races:

```sql
-- one live/approved registration per person
CREATE UNIQUE INDEX registrations_active
    ON registrations (guild_id, user_id)
    WHERE state IN ('open', 'pending', 'approved');

-- one approved registration per NIM. NULL never collides in Postgres,
-- so an empty alumni NIM is safe for free.
CREATE UNIQUE INDEX registrations_nim_approved
    ON registrations (guild_id, nim)
    WHERE state = 'approved' AND nim IS NOT NULL;
```

`thread_id` and `report_message_id` are indexed — both are how an interaction is
resolved back to a row.

`angkatan` is stored as `TEXT`: it is an identity, not a number anything is computed
from. Consistent with `joined_at TEXT` in `members`.

### Approve writes two tables in one statement

`registrations` is the only table the registration feature owns, with one exception:
`decide()` is a data-modifying CTE that transitions the row **and** enrols the person
into `members`.

```sql
WITH decided AS (
    UPDATE registrations SET state = $2, ... WHERE id = $1 AND state = 'pending'
    RETURNING *
), enrolled AS (
    INSERT INTO members (guild_id, user_id, joined_at)
    SELECT guild_id, user_id, $5 FROM decided WHERE state = 'approved'
    ON CONFLICT (guild_id, user_id) DO NOTHING
)
SELECT * FROM decided
```

One statement rather than two inside a `conn.transaction()`: the `members` row is
*derived* from the row that just changed, so it cannot drift out of sync — which is
exactly what issue #12 was, approved people with no `members` row at all. The
`WHERE state = 'approved'` filter is what keeps reject a no-op here, and
`ON CONFLICT DO NOTHING` leaves someone already captured by the onboarding snapshot
untouched, `joined_at` included.

`member_roles` is deliberately **not** written on approve — it stores internal
`roles.id`, which only exists if the snapshot ran, and every other role change after
the snapshot is equally stale.

## Operational note: pgbouncer

`create_pool()` does not set `statement_cache_size=0`. That is safe under pgbouncer
`session` mode (the default), which is what runs today. It **breaks** under
`transaction` mode — `asyncpg` uses per-connection prepared statements while
pgbouncer hands out a different server connection per transaction:

```
prepared statement "__asyncpg_stmt_3__" does not exist
```

It shows up intermittently, under load, and never locally without pgbouncer. Applies
to both pools (`warden/features/onboarding/__init__.py`,
`warden/features/registration/__init__.py`). Worth knowing because switching to
`transaction` mode is the usual move exactly when connections start getting tight.
