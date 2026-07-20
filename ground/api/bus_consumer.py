"""Background task: tails the telemetry.decoded Redis Stream and fans each
parameter out to any WebSocket connection subscribed to it. Starts from
"$" (only new entries) — this is a live tail, not a replay."""

from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("api.bus_consumer")


async def consume_decoded(redis, ws_manager) -> None:
    last_id = "$"
    while True:
        try:
            resp = await redis.xread({"telemetry.decoded": last_id}, block=5000, count=50)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("xread failed, retrying: %s", e)
            await asyncio.sleep(1)
            continue

        if not resp:
            continue

        for _stream_name, entries in resp:
            for entry_id, fields in entries:
                last_id = entry_id
                try:
                    msg = json.loads(fields["data"])
                except Exception:
                    continue
                if msg.get("packet_name") == "cmd_ack":
                    _correlate_ack(msg.get("parameters", {}))

                for key, info in msg.get("parameters", {}).items():
                    datum = {
                        "timestamp": msg["timestamp"],
                        "value": info["value"],
                        "alarm": info["alarm"],
                    }
                    await ws_manager.broadcast(key, datum)


def _correlate_ack(parameters: dict) -> None:
    """Feed a decoded APID 105 packet to the command registry. `status` has
    already been resolved to its enum label by the dictionary decoder."""
    from ground.api.commands import registry

    try:
        registry.record_ack(
            cmd_id=parameters["cmd_ack.cmd_id"]["value"],
            status=parameters["cmd_ack.status"]["value"],
            seq_of_command=parameters["cmd_ack.seq_of_command"]["value"],
        )
    except Exception as e:
        logger.debug("could not correlate ack: %s", e)
