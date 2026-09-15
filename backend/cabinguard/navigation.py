from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from .models import GeoPoint, RouteAlternative, ToolExecution, VehicleState
from .session import CabinSession
from .tools import PlanNavigationInput, SearchPlacesInput, ToolContext

GEOCODER_SOURCE = "OpenStreetMap Nominatim"
ROUTER_SOURCE = "OSRM · OpenStreetMap"
DEFAULT_GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_ROUTER_URL = "https://router.project-osrm.org"
FALLBACK_ROUTER_URL = "https://routing.openstreetmap.de/routed-car"
MAX_ROUTE_POINTS = 100
MAX_VISIBLE_ROUTE_STEPS = 20


class NavigationProviderError(RuntimeError):
    pass


def _blocked(vehicle: VehicleState, reason: str, **extra: object) -> ToolExecution:
    return ToolExecution(
        vehicle=vehicle,
        status="blocked",
        output={"executed": False, "blocked": True, "reason": reason, **extra},
    )


def _validation_block(vehicle: VehicleState, error: ValidationError) -> ToolExecution:
    return _blocked(
        vehicle,
        "工具参数无效，未调用外部导航服务",
        code="invalid_tool_arguments",
        issues=error.errors(include_url=False),
    )


def _simplify_coordinates(raw_coordinates: list[object]) -> list[GeoPoint]:
    valid: list[GeoPoint] = []
    for coordinate in raw_coordinates:
        if not isinstance(coordinate, list) or len(coordinate) < 2:
            continue
        longitude, latitude = coordinate[:2]
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue
        try:
            valid.append(GeoPoint(latitude=float(latitude), longitude=float(longitude)))
        except ValueError:
            continue
    if len(valid) <= MAX_ROUTE_POINTS:
        return valid
    indexes = {
        round(index * (len(valid) - 1) / (MAX_ROUTE_POINTS - 1))
        for index in range(MAX_ROUTE_POINTS)
    }
    return [point for index, point in enumerate(valid) if index in indexes]


def _step_instruction(step: dict[str, Any]) -> str | None:
    maneuver = step.get("maneuver") if isinstance(step.get("maneuver"), dict) else {}
    maneuver_type = str(maneuver.get("type") or "continue")
    modifier = str(maneuver.get("modifier") or "")
    road = " ".join(str(step.get("name") or "").split())
    distance = float(step.get("distance") or 0)
    direction_map = {
        "left": "左转",
        "slight left": "向左前方行驶",
        "sharp left": "向左后方转",
        "right": "右转",
        "slight right": "向右前方行驶",
        "sharp right": "向右后方转",
        "straight": "直行",
        "uturn": "调头",
    }
    if maneuver_type == "depart":
        action = "出发"
    elif maneuver_type == "arrive":
        action = "到达目的地"
    elif maneuver_type in {"roundabout", "rotary", "roundabout turn"}:
        action = "进入环岛"
    else:
        action = direction_map.get(modifier, "继续行驶")
    if action == "到达目的地":
        return action
    distance_text = (
        f"{distance / 1000:.1f} 公里" if distance >= 1000 else f"{max(1, round(distance))} 米"
    )
    if road:
        return f"{action}进入{road}，行驶约 {distance_text}"
    fallback_road = (
        "匝道"
        if maneuver_type in {"on ramp", "off ramp", "fork", "merge", "exit roundabout"}
        else "连接道路"
    )
    return f"{action}，沿{fallback_road}行驶约 {distance_text}"


def _route_step_summary(raw_steps: list[object]) -> list[str]:
    instructions = [
        instruction
        for step in raw_steps
        if isinstance(step, dict) and (instruction := _step_instruction(step))
    ]
    if len(instructions) <= MAX_VISIBLE_ROUTE_STEPS:
        return instructions
    head_count = MAX_VISIBLE_ROUTE_STEPS - 6
    omitted = len(instructions) - head_count - 5
    return [
        *instructions[:head_count],
        f"中间 {omitted} 个细分转向已折叠，可在 OpenStreetMap 核对完整路线",
        *instructions[-5:],
    ]


