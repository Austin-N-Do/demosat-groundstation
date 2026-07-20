"""Telecommand uplink — receives CCSDS TC packets (APID 200) from the ground,
executes them against spacecraft state, and emits a command-acknowledgement
telemetry packet (APID 105) back down the normal downlink.

The ACK carries the sequence count of the command it answers, not just the
command id, so the ground can correlate acknowledgements unambiguously even
when the same command is sent twice in quick succession.
"""

from __future__ import annotations

import asyncio
import logging
import struct

from shared.ccsds import TC, SpacePacket

logger = logging.getLogger("spacecraft.command")

TC_APID = 200
ACK_APID = 105

# cmd_ack.status enumeration (see config/telemetry_dictionary.yaml)
STATUS_ACCEPTED = 0
STATUS_REJECTED = 1
STATUS_EXECUTED = 2

TC_PAYLOAD = ">HH"   # cmd_id, arg


class CommandHandler(asyncio.DatagramProtocol):
    def __init__(self, dictionary, obc_state, send_ack) -> None:
        self.dictionary = dictionary
        self.obc_state = obc_state
        self.send_ack = send_ack   # (cmd_id, status, seq_of_command) -> None

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            pkt = SpacePacket.decode(data)
        except Exception as e:
            # A corrupted uplink is unacknowledgeable: without a trustworthy
            # header we don't know which command to reference in the ACK.
            logger.warning("undecodable telecommand from %s: %s", addr, e)
            return

        if pkt.packet_type != TC or pkt.apid != TC_APID:
            logger.warning("ignoring non-telecommand packet apid=%d type=%d", pkt.apid, pkt.packet_type)
            return

        try:
            cmd_id, arg = struct.unpack(TC_PAYLOAD, pkt.payload)
        except struct.error:
            logger.warning("malformed telecommand payload (%d bytes)", len(pkt.payload))
            return

        status = self._execute(cmd_id, arg)
        if status == STATUS_EXECUTED:
            self.obc_state.cmds_accepted += 1
        else:
            self.obc_state.cmds_rejected += 1

        logger.info("RX CMD id=%d arg=%d seq=%d -> %s",
                    cmd_id, arg, pkt.sequence_count,
                    "EXECUTED" if status == STATUS_EXECUTED else "REJECTED")
        self.send_ack(cmd_id, status, pkt.sequence_count)

    def _execute(self, cmd_id: int, arg: int) -> int:
        command = self.dictionary.commands_by_id.get(cmd_id)
        if command is None:
            logger.warning("unknown command id %d", cmd_id)
            return STATUS_REJECTED

        arg_enum = command.get("arg_enum") or {}
        if arg_enum and arg not in arg_enum:
            logger.warning("argument %d out of range for %s", arg, command["name"])
            return STATUS_REJECTED

        name = command["name"]
        if name == "SET_MODE":
            self.obc_state.mode = arg_enum[arg]
            return STATUS_EXECUTED
        if name == "TOGGLE_HEATER":
            self.obc_state.heater_on = arg_enum[arg] == "ON"
            return STATUS_EXECUTED

        # Defined in the dictionary but not implemented here.
        logger.warning("command %s has no handler", name)
        return STATUS_REJECTED


def build_ack_payload(packet_def, cmd_id: int, status: int, seq_of_command: int) -> bytes:
    return packet_def.encode_payload({
        "cmd_ack.cmd_id": cmd_id,
        "cmd_ack.status": status,
        "cmd_ack.seq_of_command": seq_of_command,
    })
