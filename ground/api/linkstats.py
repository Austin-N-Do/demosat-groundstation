"""GET /api/link — most recent link-quality snapshot (CRC failures,
sequence gaps, packets received) published by ingest once a second."""

from __future__ import annotations

import json

from fastapi import APIRouter

from ground.redis_client import get_redis

router = APIRouter()


@router.get("/api/link")
async def link_stats():
    redis = await get_redis()
    entries = await redis.xrevrange("link.stats", count=1)
    if not entries:
        return {}
    _entry_id, fields = entries[0]
    return json.loads(fields["data"])
