"""Ingest — UDP server that receives CCSDS packets from the spacecraft,
validates + decodes them, and tracks link quality. Bus publishing and
TimescaleDB persistence are wired in by M3 (sinks.py); this milestone's
scope is decode + link monitoring + logging only."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from ground.ingest.decoder import CRCError, DecodeError, decode_packet
from ground.ingest.link_monitor import LinkMonitor
from shared.dictionary import TelemetryDictionary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")

DICTIONARY_PATH = Path(os.environ.get("DICTIONARY_PATH", "/app/config/telemetry_dictionary.yaml"))
LISTEN_PORT = int(os.environ.get("INGEST_PORT", "10015"))


class IngestProtocol(asyncio.DatagramProtocol):
    def __init__(self, dictionary: TelemetryDictionary, monitor: LinkMonitor) -> None:
        self.dictionary = dictionary
        self.monitor = monitor

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

        logger.info("RX %-8s apid=%-3d seq=%-5d %s",
                     decoded["packet_name"], decoded["apid"], decoded["seq"], decoded["parameters"])


async def main() -> None:
    dictionary = TelemetryDictionary.load(DICTIONARY_PATH)
    monitor = LinkMonitor()

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: IngestProtocol(dictionary, monitor),
        local_addr=("0.0.0.0", LISTEN_PORT),
    )
    logger.info("Ingest listening on udp://0.0.0.0:%d", LISTEN_PORT)

    try:
        await asyncio.Event().wait()   # run forever
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(main())
