from cabinguard.utterance import (
    cabin_device_clarification,
    deterministic_cabin_tool_inputs,
    deterministic_climate_tool_inputs,
    deterministic_extended_tool_inputs,
    navigation_query,
    normalize_user_utterance,
    order_deterministic_tool_inputs,
    resolve_cabin_device_defaults,
    resolve_contextual_followup,
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


def test_current_song_query_does_not_start_new_playback() -> None:
    assert deterministic_extended_tool_inputs("现在播放的是什么歌？") == [
        ("get_media_state", {})
    ]


def test_parses_purifier_level_before_or_after_device_name() -> None:
    before = deterministic_extended_tool_inputs("打开3挡净化器")
    after = deterministic_extended_tool_inputs("打开净化器三挡")
    assert before == [("control_air_quality", {"purifier_enabled": True, "purifier_level": 3})]
    assert after == before


def test_four_windows_are_compiled_as_one_all_zone_write() -> None:
    calls = deterministic_cabin_tool_inputs(
        "麻烦把四个车窗都开到20%吧",
        speed_kmh=0,
        occupant_role="driver",
    )
    assert calls == [
        (
            "control_cabin_device",
            {"device": "window", "zone": "all", "action": "set_position", "value": 20},
        )
    ]


def test_explicit_climate_slots_preserve_unspecified_current_values() -> None:
    calls = deterministic_climate_tool_inputs(
        "空调调到23度",
        target_temperature_c=24,
        fan_level=2,
        circulation="内循环",
    )
    assert calls == [
        ("get_climate_state", {}),
        (
            "set_climate",
            {"target_temperature_c": 23.0, "fan_level": 2, "circulation": "内循环"},
        ),
    ]


def test_generic_media_and_fragrance_requests_require_slots() -> None:
    assert "播放内容" in str(cabin_device_clarification("给我播放一下"))
    assert "香氛类型" in str(cabin_device_clarification("打开香氛"))
    assert "座椅动作" in str(cabin_device_clarification("帮我调一下座椅"))


def test_resolves_door_zone_followup_from_previous_user_turn() -> None:
    assert resolve_contextual_followup(
        "右后车门",
        [{"role": "user", "content": "打开车门"}, {"role": "assistant", "content": "请补充车门"}],
    ) == "打开右后车门"
    assert deterministic_extended_tool_inputs("打开右后车门") == [
        (
            "control_door",
            {"door": "rear_right", "action": "open", "confirmed": False},
        )
    ]


def test_rain_visibility_batch_keeps_defrost_and_mirror_actions() -> None:
    cabin_calls = deterministic_cabin_tool_inputs(
        "打开自动雨刷、前后除霜，再打开两侧后视镜加热",
        speed_kmh=0,
        occupant_role="driver",
    )
    extended_calls = deterministic_extended_tool_inputs(
        "打开自动雨刷、前后除霜，再打开两侧后视镜加热"
    )
    assert cabin_calls[0][1]["device"] == "defrost"
    assert cabin_calls[0][1]["zone"] == "all"
    assert [name for name, _ in extended_calls] == ["control_wiper", "control_mirror"]
    ordered = order_deterministic_tool_inputs(
        "打开自动雨刷、前后除霜，再打开两侧后视镜加热",
        [*cabin_calls, *extended_calls],
    )
    assert [name for name, _ in ordered] == [
        "control_wiper",
        "control_cabin_device",
        "control_mirror",
    ]


def test_rest_music_phrase_uses_provider_friendly_query() -> None:
    assert deterministic_extended_tool_inputs("播放一点适合休息的轻音乐") == [
        ("play_media", {"query": "轻音乐 放松", "limit": 6})
    ]
