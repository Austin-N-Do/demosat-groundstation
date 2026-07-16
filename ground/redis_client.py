"""Shared Redis connection for ground services (ingest publishes, api reads)."""

from __future__ import annotations

import os

import redis.asyncio as redis

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

_client = None


async def get_redis():
    global _client
    if _client is None:
        _client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _client
