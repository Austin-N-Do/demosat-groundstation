"""Yellow/red limit checking against the dictionary's per-parameter limits,
plus alarm-transition tracking (an alarm event is only emitted when a
parameter's alarm state actually changes, not on every tick)."""

from __future__ import annotations


def evaluate_limit(value, limits: dict) -> str:
    """NOMINAL/YELLOW/RED for one value. Boundaries are inclusive: a value
    exactly AT a threshold counts as having crossed it. Non-numeric values
    (enums decode to their string label) and parameters with no limits are
    always NOMINAL."""
    if limits is None or not isinstance(value, (int, float)):
        return "NOMINAL"

    red_low = limits.get("red_low")
    if red_low is not None and value <= red_low:
        return "RED"
    red_high = limits.get("red_high")
    if red_high is not None and value >= red_high:
        return "RED"

    yellow_low = limits.get("yellow_low")
    if yellow_low is not None and value <= yellow_low:
        return "YELLOW"
    yellow_high = limits.get("yellow_high")
    if yellow_high is not None and value >= yellow_high:
        return "YELLOW"

    return "NOMINAL"


class LimitsEngine:
    """Evaluates every parameter in a decoded packet and reports which ones
    changed alarm state since the last time they were seen."""

    def __init__(self) -> None:
        self._last_alarm: dict = {}   # parameter key -> last-seen alarm

    def evaluate(self, packet_def, parameters: dict) -> tuple:
        """Returns (evaluated, transitions):
        evaluated: {key: {"value": v, "alarm": "NOMINAL"|"YELLOW"|"RED"}}
        transitions: [(key, new_alarm), ...] for keys whose alarm changed."""
        evaluated = {}
        transitions = []
        for p in packet_def.parameters:
            value = parameters.get(p.key)
            alarm = evaluate_limit(value, p.limits)
            evaluated[p.key] = {"value": value, "alarm": alarm}
            if self._last_alarm.get(p.key) != alarm:
                transitions.append((p.key, alarm))
            self._last_alarm[p.key] = alarm
        return evaluated, transitions
