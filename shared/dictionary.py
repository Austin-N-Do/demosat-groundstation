"""Loader for config/telemetry_dictionary.yaml — the single source of truth
for packet layout, limits, and commands. Byte offsets are never hand-written:
each PacketDef derives a struct format string from parameter order + type,
so the spacecraft encoder and ground decoder can never drift apart."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TYPE_CODES = {
    "float32": "f",
    "uint8": "B",
    "uint16": "H",
    "uint32": "I",
}


@dataclass
class Parameter:
    key: str
    name: str
    type: str
    units: str = None
    limits: dict = None
    enum: dict = None   # int -> str, e.g. {0: "SAFE", 1: "NOMINAL"}


@dataclass
class PacketDef:
    apid: int
    name: str
    parameters: list = field(default_factory=list)   # list[Parameter]

    @property
    def struct_format(self) -> str:
        return ">" + "".join(TYPE_CODES[p.type] for p in self.parameters)

    def encode_payload(self, values: dict) -> bytes:
        return struct.pack(self.struct_format, *(values[p.key] for p in self.parameters))

    def decode_payload(self, data: bytes) -> dict:
        raw = struct.unpack(self.struct_format, data)
        out = {}
        for p, v in zip(self.parameters, raw):
            if p.enum is not None:
                out[p.key] = p.enum.get(int(v), int(v))
            elif p.type == "float32":
                out[p.key] = round(float(v), 6)
            else:
                out[p.key] = int(v)
        return out


class TelemetryDictionary:
    def __init__(self, spacecraft_name: str, packets: list, commands: list):
        self.spacecraft_name = spacecraft_name
        self.packets = {p.apid: p for p in packets}                # apid -> PacketDef
        self.packets_by_name = {p.name: p for p in packets}         # e.g. "eps" -> PacketDef
        self.commands = commands                                    # list[dict]
        self.commands_by_id = {c["id"]: c for c in commands}
        self.commands_by_name = {c["name"]: c for c in commands}

    @classmethod
    def load(cls, path) -> "TelemetryDictionary":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        packets = []
        for pk in raw["packets"]:
            params = [
                Parameter(
                    key=p["key"], name=p["name"], type=p["type"],
                    units=p.get("units"), limits=p.get("limits"), enum=p.get("enum"),
                )
                for p in pk["parameters"]
            ]
            packets.append(PacketDef(apid=pk["apid"], name=pk["name"], parameters=params))
        return cls(
            spacecraft_name=raw["spacecraft"]["name"],
            packets=packets,
            commands=raw.get("commands", []),
        )
