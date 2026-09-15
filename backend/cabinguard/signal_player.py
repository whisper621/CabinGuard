"""Deterministic VSS-style temporal events for the digital-twin lab."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import VehicleState

SignalEventName = Literal[
    "urban_drive", "highway_drive", "park", "rain", "clear_weather", "low_battery", "windshield_visibility_low", "reset"
]


@dataclass(frozen=True)
class SignalEventResult:
    name: SignalEventName
    label: str
    vehicle: VehicleState
    changed_signals: tuple[str, ...]


EVENT_LABELS: dict[SignalEventName, str] = {
    "urban_drive": "进入城市道路",
    "highway_drive": "进入高速道路",
    "park": "车辆安全驻车",
    "rain": "降雨事件",
    "clear_weather": "天气转晴",
    "low_battery": "低电量事件",
    "windshield_visibility_low": "视觉感知：前风挡可视性下降（演示事件）",
    "reset": "恢复默认数字孪生状态",
}


def apply_signal_event(name: SignalEventName, vehicle: VehicleState) -> SignalEventResult:
    updates: dict[str, object]
    signals: tuple[str, ...]
    if name == "urban_drive":
        updates = {"speed": 35, "gear": "D"}
        signals = ("Vehicle.Speed", "Vehicle.Powertrain.Transmission.CurrentGear")
    elif name == "highway_drive":
        updates = {"speed": 92, "gear": "D"}
        signals = ("Vehicle.Speed", "Vehicle.Powertrain.Transmission.CurrentGear")
    elif name == "park":
        updates = {"speed": 0, "gear": "P"}
        signals = ("Vehicle.Speed", "Vehicle.Powertrain.Transmission.CurrentGear")
    elif name == "rain":
        updates = {"weather": "中雨", "rain_probability": 88}
        signals = ("Environment.Weather.Condition", "Environment.Weather.RainProbability")
    elif name == "clear_weather":
        updates = {"weather": "晴", "rain_probability": 5}
        signals = ("Environment.Weather.Condition", "Environment.Weather.RainProbability")
    elif name == "low_battery":
        updates = {"battery": 12, "range": 48}
        signals = ("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current", "Vehicle.LowVoltageBattery.CurrentVoltage")
    elif name == "windshield_visibility_low":
        updates = {"perception_event": "windshield_visibility_low"}
        signals = ("PerceptionEventAdapter.windshield_visibility_low",)
    else:
        updates = {
            "speed": 0,
            "gear": "P",
            "battery": 65,
            "range": 310,
            "weather": "多云",
            "rain_probability": 20,
            "perception_event": None,
        }
        signals = (
            "Vehicle.Speed",
            "Vehicle.Powertrain.Transmission.CurrentGear",
            "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
            "Environment.Weather.RainProbability",
        )
    return SignalEventResult(
        name=name,
        label=EVENT_LABELS[name],
        vehicle=vehicle.model_copy(update=updates),
        changed_signals=signals,
    )
