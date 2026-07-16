"""Thermal — component temperatures coupled to the orbital eclipse state
(shared with eps.py via orbit.py so heating/cooling stays consistent with
the solar/battery cycle)."""

from __future__ import annotations

import math

from spacecraft.subsystems.orbit import sun_intensity


def sample(t: float) -> dict:
    sun = sun_intensity(t)
    return {
        "thermal.battery_temp": 5.0 + 20.0 * sun + 1.5 * math.sin(t / 17.0),
        "thermal.obc_temp": 25.0 + 8.0 * sun + 1.0 * math.sin(t / 11.0),
        "thermal.radiator_temp": -15.0 + 10.0 * sun,
    }
