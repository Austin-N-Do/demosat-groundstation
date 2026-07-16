"""COMM — downlink signal strength and transmit power. Signal wanders with
antenna geometry but stays well clear of the dictionary's limit bands under
nominal operation."""

from __future__ import annotations

import math


def sample(t: float) -> dict:
    return {
        "comm.signal_strength_dbm": -65.0 + 15.0 * math.sin(t / 300.0),
        "comm.tx_power": 5.0 + 0.1 * math.sin(t / 40.0),
    }
