"""GET /api/dictionary — the telemetry dictionary as JSON, for OpenMCT's
object/composition providers and the command panel to build their trees
and forms from without hand-maintaining a second copy."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from shared.dictionary import TelemetryDictionary

router = APIRouter()

DICTIONARY_PATH = Path(os.environ.get("DICTIONARY_PATH", "/app/config/telemetry_dictionary.yaml"))
_dictionary: TelemetryDictionary = None


def get_dictionary() -> TelemetryDictionary:
    global _dictionary
    if _dictionary is None:
        _dictionary = TelemetryDictionary.load(DICTIONARY_PATH)
    return _dictionary


@router.get("/api/dictionary")
async def dictionary_json():
    d = get_dictionary()
    return {
        "spacecraft_name": d.spacecraft_name,
        "packets": [
            {
                "apid": p.apid,
                "name": p.name,
                "parameters": [
                    {
                        "key": param.key, "name": param.name, "type": param.type,
                        "units": param.units, "limits": param.limits, "enum": param.enum,
                    }
                    for param in p.parameters
                ],
            }
            for p in d.packets.values()
        ],
        "commands": d.commands,
    }
