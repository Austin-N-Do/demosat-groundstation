"""Ingest — UDP server that receives CCSDS packets from the spacecraft,
validates + decodes them, evaluates limits, and fans the result out to
Redis Streams (realtime) and TimescaleDB (durable archive)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from ground.db import get_dsn
from ground.ingest.decoder import CRCError, DecodeError, decode_packet
from ground.ingest.limits import LimitsEngine
from ground.ingest.link_monitor import LinkMonitor
from ground.ingest.sinks import BusPublisher, TimescaleWriter, row_for_parameter
from ground.redis_client import get_redis
from shared.dictionary import TelemetryDictionary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")

DICTIONARY_PATH = Path(os.environ.get("DICTIONARY_PATH", "/app/config/telemetry_dictionary.yaml"))
LISTEN_PORT = int(os.environ.get("INGEST_PORT", "10015"))
LINK_STATS_INTERVAL_S = 1.0


class IngestProtocol(asyncio.DatagramProtocol):
    def __init__(self, dictionary: TelemetryDictionary, monitor: LinkMonitor,
                 limits: LimitsEngine, bus: BusPublisher, timescale: TimescaleWriter) -> None:
        self.dictionary = dictionary
        self.monitor = monitor
        self.limits = limits
        self.bus = bus
        self.timescale = timescale

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            decoded = decode_packet(self.dictionary, data)
        except CRCError:
            self.monitor.record_crc_failure()
            logger.warning("CRC failure from %s (%d bytes)", addr, len(data))
            return
        except (DecodeError, ValueError) as e:
            logger.warning("decode error from %s: %s", addr, e)
            return

        missed = self.monitor.record_receipt(decoded["apid"], decoded["seq"])
        if missed:
            logger.warning("sequence gap: apid=%d missed=%d (arrived seq=%d)",
                            decoded["apid"], missed, decoded["seq"])

        packet_def = self.dictionary.packets[decoded["apid"]]
        evaluated, transitions = self.limits.evaluate(packet_def, decoded["parameters"])

        logger.info("RX %-8s apid=%-3d seq=%-5d %s",
                     decoded["packet_name"], decoded["apid"], decoded["seq"], decoded["parameters"])
        for key, alarm in transitions:
            logger.info("ALARM %s -> %s", key, alarm)

        asyncio.create_task(self._persist(decoded, evaluated, transitions))

    async def _persist(self, decoded: dict, evaluated: dict, transitions: list) -> None:
        try:
            await self.bus.publish_decoded({
                "apid": decoded["apid"], "packet_name": decoded["packet_name"],
                "seq": decoded["seq"], "timestamp": decoded["timestamp"],
                "parameters": evaluated,
            })
            for key, alarm in transitions:
                await self.bus.publish_alarm({
                    "parameter": key, "alarm": alarm, "timestamp": decoded["timestamp"],
                })
            rows = [row_for_parameter(key, info, decoded["timestamp"]) for key, info in evaluated.items()]
            await self.timescale.add_rows(rows)
        except Exception as e:
            logger.debug("persist failed (bus/db): %s", e)


async def _publish_link_stats(bus: BusPublisher, monitor: LinkMonitor) -> None:
    while True:
        await asyncio.sleep(LINK_STATS_INTERVAL_S)
        try:
            snap = monitor.snapshot()
            snap["timestamp"] = int(time.time() * 1000)
            await bus.publish_link_stats(snap)
        except Exception as e:
            logger.debug("link stats publish failed: %s", e)


async def main() -> None:
    dictionary = TelemetryDictionary.load(DICTIONARY_PATH)
    monitor = LinkMonitor()
    limits = LimitsEngine()

    redis = await get_redis()
    bus = BusPublisher(redis)
    timescale = TimescaleWriter(get_dsn())
    await timescale.start()

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: IngestProtocol(dictionary, monitor, limits, bus, timescale),
        local_addr=("0.0.0.0", LISTEN_PORT),
    )
    logger.info("Ingest listening on udp://0.0.0.0:%d", LISTEN_PORT)

    stats_task = asyncio.create_task(_publish_link_stats(bus, monitor))
    try:
        await asyncio.Event().wait()   # run forever
    finally:
        stats_task.cancel()
        transport.close()
        await timescale.close()


if __name__ == "__main__":
    asyncio.run(main())
