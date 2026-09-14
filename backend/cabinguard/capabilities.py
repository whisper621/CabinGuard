"""Runtime-derived capability manifest used by both the Agent and architecture UI."""

from __future__ import annotations

from .signals import CONSTRAINTS, SIGNALS
from .tools import TOOL_DESCRIPTIONS, TOOL_MODELS, TOOL_VERSION

TOOL_META: dict[str, tuple[str, str]] = {
    "get_vehicle_state": ("感知", "direct"),
    "get_weather": ("感知", "direct"),
    "get_climate_state": ("感知", "direct"),
    "set_climate": ("舒适域", "direct"),
    "search_charging_stations": ("补能", "direct"),
    "start_navigation": ("导航", "confirm"),
    "search_places": ("导航", "direct"),
    "plan_navigation": ("导航", "confirm"),
    "control_sunroof": ("车身域", "confirm"),
    "control_trunk": ("车身域", "direct"),
    "control_cabin_device": ("舒适域", "direct"),
    "get_capabilities": ("系统", "direct"),
    "manage_preferences": ("记忆", "confirm"),
    "query_trip_history": ("记忆", "direct"),
}


def capability_manifest() -> dict[str, object]:
    tools = [
        {
            "name": name,
            "category": TOOL_META.get(name, ("其他", "direct"))[0],
            "permission": TOOL_META.get(name, ("其他", "direct"))[1],
            "description": TOOL_DESCRIPTIONS[name],
        }
        for name in TOOL_MODELS
    ]
    return {
        "version": TOOL_VERSION,
        "agentCount": 1,
        "toolCount": len(tools),
        "signalCount": len(SIGNALS),
        "constraintCount": len(CONSTRAINTS),
        "tools": tools,
        "signals": [signal.public_dict() for signal in SIGNALS],
        "constraints": [constraint.public_dict() for constraint in CONSTRAINTS],
        "executionGraph": {
            "nodes": [
                {"id": "input", "label": "文本 / 中文语音", "layer": "HMI"},
                {"id": "planner", "label": "DeepSeek 多轮规划", "layer": "Agent"},
                {"id": "registry", "label": "工具注册与严格参数", "layer": "Runtime"},
                {"id": "policy", "label": "授权 / 前置 / 声明式约束", "layer": "Guardrail"},
                {"id": "executors", "label": "导航 / 车控 / 记忆执行器", "layer": "Execution"},
                {"id": "state", "label": "VSS 对齐状态与会话黑板", "layer": "State"},
                {"id": "receipt", "label": "可审计 Trace 与 HMI 回执", "layer": "HMI"},
            ],
            "edges": [
                ["input", "planner"],
                ["planner", "registry"],
                ["registry", "policy"],
                ["policy", "executors"],
                ["executors", "state"],
                ["state", "planner"],
                ["planner", "receipt"],
            ],
        },
        "integrations": [
            {"name": "DeepSeek", "type": "LLM 规划", "mode": "live"},
            {"name": "OpenStreetMap Nominatim", "type": "地点检索", "mode": "live"},
            {"name": "OSRM · OpenStreetMap", "type": "道路算路", "mode": "live"},
            {"name": "Browser Geolocation", "type": "用户授权定位", "mode": "live"},
            {"name": "Vehicle Sandbox", "type": "车辆执行", "mode": "simulated"},
        ],
    }


def compact_capabilities() -> dict[str, object]:
    manifest = capability_manifest()
    return {
        "agent_count": manifest["agentCount"],
        "tool_count": manifest["toolCount"],
        "signal_count": manifest["signalCount"],
        "constraint_count": manifest["constraintCount"],
        "tool_names": list(TOOL_MODELS),
        "execution_boundary": "真实地点与道路服务；车辆控制为安全沙箱",
    }
