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
            versions = ({row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
                        if exists else set())
            expected = set(range(1, max(versions, default=0) + 1))
            if versions != expected:
                raise RuntimeError(f"unexpected migration versions: {versions}")
            for path in sorted(MIGRATIONS.glob("*_*.sql")):
                if path.name.endswith(".down.sql"):
                    continue
                version = int(path.name.split("_", 1)[0])
                if version not in versions:
                    conn.execute(path.read_text(encoding="utf-8"))
            return
        else:
            if not exists:
                return
            versions = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            expected = set(range(1, max(versions, default=0) + 1))
            if versions != expected:
                raise RuntimeError(f"unexpected migration versions: {versions}")
            for version in sorted((value for value in versions if value > 1), reverse=True):
                path = next(MIGRATIONS.glob(f"{version:04d}_*.down.sql"))
                conn.execute(path.read_text(encoding="utf-8"))
            sql = (MIGRATIONS / "0001_initial.down.sql").read_text(encoding="utf-8")
        conn.execute(sql)


if __name__ == "__main__":
    migrate(sys.argv[1] if len(sys.argv) > 1 else "up")
