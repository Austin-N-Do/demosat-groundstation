"""Electrical Power System — battery, solar array, regulated bus. Modeled
as a pure function of mission-elapsed time so every sample is reproducible:
battery voltage sags through eclipse (no solar charging) and recovers
through the sunlit part of the orbit, floor tuned to occasionally cross
into the dictionary's YELLOW band once per orbit (config/telemetry_dictionary.yaml)."""

from __future__ import annotations

import math

from spacecraft.subsystems.orbit import ECLIPSE_FRACTION, orbit_phase, sun_intensity

V_FULL = 27.6            # battery voltage at the start of eclipse (fully charged)
ECLIPSE_DROP_V = 4.0      # sag over a full eclipse -> floor ~23.6V (dips into YELLOW)
BUS_LOAD_A = 1.8          # constant load drawn by the spacecraft bus
SOLAR_MAX_A = 3.2         # panel current at full sun intensity
SOLAR_MAX_W = 160.0


def sample(t: float) -> dict:
    phase = orbit_phase(t)
    if phase < ECLIPSE_FRACTION:
        eclipse_frac = phase / ECLIPSE_FRACTION          # 0 (just entered) -> 1 (about to exit)
        voltage = V_FULL - ECLIPSE_DROP_V * eclipse_frac
        current = -BUS_LOAD_A
    else:
        sun_frac = (phase - ECLIPSE_FRACTION) / (1 - ECLIPSE_FRACTION)
        voltage = (V_FULL - ECLIPSE_DROP_V) + ECLIPSE_DROP_V * sun_frac
        current = sun_intensity(t) * SOLAR_MAX_A - BUS_LOAD_A

    voltage += 0.05 * math.sin(t / 13.0)   # small deterministic ripple

    return {
        "eps.battery_voltage": voltage,
        "eps.battery_current": current,
        "eps.solar_array_power": sun_intensity(t) * SOLAR_MAX_W,
        "eps.bus_5v": 5.0 + 0.02 * math.sin(t / 7.0),
    }
