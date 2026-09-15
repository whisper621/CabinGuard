"""Event-driven, human-approved proactive suggestions.

Suggestions never mutate the vehicle. They expose a recommended next utterance,
which still enters the same TaskPlan, ABAC and tool-policy path as user input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import VehicleState


@dataclass(frozen=True)
class ProactiveSuggestion:
    id: str
    priority: str
    title: str
    message: str
    action_label: str
    prompt: str
    source: str
    requires_human_confirmation: bool = True

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["actionLabel"] = payload.pop("action_label")
        payload["requiresHumanConfirmation"] = payload.pop("requires_human_confirmation")
        return payload


def derive_proactive_suggestions(vehicle: VehicleState) -> list[ProactiveSuggestion]:
    suggestions: list[ProactiveSuggestion] = []
    if vehicle.battery <= 15 or vehicle.range <= 55:
        suggestions.append(
            ProactiveSuggestion(
                id="low_battery_charge",
                priority="high",
                title="补能建议",
                message=f"当前电量 {round(vehicle.battery)}%，预计续航 {round(vehicle.range)} km。可先检索顺路快充站。",
                action_label="检索快充站",
                prompt="帮我找一个顺路快充站",
                source="Vehicle.Powertrain",
            )
        )
    if vehicle.rain_probability >= 60 and any(value > 0 for value in vehicle.windows.model_dump().values()):
        suggestions.append(
            ProactiveSuggestion(
                id="rain_window_visibility",
                priority="medium",
                title="降雨安全建议",
                message="检测到较高降雨概率且存在开启车窗。可关闭车窗并开启自动雨刷。",
                action_label="查看建议",
                prompt="关闭所有车窗并打开自动雨刷",
                source="Environment.Weather",
            )
        )
    if vehicle.air_quality.pm25 >= 100:
        suggestions.append(
            ProactiveSuggestion(
                id="air_quality_purify",
                priority="medium",
                title="空气质量建议",
                message=f"车内 PM2.5 为 {vehicle.air_quality.pm25}，可开启空气净化器。",
                action_label="开启净化建议",
                prompt="打开3挡空气净化器",
                source="Vehicle.Cabin.AirQuality",
            )
        )
    if vehicle.perception_event == "windshield_visibility_low":
        suggestions.append(
            ProactiveSuggestion(
                id="vision_visibility_defrost",
                priority="high",
                title="可视性提示",
                message="视觉感知适配器报告前风挡可视性下降。建议开启前风挡除霜；请确认后再执行。",
                action_label="准备除霜",
                prompt="开启前风挡除霜",
                source="PerceptionEventAdapter",
            )
        )
    return suggestions
