"""Spacecraft simulator — samples every subsystem once a second, encodes a
CCSDS Space Packet per APID, and sends it down the (lossy) UDP link to the
ground ingest service. Command listening/ACK (APID 200/105) is wired in by
command_handler.py once M7 lands."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from shared.ccsds import TM, SpacePacket
from shared.dictionary import TelemetryDictionary
from spacecraft.link import LossyLink
from spacecraft.subsystems import adcs, comm, eps, thermal
from spacecraft.subsystems.obc import ObcState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("spacecraft")

DICTIONARY_PATH = Path(os.environ.get("DICTIONARY_PATH", "/app/config/telemetry_dictionary.yaml"))
INGEST_HOST = os.environ.get("INGEST_HOST", "ingest")
INGEST_PORT = int(os.environ.get("INGEST_PORT", "10015"))
TICK_S = 1.0

# name -> sample(t) -> dict, for the stateless subsystems. obc is handled
# separately below since it carries mutable state (mode, counters).
SAMPLERS = {
    "eps": eps.sample,
    "thermal": thermal.sample,
    "adcs": adcs.sample,
    "comm": comm.sample,
}


async def main() -> None:
    dictionary = TelemetryDictionary.load(DICTIONARY_PATH)
    link = LossyLink(INGEST_HOST, INGEST_PORT)
    obc_state = ObcState()
    seq = {apid: 0 for apid in dictionary.packets}

    logger.info("Spacecraft %s downlinking to %s:%s (DROP_PROB=%s CORRUPT_PROB=%s)",
                dictionary.spacecraft_name, INGEST_HOST, INGEST_PORT,
                os.environ.get("DROP_PROB", "0.02"), os.environ.get("CORRUPT_PROB", "0.01"))

    while True:
        now = time.time()
        for name, sampler in SAMPLERS.items():
            packet_def = dictionary.packets_by_name[name]
            _transmit(link, packet_def, sampler(now), now, seq)

        obc_def = dictionary.packets_by_name["obc"]
        _transmit(link, obc_def, obc_state.sample(now), now, seq)

        await asyncio.sleep(TICK_S)


def _transmit(link: LossyLink, packet_def, values: dict, now: float, seq: dict) -> None:
    payload = packet_def.encode_payload(values)
    pkt = SpacePacket(apid=packet_def.apid, packet_type=TM, sequence_count=seq[packet_def.apid],
                       timestamp=now, payload=payload)
    wire = pkt.encode()
    sent = link.send(wire)
    logger.info("TX %-8s apid=%-3d seq=%-5d len=%-3d sent=%s %s",
                packet_def.name, packet_def.apid, seq[packet_def.apid], len(wire), sent, wire.hex())
    seq[packet_def.apid] += 1


if __name__ == "__main__":
    asyncio.run(main())
