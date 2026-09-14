"""Domain manifests for selective delegation and deterministic tool isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuntimeKind = Literal["agent", "service"]


@dataclass(frozen=True)
class DomainManifest:
    id: str
    name: str
    runtime: RuntimeKind
    description: str
    tools: frozenset[str]
    permission_scope: str
    sla_ms: int

    def public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "runtime": self.runtime,
            "description": self.description,
            "tools": sorted(self.tools),
            "permissionScope": self.permission_scope,
            "slaMs": self.sla_ms,
        }


DOMAIN_MANIFESTS: tuple[DomainManifest, ...] = (
    DomainManifest(
        id="navigation",
        name="导航领域 Agent",
        runtime="agent",
        description="处理地点检索、路线规划和补能目的地选择；复杂且依赖外部世界知识。",
        tools=frozenset(
            {
                "get_vehicle_state",
                "search_places",
                "plan_navigation",
                "search_charging_stations",
                "start_navigation",
            }
        ),
        permission_scope="location:read,navigation:write",
        sla_ms=8000,
    ),
    DomainManifest(
        id="comfort",
        name="舒适控制服务",
        runtime="service",
        description="确定性执行空调、座椅、车窗、氛围灯与除霜动作。",
        tools=frozenset(
            {"get_climate_state", "get_vehicle_state", "set_climate", "control_cabin_device"}
        ),
        permission_scope="cabin:read,cabin:write",
        sla_ms=300,
    ),
    DomainManifest(
        id="body_safety",
        name="车身安全服务",
        runtime="service",
        description="处理天窗与后备箱动作，强制执行天气、车速和确认约束。",
        tools=frozenset(
            {"get_vehicle_state", "get_weather", "control_sunroof", "control_trunk"}
        ),
        permission_scope="vehicle:read,body:write",
        sla_ms=300,
    ),
    DomainManifest(
        id="memory",
        name="会话记忆服务",
        runtime="service",
        description="仅保存当前演示会话内用户明确声明的偏好和行程回执。",
        tools=frozenset({"manage_preferences", "query_trip_history"}),
        permission_scope="session-memory:read-write",
        sla_ms=100,
    ),
    DomainManifest(
        id="system",
        name="系统感知服务",
        runtime="service",
        description="提供车辆、天气和运行时能力的可信只读视图。",
        tools=frozenset(
            {"get_vehicle_state", "get_weather", "get_climate_state", "get_capabilities"}
        ),
        permission_scope="runtime:read",
        sla_ms=100,
    ),
)

DOMAIN_BY_ID = {manifest.id: manifest for manifest in DOMAIN_MANIFESTS}
TOOL_DOMAINS: dict[str, frozenset[str]] = {}
for _manifest in DOMAIN_MANIFESTS:
    for _tool in _manifest.tools:
        TOOL_DOMAINS[_tool] = TOOL_DOMAINS.get(_tool, frozenset()) | frozenset({_manifest.id})


def domain_for_tool(tool_name: str, preferred: str | None = None) -> str:
    domains = TOOL_DOMAINS.get(tool_name, frozenset({"system"}))
    if preferred in domains:
        return str(preferred)
    return sorted(domains)[0]
