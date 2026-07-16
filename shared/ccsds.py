"""CCSDS Space Packet Protocol — encode/decode of the primary + secondary
header, payload, and CRC-16 trailer used for every telemetry (TM) and
telecommand (TC) packet on the simulated space link.

Layout (big-endian throughout):
  primary header (6B):   version(3b)=0 | type(1b) | sec-hdr-flag(1b)=1 | APID(11b)
                          seq-flags(2b)=0b11 | seq-count(14b, wraps at 16384)
                          packet data length = len(secondary+payload) - 1
  secondary header (8B): coarse time (u32 unix seconds) | fine time (u32 us)
  payload:                fixed layout per APID (see shared/dictionary.py)
  trailer (2B):           CRC-16/CCITT-FALSE over every preceding byte
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from shared.crc import crc16_ccitt

PRIMARY_HEADER_LEN = 6
SECONDARY_HEADER_LEN = 8
HEADER_LEN = PRIMARY_HEADER_LEN + SECONDARY_HEADER_LEN
TRAILER_LEN = 2

TM = 0
TC = 1


class CRCError(ValueError):
    """Raised by decode() when the trailer CRC doesn't match the body."""


@dataclass
class SpacePacket:
    apid: int
    packet_type: int = TM
    sequence_count: int = 0          # 14-bit, wraps at 16384
    timestamp: float = 0.0           # unix seconds, fractional
    payload: bytes = b""

    def encode(self) -> bytes:
        version, sec_hdr_flag, seq_flags = 0, 1, 0b11
        word0 = (version << 13) | (self.packet_type << 12) | (sec_hdr_flag << 11) | (self.apid & 0x7FF)
        word1 = (seq_flags << 14) | (self.sequence_count & 0x3FFF)
        data_length = SECONDARY_HEADER_LEN + len(self.payload) - 1
        primary = struct.pack(">HHH", word0, word1, data_length)

        coarse = int(self.timestamp)
        fine = int(round((self.timestamp - coarse) * 1_000_000))
        secondary = struct.pack(">II", coarse, fine)

        body = primary + secondary + self.payload
        return body + struct.pack(">H", crc16_ccitt(body))

    @classmethod
    def decode(cls, data: bytes) -> SpacePacket:
        if len(data) < HEADER_LEN + TRAILER_LEN:
            raise ValueError(f"packet too short: {len(data)} bytes")

        body, trailer = data[:-TRAILER_LEN], data[-TRAILER_LEN:]
        (stored_crc,) = struct.unpack(">H", trailer)
        if crc16_ccitt(body) != stored_crc:
            raise CRCError("CRC mismatch")

        word0, word1, data_length = struct.unpack(">HHH", body[:PRIMARY_HEADER_LEN])
        packet_type = (word0 >> 12) & 0x1
        apid = word0 & 0x7FF
        sequence_count = word1 & 0x3FFF

        coarse, fine = struct.unpack(">II", body[PRIMARY_HEADER_LEN:HEADER_LEN])
        timestamp = coarse + fine / 1_000_000

        payload = body[HEADER_LEN:]
        if data_length != SECONDARY_HEADER_LEN + len(payload) - 1:
            raise ValueError("packet data length field mismatch")

        return cls(apid=apid, packet_type=packet_type, sequence_count=sequence_count,
                    timestamp=timestamp, payload=payload)
