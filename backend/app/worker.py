"""Run the account-backed script worker on the installer's computer."""

import argparse
import json
import os
from pathlib import Path
import shutil
import time

import psycopg
from redis import Redis
from redis.exceptions import RedisError, TimeoutError as RedisTimeoutError
from rq import Queue, SimpleWorker, SpawnWorker
from rq.timeouts import TimerDeathPenalty

from app.antigravity import GenerationFailure, _safe_settings


def check_installation() -> None:
    """Check local prerequisites without a model call or exposing credentials."""
    if shutil.which("agy") is None:
        raise GenerationFailure("AGY_UNAVAILABLE", "Antigravity CLI fehlt im PATH des Worker-Benutzers.")
    _safe_settings()
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as connection:
            migrated = connection.execute("SELECT to_regclass('script_generation_jobs') IS NOT NULL "
                                          "AND to_regclass('production_steps') IS NOT NULL").fetchone()[0]
            if migrated:
                migrated = connection.execute('SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 4)').fetchone()[0]
    except (psycopg.Error, OSError, ValueError) as exc:
        raise GenerationFailure("DATABASE_UNAVAILABLE", "Die konfigurierte PostgreSQL-Datenbank ist nicht erreichbar.") from exc
    if not migrated:
        raise GenerationFailure("MIGRATION_REQUIRED", "Die Datenbankmigrationen fehlen. Zuerst den Compose-API-Dienst starten.")
    try:
        with Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=3, socket_timeout=3) as connection:
            connection.ping()
    except (RedisError, OSError, ValueError) as exc:
        raise GenerationFailure("REDIS_UNAVAILABLE", "Die konfigurierte Redis-Warteschlange ist nicht erreichbar.") from exc


class RedisReconnectMixin:
    def heartbeat(self, *args, **kwargs):
        super().heartbeat(*args, **kwargs)
        if not getattr(self, "production_recovery_enabled", False):
            return
        now = time.monotonic()
        if now - getattr(self, "last_production_recovery", 0) < 5:
            return
        self.last_production_recovery = now
        from app.production_dispatch import recover_productions
        try:
            recover_productions(self.queues[0])
        except (psycopg.Error, RedisError, OSError):
            self.log.warning("Produktions-Wiederaufnahme wartet auf Datenbank/Redis.")

    def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
        # RQ 2.3.2 exits its work loop on Redis TimeoutError, even while idle.
        # Retry only waiting for work; model failures still require explicit UI retry.
        # https://github.com/rq/rq/blob/v2.3.2/rq/worker.py
        while True:
            try:
                return super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)
            except RedisTimeoutError:
                self.log.warning("Redis-Antwortzeit überschritten; Warteschlangenzugriff wird in 5 Sekunden wiederholt.")
                time.sleep(5)


class WindowsWorker(RedisReconnectMixin, SimpleWorker):
    """RQ 2.3.2 SpawnWorker still uses Unix signals and os.setpgrp on Windows."""

    death_penalty_class = TimerDeathPenalty


class PosixWorker(RedisReconnectMixin, SpawnWorker):
    """Keep the process isolation provided by SpawnWorker on Linux and macOS."""


def host_worker_class():
    return WindowsWorker if os.name == "nt" else PosixWorker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--burst", action="store_true", help="Exit when the queue is empty")
    parser.add_argument("--check", action="store_true", help="Check CLI, credit guard, database and Redis without a model call")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config" / "video-pipeline" / "worker.json",
                        help="Private JSON file with database, queue and optional Pexels/media configuration")
    args = parser.parse_args()

    if args.config.exists():
        try:
            settings = json.loads(args.config.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                raise ValueError("configuration must be an object")
            for name in ("DATABASE_URL", "REDIS_URL"):
                if not isinstance(settings.get(name), str) or not settings[name]:
                    raise ValueError(f"{name} is missing")
                os.environ[name] = settings[name]
            for name in ("PEXELS_API_KEY", "MEDIA_ROOT", "FFPROBE_PATH", "PIPER_MODEL_PATH"):
                if name in settings:
                    if not isinstance(settings[name], str) or not settings[name]:
                        raise ValueError(f"{name} must be a nonempty string")
                    os.environ[name] = settings[name]
        except (OSError, ValueError) as exc:
            parser.error(f"Invalid worker configuration: {exc}")

    for name in ("DATABASE_URL", "REDIS_URL"):
        if not os.environ.get(name):
            parser.error(f"{name} is required in {args.config} or the environment")

    try:
        check_installation()
    except GenerationFailure as exc:
        parser.error(f"{exc.code}: {exc}")
    if args.check:
        print("CLI, Kostensperre, Datenbank und Redis geprüft. Anmeldung und Pro-Konto benötigen einen echten Skriptauftrag.")
        return

    connection = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=3)
    queue = Queue("default", connection=connection)
    worker = host_worker_class()([queue], connection=connection, name="pipeline-worker")
    worker.production_recovery_enabled = True
    # RQ heartbeats on every dequeue loop, including an otherwise idle queue.
    worker.worker_ttl = 20
    worker.work(burst=args.burst)


if __name__ == "__main__":
    main()
