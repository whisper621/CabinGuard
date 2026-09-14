from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import GeoPoint, ToolExecution, VehicleState

TOOL_VERSION = "4.0.0-python"
ONLINE_TOOL_NAMES = frozenset({"search_places", "plan_navigation"})

CHARGING_STATIONS: tuple[dict[str, object], ...] = (
    {
        "name": "顺义服务区超充站",
        "latitude": 40.1672,
        "longitude": 116.6371,
        "distance_km": 18.6,
        "detour_km": 1.8,
        "available_fast_chargers": 6,
        "battery_drop_percent": 7,
    },
    {
        "name": "怀柔北综合能源站",
        "latitude": 40.3584,
        "longitude": 116.6318,
        "distance_km": 24.1,
        "detour_km": 4.6,
        "available_fast_chargers": 3,
        "battery_drop_percent": 10,
    },
)


class StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictToolInput):
    pass


class SetClimateInput(StrictToolInput):
    target_temperature_c: float = Field(ge=16, le=30)
    fan_level: int = Field(ge=1, le=5)
    circulation: str = Field(pattern="^(内循环|外循环)$")


class SearchChargingInput(StrictToolInput):
    along_route: bool
    max_detour_km: float = Field(ge=0, le=20)


class StartNavigationInput(StrictToolInput):
    destination: str = Field(min_length=1, max_length=100)


class SearchPlacesInput(StrictToolInput):
    query: str = Field(min_length=2, max_length=100)
    limit: int = Field(default=3, ge=1, le=5)


class PlanNavigationInput(StrictToolInput):
    destination_id: str = Field(min_length=8, max_length=64)
    route_preference: str = Field(default="fastest", pattern="^(fastest|avoid_highways)$")


class ControlSunroofInput(StrictToolInput):
    target_percent: int = Field(ge=0, le=100)
    confirmed: bool


class ControlTrunkInput(StrictToolInput):
    action: str = Field(pattern="^(open|close)$")


TOOL_MODELS: dict[str, type[StrictToolInput]] = {
    "get_vehicle_state": EmptyInput,
    "get_weather": EmptyInput,
    "get_climate_state": EmptyInput,
    "set_climate": SetClimateInput,
    "search_charging_stations": SearchChargingInput,
    "start_navigation": StartNavigationInput,
    "search_places": SearchPlacesInput,
    "plan_navigation": PlanNavigationInput,
    "control_sunroof": ControlSunroofInput,
    "control_trunk": ControlTrunkInput,
}

TOOL_DESCRIPTIONS = {
    "get_vehicle_state": "读取车速、挡位、电量、续航、当前位置与导航状态。执行车辆动作或补能决策前调用。",
    "get_weather": "读取当前位置天气和降雨概率。操作天窗前必须调用。",
    "get_climate_state": "读取车内温度、空调设定、风量和循环模式。调整空调前调用。",
    "set_climate": "设置空调目标温度、风量和循环模式。参数必须完整且有效。",
    "search_charging_stations": "结合当前路线搜索快充站。当前请求中必须先调用 get_vehicle_state。",
    "start_navigation": "开始补能导航。用户必须明确要求导航，且目的地必须来自本轮充电站搜索结果。",
    "search_places": "使用外部地理编码服务检索任意普通地点、地址或行政区。一般导航前先调用，返回候选 ID、名称和地址。",
    "plan_navigation": "基于 search_places 返回的候选 ID，调用外部道路服务生成真实道路距离、ETA、路线折线与步骤。需要用户明确导航意图。",
    "control_sunroof": "设置天窗开度。工具层会强制执行天气、车速和确认校验。",
    "control_trunk": "开启或关闭后备箱。行驶中会被工具层阻止。",
}


def _tool_definition(name: str, model: type[StrictToolInput]) -> dict[str, object]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "parameters": schema,
        },
    }


TOOL_DEFINITIONS = [_tool_definition(name, model) for name, model in TOOL_MODELS.items()]


@dataclass
class ToolContext:
    prior_successful_tools: tuple[str, ...] = ()
    navigation_authorized: bool = False
    place_search_authorized: bool = False
    allowed_navigation_destinations: tuple[str, ...] = ()
    allow_high_speed_sunroof: bool = False
    bypass_read_prerequisites: bool = False
    on_sunroof_confirmation_required: Callable[[int], None] | None = field(default=None, repr=False)


def _blocked(
    vehicle: VehicleState,
    reason: str,
    **extra: object,
) -> ToolExecution:
    return ToolExecution(
        vehicle=vehicle,
        status="blocked",
        output={"executed": False, "blocked": True, "reason": reason, **extra},
    )


def _has_prior(context: ToolContext, tool_name: str) -> bool:
    return tool_name in context.prior_successful_tools


