"""GET /api/history/{key} — TimescaleDB-backed historical telemetry for
OpenMCT's request() provider (time-conductor fixed-window playback)."""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg
from fastapi import APIRouter, Query

from ground.db import get_dsn

router = APIRouter()

_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(get_dsn(), min_size=1, max_size=5)
    return _pool


@router.get("/api/history/{key}")
async def history(key: str, start: int = Query(...), end: int = Query(...)):
    """start/end are ms epoch, matching every other timestamp in this system."""
    pool = await _get_pool()
    start_dt = datetime.fromtimestamp(start / 1000, tz=UTC)
    end_dt = datetime.fromtimestamp(end / 1000, tz=UTC)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT time, value, value_text, alarm FROM telemetry "
            "WHERE parameter = $1 AND time >= $2 AND time <= $3 "
            "ORDER BY time ASC LIMIT 10000",
            key, start_dt, end_dt,
        )
    return [
        {
            "timestamp": int(r["time"].timestamp() * 1000),
            "value": r["value"] if r["value"] is not None else r["value_text"],
            "alarm": r["alarm"],
        }
        for r in rows
    ]
