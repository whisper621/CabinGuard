"""Server-enforced role and TaskPlan authorization kernel."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .planning import TaskPlan, tool_allowed

OccupantRole = Literal["driver", "front_passenger", "rear_child", "guest"]


class PolicyDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    allowed: bool
    code: str
    message: str
    suggestion: str | None = None
    policy: str

    def public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True, exclude_none=True)


READ_TOOLS = frozenset(
    {
        "get_vehicle_state",
        "get_weather",
        "get_climate_state",
        "get_capabilities",
        "query_trip_history",
        "search_places",
        "search_charging_stations",
    }
)
FRONT_PASSENGER_WRITE = frozenset({"set_climate", "control_cabin_device"})
REAR_CHILD_WRITE = frozenset({"control_cabin_device"})


def authorize_tool(
    plan: TaskPlan,
    role: OccupantRole,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
) -> PolicyDecision:
    if not tool_allowed(plan, tool_name):
        return PolicyDecision(
            allowed=False,
            code="tool_outside_task_plan",
            message=f"工具 {tool_name} 不在本轮可信任务图白名单中，未执行。",
            suggestion="请明确提出与该工具对应的座舱任务。",
            policy="task-plan-allowlist",
        )
    if role == "driver":
        return PolicyDecision(
            allowed=True,
            code="authorized",
            message="驾驶员角色通过任务图与权限校验。",
            policy="abac-driver",
        )
    if tool_name in READ_TOOLS:
        return PolicyDecision(
            allowed=True,
            code="authorized_read",
            message="当前乘员角色可读取该信息。",
            policy=f"abac-{role}",
        )
    if role == "front_passenger" and tool_name in FRONT_PASSENGER_WRITE:
        attributes = tool_input or {}
        device = attributes.get("device")
        zone = attributes.get("zone")
        if tool_name == "control_cabin_device" and device in {"window", "seat"} and zone != "passenger":
            return PolicyDecision(
                allowed=False,
                code="occupant_resource_forbidden",
                message="前排乘客只能调节自己的车窗或座椅，未执行。",
                suggestion="将区域改为 passenger，或由驾驶员发起其他座位操作。",
                policy="abac-front-passenger-resource",
            )
        return PolicyDecision(
            allowed=True,
            code="authorized_comfort",
            message="前排乘客可操作非驾驶安全关键的舒适设备。",
            policy="abac-front-passenger",
        )
    if role == "rear_child" and tool_name in REAR_CHILD_WRITE:
        return PolicyDecision(
            allowed=False,
            code="guardian_authorization_required",
            message="儿童乘员的设备写操作需要驾驶员或监护人授权，未执行。",
            suggestion="由驾驶员角色发起操作，或先完成监护授权。",
            policy="abac-rear-child",
        )
    return PolicyDecision(
        allowed=False,
        code="occupant_role_forbidden",
        message="当前乘员角色没有该写操作权限，未执行。",
        suggestion="切换为有权限的驾驶员角色后重新发起。",
        policy=f"abac-{role}",
    )
