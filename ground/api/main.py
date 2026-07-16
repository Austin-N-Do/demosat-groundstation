"""Telemetry API — dictionary/history/link REST endpoints plus the
realtime WebSocket, all backed by the Redis Streams bus and TimescaleDB
that ingest writes to."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from ground.api import commands, dictionary_api, history, linkstats
from ground.api.bus_consumer import consume_decoded
from ground.api.ws import realtime_endpoint, ws_manager
from ground.redis_client import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = await get_redis()
    task = asyncio.create_task(consume_decoded(redis, ws_manager))
    yield
    task.cancel()
    try:
        await task
    except BaseException:
        pass


app = FastAPI(title="DemoSat-1 Telemetry API", lifespan=lifespan)

app.include_router(dictionary_api.router)
app.include_router(history.router)
app.include_router(linkstats.router)
app.include_router(commands.router)


@app.websocket("/ws/realtime")
async def ws_realtime(websocket: WebSocket):
    await realtime_endpoint(websocket)
