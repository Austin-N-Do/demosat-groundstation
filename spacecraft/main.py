"""Spacecraft simulator — samples every subsystem once a second, encodes a
CCSDS Space Packet per APID, and sends it down the (lossy) UDP link to the
ground ingest service. Also listens for telecommands (APID 200) and answers
each one with an acknowledgement packet (APID 105) on the same downlink."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from shared.ccsds import TM, SpacePacket
from shared.dictionary import TelemetryDictionary
from spacecraft.command_handler import CommandHandler, build_ack_payload
from spacecraft.link import LossyLink
from spacecraft.subsystems import adcs, comm, eps, thermal
from spacecraft.subsystems.obc import ObcState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("spacecraft")

DICTIONARY_PATH = Path(os.environ.get("DICTIONARY_PATH", "/app/config/telemetry_dictionary.yaml"))
INGEST_HOST = os.environ.get("INGEST_HOST", "ingest")
INGEST_PORT = int(os.environ.get("INGEST_PORT", "10015"))
TC_PORT = int(os.environ.get("TC_PORT", "10025"))
TICK_S = 1.0


async def main() -> None:
    dictionary = TelemetryDictionary.load(DICTIONARY_PATH)
    link = LossyLink(INGEST_HOST, INGEST_PORT)
    obc_state = ObcState()
    seq = {apid: 0 for apid in dictionary.packets}

    def send_ack(cmd_id: int, status: int, seq_of_command: int) -> None:
        ack_def = dictionary.packets_by_name["cmd_ack"]
        payload = build_ack_payload(ack_def, cmd_id, status, seq_of_command)
        _transmit(link, ack_def, payload, time.time(), seq)

    loop = asyncio.get_running_loop()
    tc_transport, _ = await loop.create_datagram_endpoint(
        lambda: CommandHandler(dictionary, obc_state, send_ack),
        local_addr=("0.0.0.0", TC_PORT),
    )

    logger.info("Spacecraft %s downlinking to %s:%s, telecommand uplink on udp/%d "
                "(DROP_PROB=%s CORRUPT_PROB=%s)",
                dictionary.spacecraft_name, INGEST_HOST, INGEST_PORT, TC_PORT,
                os.environ.get("DROP_PROB", "0.02"), os.environ.get("CORRUPT_PROB", "0.01"))

    try:
        while True:
            now = time.time()
            # Subsystems that depend on commanded state read it here; the rest
            # are pure functions of mission time.
            samples = {
                "eps": eps.sample(now),
                "thermal": thermal.sample(now, heater_on=obc_state.heater_on),
                "adcs": adcs.sample(now),
                "comm": comm.sample(now),
                "obc": obc_state.sample(now),
            }
            for name, values in samples.items():
                packet_def = dictionary.packets_by_name[name]
                _transmit(link, packet_def, packet_def.encode_payload(values), now, seq)

            await asyncio.sleep(TICK_S)
    finally:
        tc_transport.close()
        link.close()


def _transmit(link: LossyLink, packet_def, payload: bytes, now: float, seq: dict) -> None:
    pkt = SpacePacket(apid=packet_def.apid, packet_type=TM, sequence_count=seq[packet_def.apid],
                       timestamp=now, payload=payload)
    wire = pkt.encode()
    sent = link.send(wire)
    logger.info("TX %-8s apid=%-3d seq=%-5d len=%-3d sent=%s %s",
                packet_def.name, packet_def.apid, seq[packet_def.apid], len(wire), sent, wire.hex())
    seq[packet_def.apid] += 1


if __name__ == "__main__":
    asyncio.run(main())
