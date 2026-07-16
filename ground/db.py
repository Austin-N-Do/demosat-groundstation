"""TimescaleDB connection string, built from the same env vars docker-compose
passes to the timescaledb service so nothing has to be duplicated/hardcoded."""

from __future__ import annotations

import os


def get_dsn() -> str:
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "telemetry")
    db = os.environ.get("POSTGRES_DB", "telemetry")
    host = os.environ.get("POSTGRES_HOST", "timescaledb")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"
