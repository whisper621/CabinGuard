"""Public charging-station POI adapter with an explicit demo-catalog fallback."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError

from .models import ToolExecution, VehicleState
from .tools import SearchChargingInput, ToolContext, _haversine_km, execute_tool


class ChargingToolExecutor:
    endpoint = "https://overpass-api.de/api/interpreter"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    @staticmethod
    def _fallback(
        raw_input: Mapping[str, Any], vehicle: VehicleState, context: ToolContext, reason: str | None = None
    ) -> ToolExecution:
        result = execute_tool("search_charging_stations", raw_input, vehicle, context)
        if result.status == "success":
            result.output["provider"] = "CabinGuard demo catalog"
            result.output["fallbackReason"] = reason or "未授权外部补能 POI 查询"
            result.output["liveProviderUsed"] = False
        return result

    async def execute(
        self,
        raw_input: Mapping[str, Any],
        vehicle: VehicleState,
        context: ToolContext,
    ) -> ToolExecution:
        try:
            parsed = SearchChargingInput.model_validate(dict(raw_input))
        except ValidationError:
            return self._fallback(raw_input, vehicle, context, "补能查询参数无效")
        if not vehicle.external_routing_consent:
            return self._fallback(raw_input, vehicle, context)
        if not context.bypass_read_prerequisites and "get_vehicle_state" not in context.prior_successful_tools:
            return self._fallback(raw_input, vehicle, context, "补能决策前尚未读取车辆状态")

        query = (
            "[out:json][timeout:10];"
            "(node[\"amenity\"=\"charging_station\"](around:25000,"
            f"{vehicle.latitude},{vehicle.longitude});"
            "way[\"amenity\"=\"charging_station\"](around:25000,"
            f"{vehicle.latitude},{vehicle.longitude}););out center 12;"
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0), transport=self.transport) as client:
                response = await client.post(self.endpoint, data={"data": query})
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            return self._fallback(raw_input, vehicle, context, f"OpenStreetMap POI 服务不可用：{type(error).__name__}")

        elements = payload.get("elements", []) if isinstance(payload, dict) else []
        stations: list[dict[str, object]] = []
        seen: set[str] = set()
        for element in elements if isinstance(elements, list) else []:
            if not isinstance(element, dict):
                continue
            center = element.get("center") if isinstance(element.get("center"), dict) else element
            if not isinstance(center, dict):
                continue
            latitude, longitude = center.get("lat"), center.get("lon")
            if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
                continue
            tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
            name = str(tags.get("name") or tags.get("operator") or f"OpenStreetMap 充电站 #{element.get('id', '')}")
            if name in seen:
                continue
            distance = round(_haversine_km(vehicle.latitude, vehicle.longitude, float(latitude), float(longitude)) * 1.18, 1)
            detour = round(max(0.5, distance * 0.12), 1)
            if detour > parsed.max_detour_km:
                continue
            seen.add(name)
            stations.append(
                {
                    "name": name,
                    "latitude": round(float(latitude), 6),
                    "longitude": round(float(longitude), 6),
                    "distance_km": distance,
                    "detour_km": detour,
                    "available_fast_chargers": None,
                    "estimated_arrival_battery_percent": max(5, round(vehicle.battery - distance * 0.35)),
                    "data_source": "OpenStreetMap Overpass POI",
                    "provider_id": f"osm:{element.get('type', 'node')}:{element.get('id', '')}",
                }
            )
        stations.sort(key=lambda item: float(item["distance_km"]))
        return ToolExecution(
            vehicle=vehicle,
            status="success",
            output={
                "stations": stations[:6],
                "provider": "OpenStreetMap Overpass POI",
                "liveProviderUsed": True,
                "availabilityNotice": "站点坐标来自公开 POI；空闲枪位和营业状态未核验。",
            },
        )
