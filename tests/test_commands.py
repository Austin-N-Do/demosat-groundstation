import struct
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.ccsds import TC, TM, SpacePacket
from shared.dictionary import TelemetryDictionary
from spacecraft.command_handler import (
    STATUS_EXECUTED,
    STATUS_REJECTED,
    CommandHandler,
    build_ack_payload,
)
from spacecraft.subsystems import thermal
from spacecraft.subsystems.obc import ObcState

DICTIONARY_PATH = Path(__file__).resolve().parents[1] / "config" / "telemetry_dictionary.yaml"


@pytest.fixture(scope="module")
def dictionary() -> TelemetryDictionary:
    return TelemetryDictionary.load(DICTIONARY_PATH)


@pytest.fixture
def harness(dictionary):
    """CommandHandler wired to fresh state, capturing ACKs instead of sending."""
    state = ObcState()
    acks = []
    handler = CommandHandler(dictionary, state, lambda *a: acks.append(a))
    return handler, state, acks


def _uplink(cmd_id: int, arg: int, seq: int = 7) -> bytes:
    return SpacePacket(
        apid=200, packet_type=TC, sequence_count=seq,
        timestamp=time.time(), payload=struct.pack(">HH", cmd_id, arg),
    ).encode()


# ── SET_MODE ────────────────────────────────────────────────────────────────

def test_set_mode_executes_and_changes_mode(harness):
    handler, state, acks = harness
    handler.datagram_received(_uplink(1, 2), ("ground", 1))   # SET_MODE SCIENCE

    assert state.mode == "SCIENCE"
    assert state.cmds_accepted == 1
    assert state.cmds_rejected == 0
    assert acks == [(1, STATUS_EXECUTED, 7)]


def test_set_mode_rejects_out_of_range_argument(harness):
    handler, state, acks = harness
    handler.datagram_received(_uplink(1, 9), ("ground", 1))

    assert state.mode == "NOMINAL"          # unchanged
    assert state.cmds_rejected == 1
    assert acks == [(1, STATUS_REJECTED, 7)]


# ── TOGGLE_HEATER — a command with an observable telemetry effect ───────────

def test_toggle_heater_warms_the_battery(harness):
    handler, state, acks = harness
    t = 1000.0
    before = thermal.sample(t, heater_on=state.heater_on)["thermal.battery_temp"]

    handler.datagram_received(_uplink(2, 1), ("ground", 1))    # TOGGLE_HEATER ON

    assert state.heater_on is True
    assert acks[-1][1] == STATUS_EXECUTED
    after = thermal.sample(t, heater_on=state.heater_on)["thermal.battery_temp"]
    assert after == pytest.approx(before + thermal.HEATER_DELTA_C)


def test_toggle_heater_off_returns_to_baseline(harness):
    handler, state, _ = harness
    handler.datagram_received(_uplink(2, 1), ("ground", 1))
    handler.datagram_received(_uplink(2, 0), ("ground", 1))
    assert state.heater_on is False


# ── Rejection paths ─────────────────────────────────────────────────────────

def test_unknown_command_id_is_rejected(harness):
    handler, state, acks = harness
    handler.datagram_received(_uplink(99, 0), ("ground", 1))

    assert state.cmds_rejected == 1
    assert acks == [(99, STATUS_REJECTED, 7)]


def test_corrupted_uplink_is_dropped_without_ack(harness):
    handler, state, acks = harness
    wire = bytearray(_uplink(1, 1))
    wire[8] ^= 0xFF     # break the CRC

    handler.datagram_received(bytes(wire), ("ground", 1))

    # Unacknowledgeable: the header can't be trusted to name a command.
    assert acks == []
    assert state.cmds_accepted == 0
    assert state.cmds_rejected == 0


def test_telemetry_packet_on_the_uplink_is_ignored(harness):
    handler, _state, acks = harness
    tm = SpacePacket(apid=100, packet_type=TM, sequence_count=1,
                     timestamp=time.time(), payload=b"\x00" * 16).encode()

    handler.datagram_received(tm, ("ground", 1))
    assert acks == []


# ── ACK correlation carries the commanding sequence count ──────────────────

def test_ack_payload_round_trips_through_the_dictionary(dictionary):
    ack_def = dictionary.packets_by_name["cmd_ack"]
    payload = build_ack_payload(ack_def, cmd_id=2, status=STATUS_EXECUTED, seq_of_command=1234)

    decoded = ack_def.decode_payload(payload)
    assert decoded["cmd_ack.cmd_id"] == 2
    assert decoded["cmd_ack.status"] == "EXECUTED"       # enum resolved by the dictionary
    assert decoded["cmd_ack.seq_of_command"] == 1234


def test_ack_echoes_the_sequence_of_the_command_it_answers(harness):
    handler, _state, acks = harness
    handler.datagram_received(_uplink(1, 0, seq=4095), ("ground", 1))
    handler.datagram_received(_uplink(1, 0, seq=4096), ("ground", 1))

    assert [a[2] for a in acks] == [4095, 4096]
