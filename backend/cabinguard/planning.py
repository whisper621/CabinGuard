"""Server-side TaskPlan compiler.

The compiler is deliberately deterministic: the LLM decides how to converse, while
the server decides the maximum executable scope for the current user request.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domains import DOMAIN_BY_ID

RiskLevel = Literal["low", "medium", "high"]
TaskStatus = Literal["pending", "running", "success", "blocked", "skipped"]


class TaskNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    domain: str
    title: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    risk: RiskLevel = "low"
    permission: str = "read"
    parallelizable: bool = False
    allowed_tools: list[str] = Field(default_factory=list, alias="allowedTools")
    expected_evidence: list[str] = Field(default_factory=list, alias="expectedEvidence")
    status: TaskStatus = "pending"


class TaskPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    version: str = "6.0.0"
    objective: str
    nodes: list[TaskNode]
    execution_waves: list[list[str]] = Field(alias="executionWaves")
    allowed_tools: list[str] = Field(alias="allowedTools")
    requires_confirmation: bool = Field(False, alias="requiresConfirmation")

    @model_validator(mode="after")
    def validate_graph(self) -> TaskPlan:
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("task node ids must be unique")
        if any(dep not in node_ids for node in self.nodes for dep in node.dependencies):
            raise ValueError("task dependency does not exist")
        flattened = [node_id for wave in self.execution_waves for node_id in wave]
        if len(flattened) != len(set(flattened)) or set(flattened) != node_ids:
            raise ValueError("execution waves must contain every task exactly once")
        return self

    def public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)

    def node_for_tool(self, tool_name: str) -> TaskNode | None:
        return next((node for node in self.nodes if tool_name in node.allowed_tools), None)


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _node(
    index: int,
    domain: str,
    title: str,
    description: str,
    tools: list[str],
    *,
    dependencies: list[str] | None = None,
    risk: RiskLevel = "low",
    permission: str = "read",
    parallelizable: bool = False,
) -> TaskNode:
    manifest = DOMAIN_BY_ID[domain]
    invalid = set(tools) - manifest.tools
    if invalid:
        raise ValueError(f"domain {domain} does not own tools: {sorted(invalid)}")
    return TaskNode(
        id=f"task-{index:02d}",
        domain=domain,
        title=title,
        description=description,
        dependencies=dependencies or [],
        risk=risk,
        permission=permission,
        parallelizable=parallelizable,
        allowedTools=tools,
        expectedEvidence=["policy.decision", "tool.receipt", "state.version"],
    )


def _build_waves(nodes: list[TaskNode]) -> list[list[str]]:
    incoming = {node.id: len(node.dependencies) for node in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for dependency in node.dependencies:
            outgoing[dependency].append(node.id)
    ready = deque(node.id for node in nodes if incoming[node.id] == 0)
    waves: list[list[str]] = []
    visited = 0
    while ready:
        wave = list(ready)
        ready.clear()
        waves.append(wave)
        visited += len(wave)
        for node_id in wave:
            for target in outgoing[node_id]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
    if visited != len(nodes):
        raise ValueError("task plan contains a cycle")
    return waves


def compile_task_plan(text: str) -> TaskPlan:
    """Compile a bounded executable graph from a Chinese cockpit request."""

    text = text.strip()
    nodes: list[TaskNode] = []

    navigation = _has(text, r"导航|路线|怎么去|带我去|前往|到.+去")
    poi = _has(text, r"附近|周边|找.*(?:店|站|餐厅|医院|商场)|火锅|充电站|加油站")
    charging = _has(text, r"充电|补能|快充")
    climate = _has(text, r"空调|温度|舒服|有点冷|有点热|太冷|太热|风量|内循环|外循环")
    climate_ambiguous = climate and _has(text, r"舒服一点|调(?:低|高)一点|有点冷|有点热|太冷|太热") and not _has(
        text, r"\d{2}\s*(?:度|℃)|内循环|外循环|风量\s*\d"
    )
    cabin_device = _has(text, r"车窗|座椅|氛围灯|除霜|除雾") and not _has(text, r"按摩")
    sunroof = _has(text, r"天窗|遮阳帘")
    sunroof_ambiguous = sunroof and _has(text, r"打开|开启") and not _has(
        text, r"\d+\s*%|\d+\s*(?:成|百分比)|一半|全开|完全打开"
    )
    trunk = _has(text, r"后备箱|尾门")
    trunk_status_query = trunk and _has(text, r"打开了吗|关闭了吗|是否|状态|现在.*(?:开|关)")
    weather = _has(text, r"天气|下雨|降雨")
    vehicle_status = _has(text, r"车速|电量|续航|车况|当前位置|我在哪|状态")
    vehicle_status = vehicle_status or trunk_status_query
    capabilities = _has(text, r"会什么|能做什么|能力|几个\s*agent|多少.*工具")
    memory = _has(text, r"记住|偏好|忘记|删除.*(?:记忆|偏好)|历史行程|去过哪里")

    def add(
        domain: str,
        title: str,
        description: str,
        tools: list[str],
        **kwargs: object,
    ) -> TaskNode:
        node = _node(len(nodes) + 1, domain, title, description, tools, **kwargs)
        nodes.append(node)
        return node

    if vehicle_status or navigation or charging or cabin_device or sunroof or trunk:
        add(
            "system",
            "读取可信车辆上下文",
            "读取车速、挡位、电量、位置和座舱设备状态，作为后续策略依据。",
            ["get_vehicle_state"],
            parallelizable=bool(weather or climate),
        )
    if weather or sunroof:
        add(
            "system",
            "读取天气风险",
            "读取当前天气与降雨概率，避免不安全的车身动作。",
            ["get_weather"],
            parallelizable=True,
        )
    if climate and climate_ambiguous:
        add(
            "comfort",
            "澄清舒适偏好",
            "缺少目标温度、风量或循环模式，本节点只允许追问，不开放写工具。",
            [],
        )
    elif climate:
        read = add(
            "comfort",
            "读取舒适域状态",
            "读取当前温度、风量与循环模式，避免盲写。",
            ["get_climate_state"],
            parallelizable=True,
        )
        add(
            "comfort",
            "调节座舱气候",
            "按用户明确参数设置温度、风量与循环模式。",
            ["set_climate"],
            dependencies=[read.id],
            risk="medium",
            permission="cabin:write",
        )
    if cabin_device:
        dependency = next((node.id for node in nodes if "get_vehicle_state" in node.allowed_tools), None)
        add(
            "comfort",
            "执行座舱设备控制",
            "控制车窗、座椅、氛围灯或除霜，并应用 VSS 约束。",
            ["control_cabin_device"],
            dependencies=[dependency] if dependency else [],
            risk="medium",
            permission="cabin:write",
        )
    if sunroof and sunroof_ambiguous:
        add(
            "body_safety",
            "澄清天窗开度",
            "用户尚未说明天窗目标开度，本节点只允许追问。",
            [],
            risk="high",
            permission="body:write:clarify",
        )
    elif sunroof:
        dependencies = [
            node.id
            for node in nodes
            if "get_vehicle_state" in node.allowed_tools or "get_weather" in node.allowed_tools
        ]
        add(
            "body_safety",
            "执行天窗安全控制",
            "依据车速、降雨和一次性确认状态设置天窗开度。",
            ["control_sunroof"],
            dependencies=dependencies,
            risk="high",
            permission="body:write:confirm",
        )
    if trunk and not trunk_status_query:
        dependency = next((node.id for node in nodes if "get_vehicle_state" in node.allowed_tools), None)
        add(
            "body_safety",
            "执行后备箱控制",
            "服务端确认挡位和车速后执行尾门动作。",
            ["control_trunk"],
            dependencies=[dependency] if dependency else [],
            risk="high",
            permission="body:write",
        )
    if navigation or poi or charging:
        state_node = next((node for node in nodes if "get_vehicle_state" in node.allowed_tools), None)
        if charging:
            search = add(
                "navigation",
                "检索沿途补能点",
                "结合当前车辆位置、路线和绕行上限筛选充电站。",
                ["search_charging_stations"],
                dependencies=[state_node.id] if state_node else [],
                parallelizable=bool(climate),
            )
            if navigation:
                add(
                    "navigation",
                    "启动补能导航",
                    "仅允许导航至本轮检索得到的已验证充电站。",
                    ["start_navigation"],
                    dependencies=[search.id],
                    risk="medium",
                    permission="navigation:write",
                )
        else:
            search = add(
                "navigation",
                "检索真实地点候选",
                "调用外部地理编码服务返回可核验的地点候选。",
                ["search_places"],
                parallelizable=bool(climate),
            )
            if navigation:
                add(
                    "navigation",
                    "规划真实道路路线",
                    "使用本轮候选 ID 调用道路服务，生成距离、ETA 和路线折线。",
                    ["plan_navigation"],
                    dependencies=[search.id],
                    risk="medium",
                    permission="navigation:write",
                )
    if memory:
        memory_tools = []
        if _has(text, r"记住|偏好|忘记|删除.*(?:记忆|偏好)"):
            memory_tools.append("manage_preferences")
        if _has(text, r"历史行程|去过哪里|最近去"):
            memory_tools.append("query_trip_history")
        add(
            "memory",
            "处理会话记忆",
            "读取行程或仅按用户明确指令增删当前会话偏好。",
            memory_tools or ["manage_preferences"],
            risk="medium" if _has(text, r"记住|忘记|删除") else "low",
            permission="session-memory:read-write",
        )
    if capabilities:
        add(
            "system",
            "读取运行时能力",
            "从实际注册表读取 Agent、工具、信号和约束数量。",
            ["get_capabilities"],
        )
    if not nodes:
        add(
            "system",
            "理解与澄清请求",
            "当前请求未形成可安全执行的座舱动作，由主 Agent 直接回答或追问。",
            [],
        )

    allowed_tools = sorted({tool for node in nodes for tool in node.allowed_tools})
    waves = _build_waves(nodes)
    return TaskPlan(
        id=f"plan-{uuid4().hex[:12]}",
        objective=text,
        nodes=nodes,
        executionWaves=waves,
        allowedTools=allowed_tools,
        requiresConfirmation=any(node.risk == "high" and node.allowed_tools for node in nodes),
    )


def tool_allowed(plan: TaskPlan, tool_name: str) -> bool:
    return tool_name in plan.allowed_tools
