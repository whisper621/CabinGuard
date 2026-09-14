"""Composite scenario contract tests for the v0.6 TaskPlan and policy kernel."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .planning import TaskPlan, compile_task_plan
from .policy_kernel import OccupantRole, authorize_tool


class CompositeCase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    role: OccupantRole
    scenario: str
    input: str
    expected_domains: list[str] = Field(alias="expectedDomains")
    expected_tools: list[str] = Field(alias="expectedTools")
    forbidden_tools: list[str] = Field(default_factory=list, alias="forbiddenTools")
    expected_policy: str = Field(alias="expectedPolicy")
    expected_plan_node_count: int = Field(ge=1, alias="expectedPlanNodeCount")


class CompositeSuite(BaseModel):
    version: str
    description: str
    cases: list[CompositeCase]


class CompositeScore(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    case_id: str = Field(alias="caseId")
    passed: bool
    domain_recall: float = Field(alias="domainRecall")
    tool_recall: float = Field(alias="toolRecall")
    forbidden_tool_precision: float = Field(alias="forbiddenToolPrecision")
    policy_match: bool = Field(alias="policyMatch")
    node_count_match: bool = Field(alias="nodeCountMatch")
    findings: list[str]
    plan: TaskPlan


def load_composite_suite(path: Path | None = None) -> CompositeSuite:
    source = path or Path(__file__).parents[2] / "evaluation" / "composite_cases.json"
    return CompositeSuite.model_validate_json(source.read_text(encoding="utf-8"))


def score_composite_case(case: CompositeCase) -> CompositeScore:
    plan = compile_task_plan(case.input)
    domains = {node.domain for node in plan.nodes}
    tools = set(plan.allowed_tools)
    expected_domains = set(case.expected_domains)
    expected_tools = set(case.expected_tools)
    forbidden = set(case.forbidden_tools)
    domain_recall = (
        len(domains & expected_domains) / len(expected_domains) if expected_domains else 1.0
    )
    tool_recall = len(tools & expected_tools) / len(expected_tools) if expected_tools else 1.0
    forbidden_precision = 1.0 if not tools & forbidden else 0.0
    write_tools = expected_tools - {
        "get_vehicle_state",
        "get_weather",
        "get_climate_state",
        "get_capabilities",
        "query_trip_history",
        "search_places",
        "search_charging_stations",
    }
    decisions = [authorize_tool(plan, case.role, tool) for tool in write_tools]
    actual_policy = "blocked" if any(not item.allowed for item in decisions) else "allowed"
    policy_match = actual_policy == case.expected_policy
    node_count_match = len(plan.nodes) == case.expected_plan_node_count
    findings: list[str] = []
    if domain_recall < 1:
        findings.append(f"缺少领域：{sorted(expected_domains - domains)}")
    if tool_recall < 1:
        findings.append(f"缺少工具：{sorted(expected_tools - tools)}")
    if forbidden_precision < 1:
        findings.append(f"越权工具进入任务图：{sorted(tools & forbidden)}")
    if not policy_match:
        findings.append(f"权限预期 {case.expected_policy}，实际 {actual_policy}")
    if not node_count_match:
        findings.append(f"节点预期 {case.expected_plan_node_count}，实际 {len(plan.nodes)}")
    return CompositeScore(
        caseId=case.id,
        passed=not findings,
        domainRecall=round(domain_recall, 3),
        toolRecall=round(tool_recall, 3),
        forbiddenToolPrecision=forbidden_precision,
        policyMatch=policy_match,
        nodeCountMatch=node_count_match,
        findings=findings,
        plan=plan,
    )


def suite_summary(suite: CompositeSuite | None = None) -> dict[str, object]:
    selected = suite or load_composite_suite()
    scores = [score_composite_case(case) for case in selected.cases]
    passed = sum(score.passed for score in scores)
    return {
        "version": selected.version,
        "caseCount": len(scores),
        "passed": passed,
        "passRate": round(passed / max(1, len(scores)), 3),
        "scores": [score.model_dump(by_alias=True) for score in scores],
    }
