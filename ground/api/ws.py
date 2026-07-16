"""WS /ws/realtime — per-connection subscribe/unsubscribe to parameter
keys; only datums for subscribed keys are sent to a given connection."""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("api.ws")


class WSManager:
    def __init__(self) -> None:
        self._subs: dict = {}   # WebSocket -> set[str] of subscribed keys

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._subs[ws] = set()

    def disconnect(self, ws: WebSocket) -> None:
        self._subs.pop(ws, None)

    async def broadcast(self, key: str, datum: dict) -> None:
        dead = []
        for ws, keys in self._subs.items():
            if key not in keys:
                continue
            try:
                await ws.send_json({"type": "telemetry", "key": key, **datum})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._subs.pop(ws, None)


ws_manager = WSManager()


async def realtime_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            key = msg.get("key")
            if not key:
                continue
            if msg.get("type") == "subscribe":
                ws_manager._subs[websocket].add(key)
            elif msg.get("type") == "unsubscribe":
                ws_manager._subs[websocket].discard(key)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("realtime ws closed: %s", e)
        ws_manager.disconnect(websocket)
