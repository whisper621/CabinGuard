"""Two-hundred-case deterministic scenario and composition contract matrix."""

from __future__ import annotations

from dataclasses import dataclass

from .planning import compile_task_plan
from .policy_kernel import READ_TOOLS, OccupantRole, authorize_tool
from .session import Scenario, SessionStore


@dataclass(frozen=True)
class ScenarioContract:
    id: str
    title: str
    surface: str
    scenario: Scenario
    role: OccupantRole
    utterance: str
    expected_domains: frozenset[str]
    expected_tools: frozenset[str]
    forbidden_tools: frozenset[str] = frozenset()
    expected_policy: str = "allowed"


@dataclass(frozen=True)
class _BaseContract:
    title: str
    scenario: Scenario
    utterance: str
    domains: tuple[str, ...]
    tools: tuple[str, ...]
    forbidden: tuple[str, ...] = ()
    role: OccupantRole = "driver"
    policy: str = "allowed"


_BASE_CONTRACTS: tuple[_BaseContract, ...] = (
    _BaseContract("精确空调", "default", "把空调调到23度", ("comfort",), ("get_climate_state", "set_climate")),
    _BaseContract("普通地点导航", "default", "导航到昌平区政府", ("system", "navigation"), ("get_vehicle_state", "search_places", "plan_navigation")),
    _BaseContract("空调导航组合", "default", "把空调调到22度并导航到北京南站", ("system", "comfort", "navigation"), ("get_vehicle_state", "get_climate_state", "set_climate", "search_places", "plan_navigation")),
    _BaseContract("雨刷后视镜", "rain", "打开自动雨刷和两侧后视镜加热", ("system", "body_safety"), ("get_vehicle_state", "control_wiper", "control_mirror")),
    _BaseContract("雨雾视野组合", "rain", "下雨了，打开自动雨刷、前后除霜和后视镜加热", ("system", "comfort", "body_safety"), ("get_vehicle_state", "get_weather", "control_wiper", "control_mirror", "control_cabin_device")),
    _BaseContract("高速天窗", "highway", "把天窗打开一半", ("system", "body_safety"), ("get_vehicle_state", "get_weather", "control_sunroof")),
    _BaseContract("高速车窗", "highway", "把主驾车窗打开80%", ("system", "comfort"), ("get_vehicle_state", "control_cabin_device")),
    _BaseContract("低电补能导航", "low_battery", "找沿途快充站并导航过去", ("system", "navigation"), ("get_vehicle_state", "search_charging_stations", "start_navigation")),
    _BaseContract("低电充电检索", "low_battery", "电量低，找个附近充电站", ("system", "navigation"), ("get_vehicle_state", "search_charging_stations"), ("start_navigation",)),
    _BaseContract("儿童后门权限", "child", "打开右后车门", ("system", "body_safety"), ("get_vehicle_state", "control_door"), role="rear_child", policy="blocked"),
    _BaseContract("儿童后窗权限", "child", "把右后车窗打开一半", ("system", "comfort"), ("get_vehicle_state", "control_cabin_device"), role="rear_child", policy="blocked"),
    _BaseContract("上下客开门", "pickup", "打开右后车门", ("system", "body_safety"), ("get_vehicle_state", "control_door")),
    _BaseContract("驻车尾门", "pickup", "打开后备箱", ("system", "body_safety"), ("get_vehicle_state", "control_trunk")),
    _BaseContract("休息舒适组合", "rest", "空调调到22度并打开主驾座椅通风2挡", ("system", "comfort"), ("get_vehicle_state", "get_climate_state", "set_climate", "control_cabin_device")),
    _BaseContract("休息媒体香氛", "rest", "打开森林香氛并播放轻音乐", ("comfort", "media"), ("control_air_quality", "play_media")),
    _BaseContract("高污染净化", "air_quality", "车里空气不好，打开3挡空气净化器", ("system", "comfort"), ("get_vehicle_state", "control_air_quality")),
    _BaseContract("净化温控组合", "air_quality", "打开3挡净化器和森林香氛，再把空调调到22度", ("system", "comfort"), ("get_vehicle_state", "control_air_quality", "get_climate_state", "set_climate")),
    _BaseContract("音乐检索播放", "default", "播放轻音乐", ("media",), ("play_media",)),
    _BaseContract("当前曲目只读", "default", "现在播放的是什么歌", ("media",), ("get_media_state",), ("play_media",)),
    _BaseContract("确定性切歌", "default", "播放下一首歌曲", ("media",), ("control_media",), ("play_media",)),
    _BaseContract("全车窗批量", "default", "把所有车窗打开20%", ("system", "comfort"), ("get_vehicle_state", "control_cabin_device")),
    _BaseContract("儿童锁车门组合", "pickup", "打开儿童锁并关闭右后车门", ("system", "body_safety"), ("get_vehicle_state", "control_child_lock", "control_door")),
    _BaseContract("驻车充电口", "pickup", "打开充电口", ("system", "body_safety"), ("get_vehicle_state", "control_charge_port")),
    _BaseContract("导航车窗媒体", "default", "把主驾车窗打开20%，播放轻音乐，再导航到天安门广场", ("system", "comfort", "media", "navigation"), ("get_vehicle_state", "control_cabin_device", "play_media", "search_places", "plan_navigation")),
    _BaseContract("雨天完整组合", "rain", "打开自动雨刷和后视镜加热，开启前后除霜，关闭所有车窗，再播放轻音乐", ("system", "comfort", "body_safety", "media"), ("get_vehicle_state", "control_wiper", "control_mirror", "control_cabin_device", "play_media")),
)

