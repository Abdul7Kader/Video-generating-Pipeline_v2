"""Apply the versioned PostgreSQL schema from a clean checkout."""

import os
import sys
from pathlib import Path

import psycopg


MIGRATIONS = Path(__file__).parent / "migrations"


def migrate(direction: str = "up") -> None:
    if direction not in {"up", "down"}:
        raise ValueError("direction must be 'up' or 'down'")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(71007)")
        exists = conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]
        if direction == "up":
            if exists:
                versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
                if versions != {1}:
                    raise RuntimeError(f"unexpected migration versions: {versions}")
                return
            sql = (MIGRATIONS / "0001_initial.sql").read_text(encoding="utf-8")
        else:
            if not exists:
                return
            versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            if versions != {1}:
                raise RuntimeError(f"unexpected migration versions: {versions}")
            sql = (MIGRATIONS / "0001_initial.down.sql").read_text(encoding="utf-8")
        conn.execute(sql)


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "up")
