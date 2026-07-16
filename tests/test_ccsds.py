import struct
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.ccsds import TC, TM, CRCError, SpacePacket
from shared.crc import crc16_ccitt
from shared.dictionary import TelemetryDictionary

DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "config" / "telemetry_dictionary.yaml"


@pytest.fixture(scope="module")
def dictionary() -> TelemetryDictionary:
    return TelemetryDictionary.load(DICTIONARY_PATH)


def _sample_values(packet_def) -> dict:
    """One plausible value per parameter, respecting enum/int/float typing."""
    values = {}
    for p in packet_def.parameters:
        if p.enum is not None:
            values[p.key] = next(iter(p.enum))          # first enum int value
        elif p.type == "float32":
            values[p.key] = 12.5
        else:
            values[p.key] = 7
    return values


# ── CRC known-answer test ───────────────────────────────────────────────────

def test_crc16_known_vector():
    assert crc16_ccitt(b"123456789") == 0x29B1


# ── CCSDS round trip, every APID in the dictionary ─────────────────────────

def test_round_trip_every_apid(dictionary):
    now = time.time()
    for apid, packet_def in dictionary.packets.items():
        values = _sample_values(packet_def)
        payload = packet_def.encode_payload(values)
        pkt = SpacePacket(apid=apid, packet_type=TM, sequence_count=42, timestamp=now, payload=payload)
        wire = pkt.encode()

        decoded = SpacePacket.decode(wire)
        assert decoded.apid == apid
        assert decoded.packet_type == TM
        assert decoded.sequence_count == 42
        assert decoded.payload == payload
        assert decoded.timestamp == pytest.approx(now, abs=1e-6)

        decoded_values = packet_def.decode_payload(decoded.payload)
        for key, val in values.items():
            if isinstance(val, float):
                assert decoded_values[key] == pytest.approx(val)
            elif packet_def.parameters[[p.key for p in packet_def.parameters].index(key)].enum:
                continue   # enum ints decode to their string label, checked separately below
            else:
                assert decoded_values[key] == val


def test_round_trip_decodes_enum_to_label(dictionary):
    obc = dictionary.packets_by_name["obc"]
    values = {"obc.mode": 2, "obc.uptime": 100, "obc.cmds_accepted": 1, "obc.cmds_rejected": 0}
    decoded = obc.decode_payload(obc.encode_payload(values))
    assert decoded["obc.mode"] == "SCIENCE"


# ── CRC failure on corruption ───────────────────────────────────────────────

def test_corrupted_byte_fails_crc(dictionary):
    packet_def = dictionary.packets_by_name["eps"]
    payload = packet_def.encode_payload(_sample_values(packet_def))
    pkt = SpacePacket(apid=100, packet_type=TM, sequence_count=1, timestamp=time.time(), payload=payload)
    wire = bytearray(pkt.encode())
    wire[7] ^= 0xFF   # flip a payload byte (past the 14-byte header)

    with pytest.raises(CRCError):
        SpacePacket.decode(bytes(wire))


def test_too_short_packet_raises():
    with pytest.raises(ValueError):
        SpacePacket.decode(b"\x00" * 10)


# ── Sequence-count 14-bit wraparound ────────────────────────────────────────

def test_sequence_count_wraps_at_16384():
    pkt = SpacePacket(apid=100, packet_type=TM, sequence_count=16383, timestamp=1.0, payload=b"\x00" * 4)
    wire = pkt.encode()
    decoded = SpacePacket.decode(wire)
    assert decoded.sequence_count == 16383

    # Encoding 16384 (one past max) wraps to 0 in the 14-bit field — the
    # link_monitor gap-detection logic (tests/test_link_monitor.py) is what
    # has to handle this transition, not the packet codec itself.
    pkt2 = SpacePacket(apid=100, packet_type=TM, sequence_count=16384, timestamp=1.0, payload=b"\x00" * 4)
    decoded2 = SpacePacket.decode(pkt2.encode())
    assert decoded2.sequence_count == 0


def test_tc_packet_type_round_trips():
    payload = struct.pack(">HH", 1, 2)   # cmd_id=1, arg=2
    pkt = SpacePacket(apid=200, packet_type=TC, sequence_count=5, timestamp=time.time(), payload=payload)
    decoded = SpacePacket.decode(pkt.encode())
    assert decoded.packet_type == TC
    assert decoded.apid == 200
    assert struct.unpack(">HH", decoded.payload) == (1, 2)