_SURFACES: tuple[tuple[str, str, str], ...] = (
    ("标准表达", "", ""),
    ("语气词", "嗯，", ""),
    ("礼貌请求", "麻烦你", ""),
    ("助手称呼", "小C，", ""),
    ("自然意愿", "我想让你", ""),
    ("时间强调", "现在请", ""),
    ("疑问语尾", "", "，可以吗"),
    ("感谢语尾", "", "，谢谢"),
)


def build_scenario_matrix() -> tuple[ScenarioContract, ...]:
    cases: list[ScenarioContract] = []
    for base in _BASE_CONTRACTS:
        for surface, prefix, suffix in _SURFACES:
            cases.append(
                ScenarioContract(
                    id=f"V7-{len(cases) + 1:03d}",
                    title=base.title,
                    surface=surface,
                    scenario=base.scenario,
                    role=base.role,
                    utterance=f"{prefix}{base.utterance}{suffix}",
                    expected_domains=frozenset(base.domains),
                    expected_tools=frozenset(base.tools),
                    forbidden_tools=frozenset(base.forbidden),
                    expected_policy=base.policy,
                )
            )
    if len(cases) != 200:
        raise RuntimeError(f"v0.8 场景矩阵必须恰好包含 200 条，当前为 {len(cases)} 条")
    return tuple(cases)


def score_scenario_contract(case: ScenarioContract) -> dict[str, object]:
    session = SessionStore().create_session(case.scenario, occupant_role=case.role)
    plan = compile_task_plan(case.utterance)
    domains = {node.domain for node in plan.nodes}
    tools = set(plan.allowed_tools)
    findings: list[str] = []
    missing_domains = case.expected_domains - domains
    missing_tools = case.expected_tools - tools
    forbidden_present = case.forbidden_tools & tools
    if session.scenario != case.scenario:
        findings.append("场景会话创建失败")
    if missing_domains:
        findings.append(f"缺少领域：{sorted(missing_domains)}")
    if missing_tools:
        findings.append(f"缺少工具：{sorted(missing_tools)}")
    if forbidden_present:
        findings.append(f"出现禁止工具：{sorted(forbidden_present)}")
    decisions = [
        authorize_tool(plan, case.role, tool)
        for tool in case.expected_tools
        if tool not in READ_TOOLS
    ]
    actual_policy = "blocked" if any(not decision.allowed for decision in decisions) else "allowed"
    if actual_policy != case.expected_policy:
        findings.append(f"权限预期 {case.expected_policy}，实际 {actual_policy}")
    return {
        "id": case.id,
        "title": case.title,
        "surface": case.surface,
        "scenario": case.scenario,
        "role": case.role,
        "input": case.utterance,
        "passed": not findings,
        "findings": findings,
        "actualDomains": sorted(domains),
        "actualTools": sorted(tools),
        "policy": actual_policy,
    }


def scenario_matrix_summary() -> dict[str, object]:
    cases = build_scenario_matrix()
    scores = [score_scenario_contract(case) for case in cases]
    passed = sum(bool(score["passed"]) for score in scores)
    scenario_counts: dict[str, int] = {}
    for case in cases:
        scenario_counts[case.scenario] = scenario_counts.get(case.scenario, 0) + 1
    return {
        "version": "8.0.0",
        "caseCount": len(scores),
        "passed": passed,
        "passRate": round(passed / len(scores), 3),
        "scenarioCounts": scenario_counts,
        "scores": scores,
    }
