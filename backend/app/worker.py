"""Run the account-backed script worker on the installer's computer."""

import argparse
import json
import os
from pathlib import Path

from redis import Redis
from rq import Queue, SimpleWorker, SpawnWorker
from rq.timeouts import TimerDeathPenalty


class WindowsWorker(SimpleWorker):
    """RQ 2.3.2 SpawnWorker still uses Unix signals and os.setpgrp on Windows."""

    death_penalty_class = TimerDeathPenalty


def host_worker_class():
    return WindowsWorker if os.name == "nt" else SpawnWorker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--burst", action="store_true", help="Exit when the queue is empty")
    parser.add_argument("--config", type=Path, default=Path.home() / ".config" / "video-pipeline" / "worker.json",
                        help="Private JSON file with DATABASE_URL and REDIS_URL")
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
        except (OSError, ValueError) as exc:
            parser.error(f"Invalid worker configuration: {exc}")

    for name in ("DATABASE_URL", "REDIS_URL"):
        if not os.environ.get(name):
            parser.error(f"{name} is required in {args.config} or the environment")

    connection = Redis.from_url(os.environ["REDIS_URL"])
    queue = Queue("default", connection=connection)
    host_worker_class()([queue], connection=connection, name="pipeline-worker").work(burst=args.burst)


if __name__ == "__main__":
    main()
