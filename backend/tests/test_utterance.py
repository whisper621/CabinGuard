from cabinguard.utterance import (
    cabin_device_clarification,
    deterministic_cabin_tool_inputs,
    navigation_query,
    normalize_user_utterance,
    resolve_cabin_device_defaults,
)


def test_normalizes_fillers_and_common_window_asr_alias() -> None:
    assert normalize_user_utterance("并且嗯打开座椅通风，呃打开前橱窗") == "打开座椅通风，打开前车窗"


def test_collects_all_missing_slots_for_multi_device_request() -> None:
    message = cabin_device_clarification("打开座椅通风，打开氛围灯，打开前车窗")
    assert message is not None
    assert "座位" in message
    assert "挡位" in message
    assert "车窗" in message
    assert "开度" in message


def test_complete_multi_device_request_needs_no_clarification() -> None:
    assert (
        cabin_device_clarification(
            "打开主驾座椅通风 2 挡，开启紫色氛围灯，把主驾车窗打开 20%"
        )
        is None
    )


def test_resolves_safe_defaults_for_routine_multi_task() -> None:
    resolved, defaults = resolve_cabin_device_defaults(
        "打开车窗，打开主驾驶座椅加热和座椅通风，打开氛围灯",
        speed_kmh=82,
        occupant_role="driver",
    )

    assert defaults == ["座椅加热/通风挡位=1挡", "车窗开度=10%"]
    assert cabin_device_clarification(resolved) is None
    assert "完成全部明确任务" in resolved


def test_builds_deterministic_device_batch_and_navigation_query() -> None:
    text = "打开车窗打开主驾驶座椅加热打开座椅通风，打开紫色氛围灯，导航到天津师范大学"
    calls = deterministic_cabin_tool_inputs(
        text,
        speed_kmh=82,
        occupant_role="driver",
    )

    assert [arguments["device"] for _, arguments in calls] == [
        "window",
        "seat",
        "seat",
        "ambient_light",
    ]
    assert calls[0][1]["value"] == 10
    assert calls[1][1]["action"] == "heat"
    assert calls[2][1]["action"] == "ventilate"
    assert calls[3][1]["color"] == "violet"
    assert navigation_query(text) == "天津师范大学"
