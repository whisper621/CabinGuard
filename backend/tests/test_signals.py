from cabinguard.models import VehicleState
from cabinguard.signals import evaluate_write, segment_glob_match, signal_state
from cabinguard.tools import ToolContext, execute_tool


def test_segment_glob_matches_one_vss_path_segment() -> None:
    assert segment_glob_match(
        "Vehicle.Cabin.Door.*.*.Window.Position",
        "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position",
    )
    assert not segment_glob_match(
        "Vehicle.Cabin.Door.Row2.*.Window.Position",
        "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position",
    )


def test_high_speed_window_rule_clamps_real_tool_execution() -> None:
    vehicle = VehicleState(speed=120, gear="D")
    result = execute_tool(
        "control_cabin_device",
        {"device": "window", "zone": "driver", "action": "set_position", "value": 80},
        vehicle,
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "success"
    assert result.vehicle.windows.driver == 30
    assert result.output["constraint"]["action"] == "clamp"  # type: ignore[index]


def test_child_lock_rule_rejects_rear_window_write() -> None:
    vehicle = VehicleState(speed=0, gear="P", child_lock=True)
    result = execute_tool(
        "control_cabin_device",
        {"device": "window", "zone": "rear_left", "action": "set_position", "value": 20},
        vehicle,
        ToolContext(prior_successful_tools=("get_vehicle_state",)),
    )
    assert result.status == "blocked"
    assert result.output["code"] == "rear_window_blocked_by_child_lock"


def test_low_battery_rule_clamps_fan_level() -> None:
    vehicle = VehicleState(battery=8)
    result = execute_tool(
        "set_climate",
        {"target_temperature_c": 22, "fan_level": 5, "circulation": "内循环"},
        vehicle,
        ToolContext(prior_successful_tools=("get_climate_state",)),
    )
    assert result.status == "success"
    assert result.vehicle.fan_level == 3
    assert result.output["constraint"]["code"] == "fan_level_clamped_for_low_battery"  # type: ignore[index]


def test_allow_decision_keeps_requested_value() -> None:
    state = signal_state(speed=40, gear="D", battery=50, rain_probability=10, child_lock=False)
    decision = evaluate_write(
        "Vehicle.Cabin.Door.Row1.DriverSide.Window.Position", 50, state
    )
    assert decision.allowed is True
    assert decision.value == 50
    assert decision.action == "allow"
