from cabinguard.evaluation_v6 import load_composite_suite, score_composite_case
from cabinguard.planning import compile_task_plan


def test_compiles_cross_domain_task_into_dependency_waves() -> None:
    plan = compile_task_plan("空调调到22度并导航去故宫")

    assert {node.domain for node in plan.nodes} == {"system", "comfort", "navigation"}
    assert {"set_climate", "search_places", "plan_navigation"} <= set(plan.allowed_tools)
    search = next(node for node in plan.nodes if "search_places" in node.allowed_tools)
    route = next(node for node in plan.nodes if "plan_navigation" in node.allowed_tools)
    assert route.dependencies == [search.id]
    assert len(plan.execution_waves) >= 2


def test_task_plan_does_not_authorize_unrequested_body_action() -> None:
    plan = compile_task_plan("把空调调到23度")
    assert "control_trunk" not in plan.allowed_tools
    assert "control_sunroof" not in plan.allowed_tools


def test_ambiguous_writes_compile_to_clarification_only() -> None:
    climate = compile_task_plan("帮我调舒服一点")
    sunroof = compile_task_plan("帮我打开天窗")
    assert "set_climate" not in climate.allowed_tools
    assert "control_sunroof" not in sunroof.allowed_tools
    assert climate.nodes[0].title == "澄清舒适偏好"
    assert sunroof.nodes[-1].title == "澄清天窗开度"


def test_all_composite_contract_cases_pass() -> None:
    scores = [score_composite_case(case) for case in load_composite_suite().cases]
    failures = {score.case_id: score.findings for score in scores if not score.passed}
    assert failures == {}
    assert len(scores) == 24


def test_compiles_new_cockpit_domains_into_one_multi_task_plan() -> None:
    plan = compile_task_plan(
        "嗯，打开自动雨刷和后视镜加热，开启空气净化，然后播放轻音乐"
    )
    tools = set(plan.allowed_tools)
    assert {
        "control_wiper",
        "control_mirror",
        "control_air_quality",
        "play_media",
    } <= tools
    assert {node.domain for node in plan.nodes} >= {"body_safety", "comfort", "media"}


def test_current_song_query_is_read_only() -> None:
    plan = compile_task_plan("现在播放的是什么歌？")
    assert "get_media_state" in plan.allowed_tools
    assert "play_media" not in plan.allowed_tools
