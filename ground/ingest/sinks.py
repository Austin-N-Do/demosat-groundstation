"""Where decoded telemetry goes: Redis Streams for anything real-time
(WebSocket fanout, historical fallback) and a batched TimescaleDB writer
for the durable archive OpenMCT's historical provider queries."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

import asyncpg

MAXLEN = 10_000


class BusPublisher:
    def __init__(self, redis) -> None:
        self.redis = redis

    async def publish_decoded(self, msg: dict) -> None:
        await self.redis.xadd("telemetry.decoded", {"data": json.dumps(msg)},
                              maxlen=MAXLEN, approximate=True)

    async def publish_alarm(self, msg: dict) -> None:
        await self.redis.xadd("telemetry.alarms", {"data": json.dumps(msg)},
                               maxlen=MAXLEN, approximate=True)

    async def publish_link_stats(self, msg: dict) -> None:
        await self.redis.xadd("link.stats", {"data": json.dumps(msg)},
                               maxlen=MAXLEN, approximate=True)


class TimescaleWriter:
    """Buffers (time, parameter, value, value_text, alarm) rows and flushes
    on whichever comes first: flush_size rows or flush_interval_s elapsed."""

    def __init__(self, dsn: str, flush_interval_s: float = 1.0, flush_size: int = 100) -> None:
        self.dsn = dsn
        self.flush_interval_s = flush_interval_s
        self.flush_size = flush_size
        self._buffer: list = []
        self._pool = None
        self._lock = asyncio.Lock()
        self._last_flush = time.monotonic()

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=3)

    async def add_rows(self, rows: list) -> None:
        async with self._lock:
            self._buffer.extend(rows)
            due = (len(self._buffer) >= self.flush_size
                   or (time.monotonic() - self._last_flush) >= self.flush_interval_s)
        if due:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            rows, self._buffer = self._buffer, []
            self._last_flush = time.monotonic()
        if not rows or self._pool is None:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO telemetry (time, parameter, value, value_text, alarm) "
                "VALUES ($1, $2, $3, $4, $5)",
                rows,
            )

    async def close(self) -> None:
        await self.flush()
        if self._pool is not None:
            await self._pool.close()


def row_for_parameter(key: str, info: dict, timestamp_ms: int) -> tuple:
    """One TimescaleWriter row from a limits-evaluated parameter."""
    ts = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    value = info["value"]
    if isinstance(value, (int, float)):
        return (ts, key, float(value), None, info["alarm"])
    return (ts, key, None, str(value), info["alarm"])
