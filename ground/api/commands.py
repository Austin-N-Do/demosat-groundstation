"""Command uplink — validates a command against the telemetry dictionary,
encodes it as a CCSDS telecommand, sends it to the spacecraft over UDP, and
correlates the acknowledgement that comes back as APID 105 telemetry.

Correlation is on (cmd_id, sequence_count) rather than cmd_id alone, so
sending the same command twice in quick succession can't cross the wires.
"""

from __future__ import annotations

import logging
import os
import socket
import struct
import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ground.api.dictionary_api import get_dictionary
from shared.ccsds import TC, SpacePacket

logger = logging.getLogger("api.commands")

router = APIRouter()

TC_APID = 200
SPACECRAFT_HOST = os.environ.get("SPACECRAFT_HOST", "spacecraft")
TC_PORT = int(os.environ.get("TC_PORT", "10025"))
ACK_TIMEOUT_S = 5.0

STATUS_NAMES = {0: "ACCEPTED", 1: "REJECTED", 2: "EXECUTED"}


class CommandIn(BaseModel):
    id: int
    arg: int = 0


class CommandRegistry:
    """In-memory record of commands sent this process and their ACK state."""

    def __init__(self) -> None:
        self._records: dict = {}     # command_uuid -> record
        self._pending: dict = {}     # (cmd_id, seq) -> command_uuid
        self._seq = 0

    def next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) % 16384   # 14-bit CCSDS sequence field
        return seq

    def register(self, cmd_id: int, name: str, arg: int, seq: int) -> str:
        command_uuid = str(uuid.uuid4())
        self._records[command_uuid] = {
            "command_id": command_uuid, "id": cmd_id, "name": name, "arg": arg,
            "seq": seq, "status": "PENDING", "sent_at": time.time(), "acked_at": None,
        }
        self._pending[(cmd_id, seq)] = command_uuid
        return command_uuid

    def record_ack(self, cmd_id: int, status: str, seq_of_command: int) -> None:
        command_uuid = self._pending.pop((cmd_id, seq_of_command), None)
        if command_uuid is None:
            logger.debug("unmatched ACK cmd_id=%s seq=%s", cmd_id, seq_of_command)
            return
        record = self._records[command_uuid]
        record["status"] = status
        record["acked_at"] = time.time()
        logger.info("command %s (%s) -> %s", command_uuid, record["name"], status)

    def get(self, command_uuid: str):
        record = self._records.get(command_uuid)
        if record is None:
            return None
        return self._with_timeout(record)

    def recent(self, limit: int = 20) -> list:
        records = sorted(self._records.values(), key=lambda r: r["sent_at"], reverse=True)
        return [self._with_timeout(r) for r in records[:limit]]

    def _with_timeout(self, record: dict) -> dict:
        """A command still PENDING past the ACK window is reported TIMEOUT —
        evaluated on read so no background task is needed."""
        if record["status"] == "PENDING" and time.time() - record["sent_at"] > ACK_TIMEOUT_S:
            record["status"] = "TIMEOUT"
            self._pending.pop((record["id"], record["seq"]), None)
        return record


registry = CommandRegistry()

_socket = None


def _get_socket():
    global _socket
    if _socket is None:
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return _socket


@router.post("/api/commands")
async def post_command(body: CommandIn):
    dictionary = get_dictionary()
    command = dictionary.commands_by_id.get(body.id)
    if command is None:
        raise HTTPException(400, f"unknown command id {body.id}")

    arg_enum = command.get("arg_enum") or {}
    if arg_enum and body.arg not in arg_enum:
        raise HTTPException(400, f"argument {body.arg} not valid for {command['name']}")

    seq = registry.next_seq()
    packet = SpacePacket(
        apid=TC_APID, packet_type=TC, sequence_count=seq,
        timestamp=time.time(), payload=struct.pack(">HH", body.id, body.arg),
    )
    try:
        _get_socket().sendto(packet.encode(), (SPACECRAFT_HOST, TC_PORT))
    except OSError as e:
        raise HTTPException(503, f"uplink unavailable: {e}")

    command_uuid = registry.register(body.id, command["name"], body.arg, seq)
    logger.info("uplinked %s(%s) seq=%d as %s", command["name"], body.arg, seq, command_uuid)
    return registry.get(command_uuid)


@router.get("/api/commands")
async def list_commands():
    return registry.recent()


@router.get("/api/commands/{command_id}")
async def get_command(command_id: str):
    record = registry.get(command_id)
    if record is None:
        raise HTTPException(404, "unknown command id")
    return record
