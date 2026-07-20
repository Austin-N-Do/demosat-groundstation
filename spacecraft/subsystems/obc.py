"""On-Board Computer — spacecraft mode, uptime, and command counters. The
one subsystem with real mutable state: mode and the command counters are
changed by command_handler.py when a telecommand executes, so (unlike the
other subsystems) this can't be a pure function of t alone."""

from __future__ import annotations

import time


class ObcState:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.mode = "NOMINAL"
        self.cmds_accepted = 0
        self.cmds_rejected = 0
        # Commanded by TOGGLE_HEATER; read by the thermal subsystem so an
        # uplinked command produces a visible change in downlinked telemetry.
        self.heater_on = False

    _MODE_CODES = {"SAFE": 0, "NOMINAL": 1, "SCIENCE": 2}

    def sample(self, t: float) -> dict:
        return {
            "obc.mode": self._MODE_CODES[self.mode],
            "obc.uptime": max(0, int(t - self.start_time)),
            "obc.cmds_accepted": self.cmds_accepted,
            "obc.cmds_rejected": self.cmds_rejected,
        }
