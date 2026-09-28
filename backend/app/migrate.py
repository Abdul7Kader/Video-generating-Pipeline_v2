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
        versions = ({row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
                    if exists else set())
        if versions not in (set(), {1}, {1, 2}):
            raise RuntimeError(f"unexpected migration versions: {versions}")
        if direction == "up":
            for version, filename in ((1, "0001_initial.sql"), (2, "0002_script_generation.sql")):
                if version not in versions:
                    conn.execute((MIGRATIONS / filename).read_text(encoding="utf-8"))
        else:
            for version, filename in ((2, "0002_script_generation.down.sql"),
                                      (1, "0001_initial.down.sql")):
                if version in versions:
                    conn.execute((MIGRATIONS / filename).read_text(encoding="utf-8"))


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "up")
