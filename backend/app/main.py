import os

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from rq import Worker

app = FastAPI(
    title="Video Pipeline", version="0.1.0",
    docs_url="/api/docs", openapi_url="/api/openapi.json",
)


@app.get("/api/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health/ready")
def ready() -> JSONResponse:
    services = {"database": False, "redis": False, "worker": False}

    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        services["database"] = True
    except (psycopg.Error, KeyError, OSError):
        pass

    try:
        redis = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=2)
        services["redis"] = bool(redis.ping())
        services["worker"] = Worker.count(connection=redis) > 0
    except (RedisError, KeyError, OSError, ValueError):
        pass

    healthy = all(services.values())
    return JSONResponse(
        {"status": "ready" if healthy else "waiting", "services": services},
        status_code=200 if healthy else 503,
    )