def _normalize_place_query(query: str) -> str:
    """Expand a common Chinese shorthand without inventing a destination."""

    normalized = " ".join(query.split())
    if "人民政府" not in normalized and re.search(r"[区县市]政府$", normalized):
        return f"{normalized[:-2]}人民政府"
    return normalized


def _clean_external_text(value: object, fallback: str, limit: int) -> str:
    """Bound third-party labels before returning them to the model or browser."""

    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", " ".join(str(value or "").split()))
    return (cleaned or fallback)[:limit]


class NavigationProvider:
    """Small, replaceable adapter for user-triggered geocoding and road routing."""

    def __init__(
        self,
        *,
        geocoder_url: str | None = None,
        router_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.geocoder_url = geocoder_url or os.getenv(
            "CABINGUARD_GEOCODER_URL", DEFAULT_GEOCODER_URL
        )
        configured_router_url = router_url or os.getenv("CABINGUARD_ROUTER_URL")
        self.router_url = (configured_router_url or DEFAULT_ROUTER_URL).rstrip("/")
        self.router_urls = [self.router_url]
        if configured_router_url is None and FALLBACK_ROUTER_URL != self.router_url:
            self.router_urls.append(FALLBACK_ROUTER_URL)
        self.transport = transport
        self._search_cache: dict[str, tuple[float, list[dict[str, object]]]] = {}
        self._geocoder_lock = asyncio.Lock()
        self._last_geocoder_request = 0.0

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "User-Agent": os.getenv(
                "CABINGUARD_MAP_USER_AGENT",
                "CabinGuard/0.4 (+https://github.com/whisper621/CabinGuard)",
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        }

    async def search_places(self, query: str, limit: int) -> list[dict[str, object]]:
        normalized = " ".join(query.split()).lower()
        cached = self._search_cache.get(normalized)
        if cached and cached[0] > time.time():
            return cached[1][:limit]

        async with self._geocoder_lock:
            delay = 1.0 - (time.monotonic() - self._last_geocoder_request)
            if delay > 0:
                await asyncio.sleep(delay)
            params = {
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": limit,
                "accept-language": "zh-CN",
            }
            country_codes = os.getenv("CABINGUARD_NAV_COUNTRY_CODES", "cn").strip()
            if country_codes:
                params["countrycodes"] = country_codes
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(12.0, connect=8.0),
                    transport=self.transport,
                    trust_env=True,
                ) as client:
                    response = await client.get(
                        self.geocoder_url,
                        params=params,
                        headers=self._headers(),
                    )
                    self._last_geocoder_request = time.monotonic()
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as error:
                raise NavigationProviderError(f"地点检索服务暂时不可用：{error}") from error

        if not isinstance(payload, list):
            raise NavigationProviderError("地点检索服务返回了无法识别的数据")

        candidates: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                latitude = float(item["lat"])
                longitude = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            display_name = _clean_external_text(item.get("display_name"), query, 240)
            raw_identifier = f"{item.get('osm_type')}:{item.get('osm_id')}:{latitude}:{longitude}"
            candidate_id = hashlib.sha256(raw_identifier.encode()).hexdigest()[:16]
            candidates.append(
                {
                    "id": candidate_id,
                    "name": _clean_external_text(
                        item.get("name"), display_name.split(",", 1)[0], 80
                    ),
                    "address": display_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "category": _clean_external_text(item.get("type"), "place", 40),
                    "importance": float(item.get("importance") or 0),
                }
            )

        self._search_cache[normalized] = (time.time() + 24 * 60 * 60, candidates)
        return candidates[:limit]

    async def plan_route(
        self,
        vehicle: VehicleState,
        destination: dict[str, object],
        route_preference: str,
    ) -> dict[str, object]:
        coordinates = (
            f"{vehicle.longitude:.6f},{vehicle.latitude:.6f};"
            f"{float(destination['longitude']):.6f},{float(destination['latitude']):.6f}"
        )
        params: dict[str, str] = {
            "alternatives": "true",
            "steps": "true",
            "geometries": "geojson",
            "overview": "full",
        }
        if route_preference == "avoid_highways":
            params["exclude"] = "motorway"
        payload: object | None = None
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(18.0, connect=8.0),
            transport=self.transport,
            trust_env=True,
        ) as client:
            for router_url in self.router_urls:
                try:
                    response = await client.get(
                        f"{router_url}/route/v1/driving/{coordinates}",
                        params=params,
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    payload = response.json()
                    break
                except (httpx.HTTPError, ValueError) as error:
                    last_error = error
        if payload is None:
            raise NavigationProviderError(
                f"道路算路服务暂时不可用：{last_error or '所有服务端点均无响应'}"
            ) from last_error

        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            message = payload.get("message") if isinstance(payload, dict) else None
            raise NavigationProviderError(str(message or "没有找到可驾驶路线"))
        routes = payload.get("routes")
        if not isinstance(routes, list) or not routes:
            raise NavigationProviderError("没有找到可驾驶路线")

        primary = routes[0]
        if not isinstance(primary, dict):
            raise NavigationProviderError("道路算路结果格式错误")
        geometry = primary.get("geometry") if isinstance(primary.get("geometry"), dict) else {}
        raw_coordinates = geometry.get("coordinates")
        points = _simplify_coordinates(raw_coordinates if isinstance(raw_coordinates, list) else [])
        if len(points) < 2:
            raise NavigationProviderError("道路算路结果缺少路线坐标")

        route_distance_km = round(float(primary.get("distance") or 0) / 1000, 1)
        eta_minutes = max(1, round(float(primary.get("duration") or 0) / 60))
        legs = primary.get("legs") if isinstance(primary.get("legs"), list) else []
        first_leg = legs[0] if legs and isinstance(legs[0], dict) else {}
        raw_steps = first_leg.get("steps") if isinstance(first_leg.get("steps"), list) else []
        steps = _route_step_summary(raw_steps)

        alternatives: list[RouteAlternative] = []
        for index, route in enumerate(routes[:3]):
            if not isinstance(route, dict):
                continue
            alternatives.append(
                RouteAlternative(
                    label="OSRM 主路线" if index == 0 else f"OSRM 备选路线 {index}",
                    distanceKm=round(float(route.get("distance") or 0) / 1000, 1),
                    etaMinutes=max(1, round(float(route.get("duration") or 0) / 60)),
                )
            )

        range_per_percent = vehicle.range / max(vehicle.battery, 1)
        arrival_battery = round(max(0, vehicle.battery - route_distance_km / range_per_percent), 1)
        destination_latitude = float(destination["latitude"])
        destination_longitude = float(destination["longitude"])
        navigation_url = (
            "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
            f"{vehicle.latitude:.6f}%2C{vehicle.longitude:.6f}%3B"
            f"{destination_latitude:.6f}%2C{destination_longitude:.6f}"
        )
        return {
            "destination": str(destination["name"]),
            "destination_latitude": destination_latitude,
            "destination_longitude": destination_longitude,
            "route_distance_km": route_distance_km,
            "eta_minutes": eta_minutes,
            "route_polyline": points,
            "route_steps": steps,
            "route_alternatives": alternatives,
            "route_provider": ROUTER_SOURCE,
            "route_data_freshness": datetime.now(UTC).isoformat(timespec="seconds"),
            "navigation_url": navigation_url,
            "estimated_arrival_battery": arrival_battery,
        }


class NavigationToolExecutor:
    def __init__(self, provider: NavigationProvider | None = None) -> None:
        self.provider = provider or NavigationProvider()

    async def execute(
        self,
        name: str,
        raw_input: dict[str, object],
        vehicle: VehicleState,
        session: CabinSession,
        context: ToolContext,
    ) -> ToolExecution:
        if name == "search_places":
            try:
                parsed = SearchPlacesInput.model_validate(raw_input)
            except ValidationError as error:
                return _validation_block(vehicle, error)
            if not (context.place_search_authorized or context.navigation_authorized):
                return _blocked(
                    vehicle,
                    "用户没有明确提出地点检索或导航需求",
                    code="navigation_not_authorized",
                )
            try:
                candidates = await self.provider.search_places(
                    _normalize_place_query(parsed.query), parsed.limit
                )
            except NavigationProviderError as error:
                return _blocked(vehicle, str(error), code="place_provider_unavailable")
            if not candidates:
                return _blocked(
                    vehicle,
                    f"没有检索到“{parsed.query}”的可验证地点",
                    code="place_not_found",
                )
            session.place_candidates = {
                str(candidate["id"]): candidate for candidate in candidates
            }
            public_candidates = [
                {
                    "id": candidate["id"],
                    "name": candidate["name"],
                    "address": candidate["address"],
                    "category": candidate["category"],
                    "source": GEOCODER_SOURCE,
                }
                for candidate in candidates
            ]
            return ToolExecution(
                vehicle=vehicle,
                status="success",
                output={
                    "query": parsed.query,
                    "candidates": public_candidates,
                    "provider": GEOCODER_SOURCE,
                    "live_data": True,
                },
            )

        if name != "plan_navigation":
            return _blocked(vehicle, f"未知在线工具：{name}", code="unknown_online_tool")
        try:
            parsed = PlanNavigationInput.model_validate(raw_input)
        except ValidationError as error:
            return _validation_block(vehicle, error)
        if not context.navigation_authorized:
            return _blocked(vehicle, "用户没有明确要求启动导航", code="navigation_not_authorized")
        if "get_vehicle_state" not in context.prior_successful_tools:
            return _blocked(vehicle, "真实算路前必须先读取当前位置", retryable=True)
        if "search_places" not in context.prior_successful_tools:
            return _blocked(vehicle, "真实算路前必须先检索并验证目的地", retryable=True)
        destination = session.place_candidates.get(parsed.destination_id)
        if destination is None:
            return _blocked(
                vehicle,
                "目的地不是本轮地点检索返回的候选",
                code="destination_not_verified",
            )
        if vehicle.location_source == "browser_geolocation" and not vehicle.external_routing_consent:
            return _blocked(
                vehicle,
                "尚未授权将起点坐标发送给外部道路算路服务",
                code="external_routing_consent_required",
            )
        try:
            route = await self.provider.plan_route(vehicle, destination, parsed.route_preference)
        except NavigationProviderError as error:
            return _blocked(vehicle, str(error), code="route_provider_unavailable")

        next_vehicle = vehicle.model_copy(
            update={
                "destination": route["destination"],
                "destination_latitude": route["destination_latitude"],
                "destination_longitude": route["destination_longitude"],
                "route_distance_km": route["route_distance_km"],
                "route_eta_minutes": route["eta_minutes"],
                "route_polyline": route["route_polyline"],
                "route_provider": route["route_provider"],
                "route_data_freshness": route["route_data_freshness"],
                "route_steps": route["route_steps"],
                "route_alternatives": route["route_alternatives"],
                "navigation_url": route["navigation_url"],
                "estimated_arrival_battery": route["estimated_arrival_battery"],
            }
        )
        arrival_battery = float(route["estimated_arrival_battery"])
        return ToolExecution(
            vehicle=next_vehicle,
            status="success",
            output={
                "navigation_started": True,
                "destination": route["destination"],
                "route_distance_km": route["route_distance_km"],
                "eta_minutes": route["eta_minutes"],
                "estimated_arrival_battery_percent": arrival_battery,
                "energy_warning": arrival_battery < 10,
                "route_provider": route["route_provider"],
                "route_alternatives": [
                    alternative.model_dump(by_alias=True)
                    for alternative in route["route_alternatives"]
                    if isinstance(alternative, RouteAlternative)
                ],
                "privacy": "起点坐标用于本次外部算路，但未写入模型工具回执",
            },
        )
