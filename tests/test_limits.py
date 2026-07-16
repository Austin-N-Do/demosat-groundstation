import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ground.ingest.limits import LimitsEngine, evaluate_limit
from shared.dictionary import Parameter, PacketDef

LIMITS = {"yellow_low": 24.0, "red_low": 22.0, "yellow_high": 33.0, "red_high": 34.5}


def test_nominal_inside_band():
    assert evaluate_limit(28.0, LIMITS) == "NOMINAL"


def test_yellow_low_boundary_inclusive():
    assert evaluate_limit(24.0, LIMITS) == "YELLOW"
    assert evaluate_limit(23.999, LIMITS) == "YELLOW"   # still yellow, not red
    assert evaluate_limit(24.001, LIMITS) == "NOMINAL"


def test_red_low_boundary_inclusive():
    assert evaluate_limit(22.0, LIMITS) == "RED"
    assert evaluate_limit(21.999, LIMITS) == "RED"
    assert evaluate_limit(22.001, LIMITS) == "YELLOW"


def test_yellow_high_boundary_inclusive():
    assert evaluate_limit(33.0, LIMITS) == "YELLOW"
    assert evaluate_limit(32.999, LIMITS) == "NOMINAL"


def test_red_high_boundary_inclusive():
    assert evaluate_limit(34.5, LIMITS) == "RED"
    assert evaluate_limit(34.499, LIMITS) == "YELLOW"


def test_no_limits_always_nominal():
    assert evaluate_limit(999999.0, None) == "NOMINAL"


def test_non_numeric_value_always_nominal():
    # Enum parameters decode to their string label (e.g. "SAFE") — limits
    # never apply even if the dictionary happened to define them.
    assert evaluate_limit("SAFE", LIMITS) == "NOMINAL"


def _eps_packet_def():
    return PacketDef(apid=100, name="eps", parameters=[
        Parameter(key="eps.battery_voltage", name="Battery Voltage", type="float32",
                  units="V", limits=LIMITS),
        Parameter(key="eps.bus_5v", name="5V Bus", type="float32", units="V", limits=None),
    ])


def test_evaluate_returns_value_and_alarm_per_parameter():
    engine = LimitsEngine()
    evaluated, _ = engine.evaluate(_eps_packet_def(), {"eps.battery_voltage": 20.0, "eps.bus_5v": 5.0})
    assert evaluated == {
        "eps.battery_voltage": {"value": 20.0, "alarm": "RED"},
        "eps.bus_5v": {"value": 5.0, "alarm": "NOMINAL"},
    }


def test_transition_only_reported_on_change():
    engine = LimitsEngine()
    packet_def = _eps_packet_def()

    _, transitions1 = engine.evaluate(packet_def, {"eps.battery_voltage": 28.0, "eps.bus_5v": 5.0})
    assert ("eps.battery_voltage", "NOMINAL") in transitions1   # first sighting is a transition

    _, transitions2 = engine.evaluate(packet_def, {"eps.battery_voltage": 27.5, "eps.bus_5v": 5.0})
    assert transitions2 == []   # still NOMINAL, no transition

    _, transitions3 = engine.evaluate(packet_def, {"eps.battery_voltage": 20.0, "eps.bus_5v": 5.0})
    assert transitions3 == [("eps.battery_voltage", "RED")]