def _haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return great-circle distance for browser-position route estimates."""

    earth_radius_km = 6371.0
    lat_delta = radians(latitude_b - latitude_a)
    lon_delta = radians(longitude_b - longitude_a)
    haversine = sin(lat_delta / 2) ** 2 + (
        cos(radians(latitude_a))
        * cos(radians(latitude_b))
        * sin(lon_delta / 2) ** 2
    )
    return 2 * earth_radius_km * asin(sqrt(haversine))


def _route_distance(vehicle: VehicleState, station: Mapping[str, object]) -> float:
    if vehicle.location_source == "browser_geolocation":
        straight_line = _haversine_km(
            vehicle.latitude,
            vehicle.longitude,
            float(station["latitude"]),
            float(station["longitude"]),
        )
        return round(straight_line * 1.18, 1)
    return float(station["distance_km"])


def _route_polyline(vehicle: VehicleState, station: Mapping[str, object]) -> list[GeoPoint]:
    destination_latitude = float(station["latitude"])
    destination_longitude = float(station["longitude"])
    return [
        GeoPoint(latitude=vehicle.latitude, longitude=vehicle.longitude),
        GeoPoint(
            latitude=round((vehicle.latitude + destination_latitude) / 2 + 0.008, 6),
            longitude=round((vehicle.longitude + destination_longitude) / 2 - 0.006, 6),
        ),
        GeoPoint(latitude=destination_latitude, longitude=destination_longitude),
    ]


def execute_tool(
    name: str,
    raw_input: Mapping[str, Any],
    vehicle: VehicleState,
    context: ToolContext | None = None,
) -> ToolExecution:
    """Validate and execute one domain tool against trusted vehicle state."""

    context = context or ToolContext()
    model = TOOL_MODELS.get(name)
    if model is None:
        return _blocked(vehicle, f"未知工具：{name}", code="unknown_tool")

    try:
        parsed = model.model_validate(dict(raw_input))
    except (ValidationError, TypeError, ValueError) as error:
        issues = (
            error.errors(include_url=False)
            if isinstance(error, ValidationError)
            else [{"msg": str(error)}]
        )
        return _blocked(
            vehicle,
            "工具参数无效，未执行任何车辆操作",
            code="invalid_tool_arguments",
            issues=issues,
        )

    if name in ONLINE_TOOL_NAMES:
        return _blocked(
            vehicle,
            "该工具必须通过异步外部导航执行器调用",
            code="online_tool_requires_async_executor",
        )

    if name == "get_vehicle_state":
        return ToolExecution(
            vehicle=vehicle,
            status="success",
            output={
                "speed_kmh": vehicle.speed,
                "gear": "D" if vehicle.speed > 0 else "P",
                "battery_percent": vehicle.battery,
                "estimated_range_km": vehicle.range,
                "current_location": {
                    "name": vehicle.current_location,
                    "source": vehicle.location_source,
                    "coordinate_available": True,
                },
                "route": {
                    "road": "京承高速北向（模拟）",
                    "destination": vehicle.destination,
                    "distance_km": vehicle.route_distance_km,
                    "eta_minutes": vehicle.route_eta_minutes,
                    "polyline_points": len(vehicle.route_polyline),
                    "provider": "CabinGuard navigation sandbox",
                },
                "destination": vehicle.destination,
            },
        )

    if name == "get_weather":
        return ToolExecution(
            vehicle=vehicle,
            status="success",
            output={
                "condition": vehicle.weather,
                "rain_probability": vehicle.rain_probability,
            },
        )

    if name == "get_climate_state":
        return ToolExecution(
            vehicle=vehicle,
            status="success",
            output={
                "cabin_temperature_c": vehicle.cabin_temperature,
                "target_temperature_c": vehicle.target_temperature,
                "fan_level": vehicle.fan_level,
                "circulation": vehicle.circulation,
            },
        )

    if name == "set_climate":
        assert isinstance(parsed, SetClimateInput)
        if not context.bypass_read_prerequisites and not _has_prior(context, "get_climate_state"):
            return _blocked(
                vehicle,
                "调节空调前必须先读取当前空调状态",
                retryable=True,
            )
        next_vehicle = vehicle.model_copy(
            update={
                "target_temperature": parsed.target_temperature_c,
                "fan_level": parsed.fan_level,
                "circulation": parsed.circulation,
            }
        )
        return ToolExecution(
            vehicle=next_vehicle,
            status="success",
            output={
                "executed": True,
                "target_temperature_c": next_vehicle.target_temperature,
                "fan_level": next_vehicle.fan_level,
                "circulation": next_vehicle.circulation,
            },
        )

    if name == "search_charging_stations":
        assert isinstance(parsed, SearchChargingInput)
        if not context.bypass_read_prerequisites and not _has_prior(context, "get_vehicle_state"):
            return _blocked(
                vehicle,
                "补能决策前必须先读取车辆电量、续航和当前路线",
                retryable=True,
            )
        filtered = []
        for station in CHARGING_STATIONS:
            if float(station["detour_km"]) > parsed.max_detour_km:
                continue
            filtered.append(
                {
                    "name": station["name"],
                    "latitude": station["latitude"],
                    "longitude": station["longitude"],
                    "distance_km": _route_distance(vehicle, station),
                    "detour_km": station["detour_km"],
                    "available_fast_chargers": station["available_fast_chargers"],
                    "estimated_arrival_battery_percent": max(
                        8, vehicle.battery - float(station["battery_drop_percent"])
                    ),
                    "data_source": "CabinGuard demo catalog",
                }
            )
        return ToolExecution(
            vehicle=vehicle,
            status="success",
            output={"stations": filtered},
        )

    if name == "start_navigation":
        assert isinstance(parsed, StartNavigationInput)
        destination = parsed.destination.strip()
        if not context.navigation_authorized:
            return _blocked(
                vehicle,
                "用户没有明确要求启动导航",
                code="navigation_not_authorized",
            )
        if not _has_prior(context, "search_charging_stations"):
            return _blocked(
                vehicle,
                "启动补能导航前必须先搜索充电站",
                retryable=True,
            )
        if destination not in context.allowed_navigation_destinations:
            return _blocked(
                vehicle,
                "导航目的地不在本轮充电站搜索结果中",
                code="destination_not_verified",
            )
        station = next(
            (item for item in CHARGING_STATIONS if item["name"] == destination),
            None,
        )
        if station is None:
            return _blocked(
                vehicle,
                "导航目的地缺少可验证的坐标数据",
                code="destination_coordinates_unavailable",
            )
        route_distance_km = _route_distance(vehicle, station)
        eta_minutes = max(
            5,
            round(route_distance_km / 70 * 60 + float(station["detour_km"]) * 2),
        )
        route_points = _route_polyline(vehicle, station)
        next_vehicle = vehicle.model_copy(
            update={
                "destination": destination,
                "route_distance_km": route_distance_km,
                "route_eta_minutes": eta_minutes,
                "route_polyline": route_points,
            }
        )
        return ToolExecution(
            vehicle=next_vehicle,
            status="success",
            output={
                "navigation_started": True,
                "destination": destination,
                "route_distance_km": route_distance_km,
                "eta_minutes": eta_minutes,
                "route_provider": "CabinGuard navigation sandbox",
                "data_freshness": "demo fixture",
            },
        )

    if name == "control_sunroof":
        assert isinstance(parsed, ControlSunroofInput)
        target = parsed.target_percent
        missing_reads = not _has_prior(context, "get_vehicle_state") or not _has_prior(
            context, "get_weather"
        )
        if target > 0 and not context.bypass_read_prerequisites and missing_reads:
            return _blocked(
                vehicle,
                "开启天窗前必须先读取车辆状态和天气",
                retryable=True,
            )
        if target > 0 and vehicle.rain_probability >= 50:
            return _blocked(
                vehicle,
                f"降雨概率 {vehicle.rain_probability:g}%，禁止开启天窗",
            )
        if target > 0 and vehicle.speed >= 80 and not context.allow_high_speed_sunroof:
            if context.on_sunroof_confirmation_required:
                context.on_sunroof_confirmation_required(target)
            return _blocked(
                vehicle,
                f"当前车速 {vehicle.speed:g} km/h，需要用户明确确认",
                confirmation_required=True,
            )
        next_vehicle = vehicle.model_copy(
            update={
                "sunshade": 100 if target > 0 else vehicle.sunshade,
                "sunroof": target,
            }
        )
        return ToolExecution(
            vehicle=next_vehicle,
            status="success",
            output={
                "executed": True,
                "sunroof_percent": target,
                "sunshade_percent": next_vehicle.sunshade,
            },
        )

    assert isinstance(parsed, ControlTrunkInput)
    if (
        parsed.action == "open"
        and not context.bypass_read_prerequisites
        and not _has_prior(context, "get_vehicle_state")
    ):
        return _blocked(
            vehicle,
            "开启后备箱前必须先读取车辆状态",
            retryable=True,
        )
    if parsed.action == "open" and vehicle.speed > 0:
        return _blocked(
            vehicle,
            f"车辆以 {vehicle.speed:g} km/h 行驶，后备箱只能在 P 挡开启",
        )
    return ToolExecution(
        vehicle=vehicle,
        status="success",
        output={"executed": True, "action": parsed.action},
    )
