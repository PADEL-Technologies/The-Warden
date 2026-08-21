from pathlib import Path

import aiosqlite

# migrations/ hidup di root repo, se-level dengan warden/
MIGRATIONS_DIR = Path(__file__).resolve().parents[5] / "migrations"


async def apply_pending(db: aiosqlite.Connection) -> None:
    """Terapkan .sql yang belum tercatat, urut nama file (<timestamp>_<name>.sql)."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT name FROM schema_migrations")
    applied = {row[0] for row in rows}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in applied:
            continue
        await db.executescript(path.read_text(encoding="utf-8"))
        await db.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))
        await db.commit()
