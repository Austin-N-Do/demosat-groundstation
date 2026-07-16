"""Wire bytes -> CRC-verified, dictionary-decoded telemetry. Raises on CRC
failure or an APID the dictionary doesn't know about; the caller (main.py)
is responsible for counting/logging those separately from a clean decode."""

from __future__ import annotations

from shared.ccsds import CRCError, SpacePacket
from shared.dictionary import TelemetryDictionary

__all__ = ["CRCError", "DecodeError", "decode_packet"]


class DecodeError(ValueError):
    """Packet passed CRC but isn't decodable (unknown APID, bad payload length)."""


def decode_packet(dictionary: TelemetryDictionary, wire: bytes) -> dict:
    pkt = SpacePacket.decode(wire)   # raises CRCError / ValueError on malformed packets

    packet_def = dictionary.packets.get(pkt.apid)
    if packet_def is None:
        raise DecodeError(f"unknown apid {pkt.apid}")

    parameters = packet_def.decode_payload(pkt.payload)
    return {
        "apid": pkt.apid,
        "packet_name": packet_def.name,
        "seq": pkt.sequence_count,
        "timestamp": int(pkt.timestamp * 1000),   # ms epoch, everywhere downstream
        "parameters": parameters,
    }
