"""Attitude Determination and Control System — three-axis gyro rates and
reaction wheel speed for a nominally three-axis-stabilized spacecraft
(small jitter, no tumbling)."""

from __future__ import annotations

import math


def sample(t: float) -> dict:
    return {
        "adcs.gyro_x": 0.5 * math.sin(t / 9.0),
        "adcs.gyro_y": 0.4 * math.sin(t / 12.0 + 1.0),
        "adcs.gyro_z": 0.3 * math.sin(t / 15.0 + 2.0),
        "adcs.wheel_rpm": 2500.0 + 700.0 * math.sin(t / 500.0),
    }
