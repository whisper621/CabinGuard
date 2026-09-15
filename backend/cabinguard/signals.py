"""VSS-aligned signal catalog and declarative safety constraints.

The segment-glob matching semantics and declarative constraint shape are adapted
from cockpit-agent-sim (MIT), Copyright (c) 2026 yancent. The Python runtime and
CabinGuard-specific rules are implemented for this project. See
THIRD_PARTY_NOTICES.md and licenses/cockpit-agent-sim-MIT.txt.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal

Permission = Literal["direct", "confirm", "blocked"]
ConstraintAction = Literal["reject", "clamp"]
Operator = Literal["eq", "ne", "gt", "gte", "lt", "lte"]


@dataclass(frozen=True)
class SignalDefinition:
    path: str
    alias: str
    label: str
    value_type: str
    access: Literal["read", "write", "read_write"]
    permission: Permission
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    values: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value not in (None, ())}


@dataclass(frozen=True)
class Condition:
    path: str
    operator: Operator
    value: object


@dataclass(frozen=True)
class ConstraintDefinition:
    id: str
    target_pattern: str
    conditions: tuple[Condition, ...]
    action: ConstraintAction
    code: str
    message: str
    suggestion: str
    clamp_max: float | None = None

    def public_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["targetPattern"] = result.pop("target_pattern")
        result["clampMax"] = result.pop("clamp_max")
        return {key: value for key, value in result.items() if value is not None}


@dataclass(frozen=True)
class ConstraintDecision:
    allowed: bool
    value: object
    action: Literal["allow", "reject", "clamp"]
    constraint_id: str | None = None
    code: str | None = None
    message: str | None = None
    suggestion: str | None = None


SIGNALS: tuple[SignalDefinition, ...] = (
    SignalDefinition("Vehicle.Speed", "speed", "车速", "number", "read", "direct", "km/h", 0, 260),
    SignalDefinition("Vehicle.Powertrain.Transmission.CurrentGear", "gear", "当前挡位", "enum", "read", "direct", values=("P", "R", "N", "D")),
    SignalDefinition("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current", "battery", "动力电池电量", "number", "read", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Powertrain.Range", "range", "预计续航", "number", "read", "direct", "km", 0, 1500),
    SignalDefinition("Vehicle.Cabin.HVAC.AmbientAirTemperature", "cabinTemperature", "车内温度", "number", "read", "direct", "°C", -40, 80),
    SignalDefinition("Vehicle.Cabin.HVAC.Station.Row1.Left.Temperature", "targetTemperature", "空调设定温度", "number", "read_write", "direct", "°C", 16, 30),
    SignalDefinition("Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed", "fanLevel", "空调风量", "integer", "read_write", "direct", None, 1, 5),
    SignalDefinition("Vehicle.Cabin.HVAC.IsRecirculationActive", "circulation", "内外循环", "enum", "read_write", "direct", values=("内循环", "外循环")),
    SignalDefinition("Vehicle.Cabin.Sunroof.Position", "sunroof", "天窗开度", "integer", "read_write", "confirm", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Sunroof.Shade.Position", "sunshade", "遮阳帘开度", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Door.Row1.DriverSide.Window.Position", "windows.driver", "主驾车窗", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Door.Row1.PassengerSide.Window.Position", "windows.passenger", "副驾车窗", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Door.Row2.DriverSide.Window.Position", "windows.rearLeft", "左后车窗", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Door.Row2.PassengerSide.Window.Position", "windows.rearRight", "右后车窗", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Cabin.Door.Row1.DriverSide.IsOpen", "doors.driver", "主驾车门", "boolean", "read_write", "confirm"),
    SignalDefinition("Vehicle.Cabin.Door.Row1.PassengerSide.IsOpen", "doors.passenger", "副驾车门", "boolean", "read_write", "confirm"),
    SignalDefinition("Vehicle.Cabin.Door.Row2.DriverSide.IsOpen", "doors.rearLeft", "左后车门", "boolean", "read_write", "confirm"),
    SignalDefinition("Vehicle.Cabin.Door.Row2.PassengerSide.IsOpen", "doors.rearRight", "右后车门", "boolean", "read_write", "confirm"),
    SignalDefinition("Vehicle.Cabin.Seat.Row1.DriverSide.Heating", "seats.driverHeating", "主驾座椅加热", "integer", "read_write", "direct", None, 0, 3),
    SignalDefinition("Vehicle.Cabin.Seat.Row1.PassengerSide.Heating", "seats.passengerHeating", "副驾座椅加热", "integer", "read_write", "direct", None, 0, 3),
    SignalDefinition("Vehicle.Cabin.Seat.Row1.DriverSide.Ventilation", "seats.driverVentilation", "主驾座椅通风", "integer", "read_write", "direct", None, 0, 3),
    SignalDefinition("Vehicle.Cabin.Seat.Row1.PassengerSide.Ventilation", "seats.passengerVentilation", "副驾座椅通风", "integer", "read_write", "direct", None, 0, 3),
    SignalDefinition("Vehicle.Cabin.Light.AmbientLight.IsOn", "ambientLight.enabled", "氛围灯", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Light.AmbientLight.Intensity", "ambientLight.brightness", "氛围灯亮度", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Vehicle.Body.Windshield.Front.IsHeatingOn", "defrost.front", "前风挡除霜", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Body.Windshield.Rear.IsHeatingOn", "defrost.rear", "后风挡除霜", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Door.Row2.ChildLock", "childLock", "后排儿童锁", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Body.Trunk.Rear.IsOpen", "trunkOpen", "后备箱", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Body.ChargePort.IsOpen", "chargePortOpen", "充电口盖", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Body.Windshield.Wiper.Mode", "wiperMode", "雨刷模式", "enum", "read_write", "direct", values=("off", "auto", "slow", "medium", "high")),
    SignalDefinition("Vehicle.Cabin.Mirror.Driver.IsFolded", "mirrors.driverFolded", "主驾后视镜折叠", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Mirror.Passenger.IsFolded", "mirrors.passengerFolded", "副驾后视镜折叠", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Mirror.Driver.Heating", "mirrors.driverHeating", "主驾后视镜加热", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Mirror.Passenger.Heating", "mirrors.passengerHeating", "副驾后视镜加热", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.AirQuality.PM25", "airQuality.pm25", "车内 PM2.5", "integer", "read", "direct", "μg/m³", 0, 999),
    SignalDefinition("Vehicle.Cabin.AirQuality.Purifier.IsOn", "airQuality.purifierEnabled", "空气净化器", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.AirQuality.Purifier.Level", "airQuality.purifierLevel", "净化器挡位", "integer", "read_write", "direct", None, 0, 3),
    SignalDefinition("Vehicle.Cabin.Fragrance.Mode", "airQuality.fragrance", "座舱香氛", "enum", "read_write", "direct", values=("off", "forest", "ocean", "citrus")),
    SignalDefinition("Vehicle.Cabin.Infotainment.Media.IsPlaying", "media.playing", "媒体播放状态", "boolean", "read_write", "direct"),
    SignalDefinition("Vehicle.Cabin.Infotainment.Media.Volume", "media.volume", "媒体音量", "integer", "read_write", "direct", "%", 0, 100),
    SignalDefinition("Environment.Weather.RainProbability", "rainProbability", "降雨概率", "number", "read", "direct", "%", 0, 100),
)


CONSTRAINTS: tuple[ConstraintDefinition, ...] = (
    ConstraintDefinition(
        id="window-high-speed-clamp",
        target_pattern="Vehicle.Cabin.Door.*.*.Window.Position",
        conditions=(Condition("Vehicle.Speed", "gt", 100), Condition("$target", "gt", 30)),
        action="clamp",
        clamp_max=30,
        code="window_position_clamped_at_high_speed",
        message="车速超过 100 km/h，车窗开度已限制为 30%",
        suggestion="降低车速后可继续开启车窗",
    ),
    ConstraintDefinition(
        id="rear-window-child-lock",
        target_pattern="Vehicle.Cabin.Door.Row2.*.Window.Position",
        conditions=(Condition("Vehicle.Cabin.Door.Row2.ChildLock", "eq", True), Condition("$target", "gt", 0)),
        action="reject",
        code="rear_window_blocked_by_child_lock",
        message="后排儿童锁已开启，不能打开后排车窗",
        suggestion="由驾驶员关闭儿童锁后重试",
    ),
    ConstraintDefinition(
        id="trunk-park-only",
        target_pattern="Vehicle.Body.Trunk.Rear.IsOpen",
        conditions=(Condition("Vehicle.Powertrain.Transmission.CurrentGear", "ne", "P"), Condition("$target", "eq", True)),
        action="reject",
        code="trunk_requires_park",
        message="后备箱只能在 P 挡开启",
        suggestion="停车并切换到 P 挡后重试",
    ),
    ConstraintDefinition(
        id="door-moving-lock",
        target_pattern="Vehicle.Cabin.Door.*.*.IsOpen",
        conditions=(Condition("Vehicle.Speed", "gt", 0), Condition("$target", "eq", True)),
        action="reject",
        code="door_blocked_while_moving",
        message="车辆仍在行驶，禁止开启车门",
        suggestion="停车并切换到 P 挡后重试",
    ),
    ConstraintDefinition(
        id="door-park-only",
        target_pattern="Vehicle.Cabin.Door.*.*.IsOpen",
        conditions=(Condition("Vehicle.Powertrain.Transmission.CurrentGear", "ne", "P"), Condition("$target", "eq", True)),
        action="reject",
        code="door_requires_park",
        message="车门只能在 P 挡开启",
        suggestion="停车并切换到 P 挡后重试",
    ),
    ConstraintDefinition(
        id="rear-door-child-lock",
        target_pattern="Vehicle.Cabin.Door.Row2.*.IsOpen",
        conditions=(Condition("Vehicle.Cabin.Door.Row2.ChildLock", "eq", True), Condition("$target", "eq", True)),
        action="reject",
        code="rear_door_blocked_by_child_lock",
        message="后排儿童锁已开启，不能打开后排车门",
        suggestion="由驾驶员关闭儿童锁后重试",
    ),
    ConstraintDefinition(
        id="charge-port-park-only",
        target_pattern="Vehicle.Body.ChargePort.IsOpen",
        conditions=(Condition("Vehicle.Powertrain.Transmission.CurrentGear", "ne", "P"), Condition("$target", "eq", True)),
        action="reject",
        code="charge_port_requires_park",
        message="充电口只能在 P 挡开启",
        suggestion="停车并切换到 P 挡后重试",
    ),
    ConstraintDefinition(
        id="sunroof-rain-lock",
        target_pattern="Vehicle.Cabin.Sunroof.Position",
        conditions=(Condition("Environment.Weather.RainProbability", "gte", 50), Condition("$target", "gt", 0)),
        action="reject",
        code="sunroof_blocked_by_rain",
        message="降雨概率不低于 50%，禁止开启天窗",
        suggestion="雨停或降雨概率降低后重试",
    ),
    ConstraintDefinition(
        id="low-battery-fan-clamp",
        target_pattern="Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed",
        conditions=(Condition("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current", "lt", 10), Condition("$target", "gt", 3)),
        action="clamp",
        clamp_max=3,
        code="fan_level_clamped_for_low_battery",
        message="电量低于 10%，空调风量已限制为 3 挡",
        suggestion="充电后可使用更高风量",
    ),
)


@lru_cache(maxsize=256)
def _glob_regex(pattern: str) -> re.Pattern[str]:
    escaped_segments = [re.escape(segment).replace(r"\*", "[^.]*") for segment in pattern.split(".")]
    return re.compile(r"^" + r"\.".join(escaped_segments) + r"$")


def segment_glob_match(pattern: str, path: str) -> bool:
    """Match `*` within a single dot-delimited signal segment."""

    if pattern == "*":
        return True
    return bool(_glob_regex(pattern).match(path))


def _compare(actual: object, operator: Operator, expected: object) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return isinstance(actual, (int, float)) and actual > expected  # type: ignore[operator]
    if operator == "gte":
        return isinstance(actual, (int, float)) and actual >= expected  # type: ignore[operator]
    if operator == "lt":
        return isinstance(actual, (int, float)) and actual < expected  # type: ignore[operator]
    return isinstance(actual, (int, float)) and actual <= expected  # type: ignore[operator]


def evaluate_write(
    signal_path: str,
    requested_value: object,
    current_signals: dict[str, object],
) -> ConstraintDecision:
    """Apply every matching rule and return a machine-readable decision."""

    value = requested_value
    for constraint in CONSTRAINTS:
        if not segment_glob_match(constraint.target_pattern, signal_path):
            continue
        matches = all(
            _compare(value if condition.path == "$target" else current_signals.get(condition.path), condition.operator, condition.value)
            for condition in constraint.conditions
        )
        if not matches:
            continue
        if constraint.action == "reject":
            return ConstraintDecision(
                allowed=False,
                value=value,
                action="reject",
                constraint_id=constraint.id,
                code=constraint.code,
                message=constraint.message,
                suggestion=constraint.suggestion,
            )
        if constraint.clamp_max is not None and isinstance(value, (int, float)):
            value = min(value, constraint.clamp_max)
            return ConstraintDecision(
                allowed=True,
                value=value,
                action="clamp",
                constraint_id=constraint.id,
                code=constraint.code,
                message=constraint.message,
                suggestion=constraint.suggestion,
            )
    return ConstraintDecision(allowed=True, value=value, action="allow")


def signal_state(*, speed: float, gear: str, battery: float, rain_probability: float, child_lock: bool) -> dict[str, object]:
    return {
        "Vehicle.Speed": speed,
        "Vehicle.Powertrain.Transmission.CurrentGear": gear,
        "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current": battery,
        "Environment.Weather.RainProbability": rain_probability,
        "Vehicle.Cabin.Door.Row2.ChildLock": child_lock,
    }
