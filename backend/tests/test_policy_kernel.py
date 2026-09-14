from cabinguard.planning import compile_task_plan
from cabinguard.policy_kernel import authorize_tool


def test_guest_cannot_start_navigation() -> None:
    plan = compile_task_plan("导航去北京南站")
    decision = authorize_tool(plan, "guest", "plan_navigation")
    assert decision.allowed is False
    assert decision.code == "occupant_role_forbidden"


def test_front_passenger_can_adjust_comfort() -> None:
    plan = compile_task_plan("把空调调到22度")
    decision = authorize_tool(plan, "front_passenger", "set_climate")
    assert decision.allowed is True


def test_front_passenger_cannot_operate_driver_window() -> None:
    plan = compile_task_plan("把主驾车窗打开一半")
    decision = authorize_tool(
        plan,
        "front_passenger",
        "control_cabin_device",
        {"device": "window", "zone": "driver", "action": "set_position", "value": 50},
    )
    assert decision.allowed is False
    assert decision.code == "occupant_resource_forbidden"


def test_driver_is_still_blocked_outside_task_plan() -> None:
    plan = compile_task_plan("你好")
    decision = authorize_tool(plan, "driver", "control_trunk")
    assert decision.allowed is False
    assert decision.code == "tool_outside_task_plan"
