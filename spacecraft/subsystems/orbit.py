"""Shared orbital clock: a 90-minute LEO-like period with a sun-lit and an
eclipse phase (roughly 60/40, like a real low-Earth orbit). Every other
subsystem samples this instead of keeping its own notion of day/night so
eclipse-driven effects (solar power loss, battery sag, cooling) stay
consistent with each other."""

from __future__ import annotations

import math

ORBIT_PERIOD_S = 90 * 60
ECLIPSE_FRACTION = 0.4   # fraction of the orbit spent in Earth's shadow


def orbit_phase(t: float) -> float:
    """0..1 position within the current orbit."""
    return (t % ORBIT_PERIOD_S) / ORBIT_PERIOD_S


def in_eclipse(t: float) -> bool:
    return orbit_phase(t) < ECLIPSE_FRACTION


def sun_intensity(t: float) -> float:
    """0 during eclipse, smoothly rising/falling near the terminator,
    ~1 at local noon — drives solar array power."""
    phase = orbit_phase(t)
    if phase < ECLIPSE_FRACTION:
        return 0.0
    # Map the sunlit portion of the orbit onto a half sine wave.
    sunlit_phase = (phase - ECLIPSE_FRACTION) / (1 - ECLIPSE_FRACTION)
    return math.sin(math.pi * sunlit_phase)
