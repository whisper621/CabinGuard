"""Deterministic normalization and slot checks for spoken cabin commands."""

import re
from collections.abc import Sequence

_LEADING_CONNECTORS = re.compile(r"^(?:(?:并且|然后|还有|同时|顺便|再)\s*)+")
_PUNCTUATION = re.compile(r"[，,。；;！？!?、]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_user_utterance(text: str) -> str:
    """Clean common Chinese ASR fillers without changing task semantics."""

    normalized = text.strip()
    normalized = re.sub(r"[嗯呃]+", "", normalized)
    normalized = re.sub(
        r"(^|并且|然后|还有|同时|顺便|再|[，,。；;！？!?、])(?:额+|那个|就是)(?=$|\s|[，,。；;！？!?、]|帮|给|把|打开|开启|关闭|调|导航|注意)",
        r"\1",
        normalized,
    )
    normalized = normalized.replace("前橱窗", "前车窗").replace("橱窗", "车窗")
    normalized = _PUNCTUATION.sub("，", normalized)
    normalized = _WHITESPACE.sub(" ", normalized).strip(" ，")
    normalized = _LEADING_CONNECTORS.sub("", normalized).strip(" ，")
    return normalized or text.strip()


def _has_seat_zone(text: str) -> bool:
    return bool(
        re.search(
            r"主驾|驾驶位|司机位|副驾|前排乘客|左后|后排左|右后|后排右|全部座椅|所有座椅|全车座椅",
            text,
        )
    )


def _has_seat_level(text: str) -> bool:
    return bool(
        re.search(
            r"(?:座椅|通风|加热).{0,10}[0-3零一二三]\s*(?:档|挡)|"
            r"[0-3零一二三]\s*(?:档|挡).{0,10}(?:座椅|通风|加热)|"
            r"(?:关闭|关掉).{0,8}(?:座椅|通风|加热)",
            text,
        )
    )


def _has_window_zone(text: str) -> bool:
    return bool(
        re.search(
            r"主驾|驾驶位|司机位|副驾|前排乘客|左后|后排左|右后|后排右|"
            r"全部车窗|所有车窗|全车车窗|四个车窗|四窗",
            text,
        )
    )


def _has_window_position(text: str) -> bool:
    return bool(
        re.search(
            r"车窗.{0,10}(?:\d{1,3}\s*%|百分之\s*\d{1,3}|[一二三四五六七八九]\s*成|一半|半开|全开|完全打开|关闭|关上|关掉)|"
            r"(?:\d{1,3}\s*%|百分之\s*\d{1,3}|[一二三四五六七八九]\s*成|一半|半开|全开|完全打开|关闭|关上|关掉).{0,10}车窗",
            text,
        )
    )


def cabin_device_clarification(text: str) -> str | None:
    """Return one consolidated clarification before any partial cabin write."""

    missing: list[str] = []
    seat_action = bool(
        re.search(r"座椅.{0,8}(?:通风|加热)|(?:通风|加热).{0,8}座椅", text)
    )
    window_action = "车窗" in text and bool(
        re.search(r"打开|开启|开到|调到|关闭|关上|关掉", text)
    )
    door_action = bool(
        re.search(r"(?:打开|开启|关闭|关上).{0,6}车门|打开车门|开启车门|开门|关门", text)
    )
    generic_media_play = bool(
        re.fullmatch(r"(?:请|麻烦)?(?:给我)?(?:播放|放)(?:一下|音乐|歌曲)?(?:吧)?", text)
    )
    fragrance_action = "香氛" in text and bool(re.search(r"打开|开启", text))
    generic_seat_adjust = "座椅" in text and bool(re.search(r"调一下|调整", text)) and not seat_action

    if seat_action:
        seat_parts: list[str] = []
        if not _has_seat_zone(text):
            seat_parts.append("座位（如主驾）")
        if not _has_seat_level(text):
            seat_parts.append("挡位（0—3 挡）")
        if seat_parts:
            missing.append("座椅的" + "和".join(seat_parts))

    if window_action:
        window_parts: list[str] = []
        if not _has_window_zone(text):
            window_parts.append("位置（主驾/副驾/左后/右后）")
        if not _has_window_position(text):
            window_parts.append("开度（如 20%、一半或关闭）")
        if window_parts:
            missing.append("车窗的" + "和".join(window_parts))

    if door_action and not _has_window_zone(text):
        missing.append("目标车门（主驾/副驾/左后/右后）")
    if generic_media_play:
        missing.append("播放内容（歌名、歌手或音乐风格）")
    if fragrance_action and not re.search(r"森林|海洋|柑橘", text):
        missing.append("香氛类型（森林/海洋/柑橘）")
    if generic_seat_adjust:
        missing.append("座椅动作和参数（如主驾通风 2 挡）")

    if not missing:
        return None
    details = "；".join(missing)
    return f"我已识别到任务，但为避免误操作，暂未执行。请补充{details}，补充后我会继续。"


def resolve_contextual_followup(text: str, history: Sequence[dict[str, str]]) -> str:
    """Resolve a narrow multi-turn slot answer without letting history invent new work."""

    if not re.fullmatch(r"(?:主驾|驾驶位|司机位|副驾|前排乘客|左后|后排左|右后|后排右)(?:车门)?", text):
        return text
    previous_user = next(
        (
            str(item.get("content") or "")
            for item in reversed(history)
            if item.get("role") == "user"
        ),
        "",
    )
    if not re.search(r"打开车门|开启车门|关闭车门|关上车门|开门|关门", previous_user):
        return text
    action = "关闭" if re.search(r"关闭|关上|关门", previous_user) else "打开"
    target = text if text.endswith("车门") else f"{text}车门"
    return f"{action}{target}"


def deterministic_climate_tool_inputs(
    text: str,
    *,
    target_temperature_c: float,
    fan_level: int,
    circulation: str,
) -> list[tuple[str, dict[str, object]]]:
    """Compile explicit climate slots while preserving unspecified current settings."""

    if not re.search(r"空调|温度|风量|内循环|外循环", text):
        return []
    temperature = re.search(r"(?:调到|设为|设置为|保持)?\s*(1[6-9]|2\d|30)\s*(?:度|℃)", text)
    fan = re.search(r"风量.{0,5}?([1-5一二三四五])\s*(?:档|挡)?", text)
    explicit_circulation = "外循环" if "外循环" in text else "内循环" if "内循环" in text else None
    if not (temperature or fan or explicit_circulation):
        return []
    number_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
    raw_fan = fan.group(1) if fan else None
    arguments: dict[str, object] = {
        "target_temperature_c": float(temperature.group(1)) if temperature else target_temperature_c,
        "fan_level": number_map.get(raw_fan, int(raw_fan) if raw_fan and raw_fan.isdigit() else fan_level),
        "circulation": explicit_circulation or circulation,
    }
    return [("get_climate_state", {}), ("set_climate", arguments)]


def resolve_cabin_device_defaults(
    text: str,
    *,
    speed_kmh: float,
    occupant_role: str,
) -> tuple[str, list[str]]:
    """Resolve low-risk omitted values so a routine multi-task can continue."""

    zone_by_role = {
        "driver": "主驾",
        "front_passenger": "副驾",
        "rear_child": "左后",
        "guest": "副驾",
    }
    default_zone = zone_by_role.get(occupant_role, "主驾")
    defaults: list[str] = []
    seat_action = bool(
        re.search(r"座椅.{0,8}(?:通风|加热)|(?:通风|加热).{0,8}座椅", text)
    )
    window_action = "车窗" in text and bool(
        re.search(r"打开|开启|开到|调到|关闭|关上|关掉", text)
    )

    if seat_action:
        if not _has_seat_zone(text):
            defaults.append(f"座椅位置={default_zone}")
        if not _has_seat_level(text):
            defaults.append("座椅加热/通风挡位=1挡")

    if window_action:
        if not _has_window_zone(text):
            defaults.append(f"车窗位置={default_zone}")
        if not _has_window_position(text):
            safe_position = 10 if speed_kmh >= 80 else 20
            defaults.append(f"车窗开度={safe_position}%")

    if not defaults:
        return text, []
    directive = "；".join(defaults)
    return (
        f"{text}。用户未指定的普通舒适参数采用以下安全默认值：{directive}。"
        "请完成全部明确任务，并在最终回复中说明这些默认值。",
        defaults,
    )


def _tool_zone(text: str, occupant_role: str) -> str:
    if re.search(r"主驾|驾驶位|司机位", text):
        return "driver"
    if re.search(r"副驾|前排乘客", text):
        return "passenger"
    if re.search(r"左后|后排左", text):
        return "rear_left"
    if re.search(r"右后|后排右", text):
        return "rear_right"
    return {
        "driver": "driver",
        "front_passenger": "passenger",
        "rear_child": "rear_left",
        "guest": "passenger",
    }.get(occupant_role, "driver")


def _seat_level(text: str, mode: str) -> int:
    keyword = "加热" if mode == "heat" else "通风"
    match = re.search(
        rf"(?:座椅)?{keyword}.{{0,8}}?([0-3零一二三])\s*(?:档|挡)|"
        rf"([0-3零一二三])\s*(?:档|挡).{{0,8}}?(?:座椅)?{keyword}",
        text,
    )
    if not match:
        return 1
    value = match.group(1) or match.group(2)
    chinese_levels = {"零": 0, "一": 1, "二": 2, "三": 3}
    return chinese_levels[value] if value in chinese_levels else int(value)


def _window_position(text: str, speed_kmh: float) -> int:
    if re.search(r"车窗.{0,8}(?:关闭|关上|关掉)|(?:关闭|关上|关掉).{0,8}车窗", text):
        return 0
    if re.search(r"车窗.{0,8}(?:一半|半开)|(?:一半|半开).{0,8}车窗", text):
        return 50
    if re.search(r"车窗.{0,8}(?:全开|完全打开)|(?:全开|完全打开).{0,8}车窗", text):
        return 100
    match = re.search(r"车窗.{0,10}?(\d{1,3})\s*%|(\d{1,3})\s*%.{0,8}?车窗", text)
    if match:
        return min(100, int(match.group(1) or match.group(2)))
    return 10 if speed_kmh >= 80 else 20


def deterministic_cabin_tool_inputs(
    text: str,
    *,
    speed_kmh: float,
    occupant_role: str,
) -> list[tuple[str, dict[str, object]]]:
    """Parse routine device-on actions into bounded deterministic tool inputs."""

    if re.search(r"全部座椅|所有座椅|全车座椅", text):
        return []
    zone = _tool_zone(text, occupant_role)
    calls: list[tuple[str, dict[str, object]]] = []
    if "车窗" in text and re.search(r"打开|开启|开到|关闭|关上|关掉", text):
        calls.append(
            (
                "control_cabin_device",
                {
                    "device": "window",
                    "zone": "all"
                    if re.search(r"全部车窗|所有车窗|全车车窗|四个车窗|四窗", text)
                    else zone,
                    "action": "set_position",
                    "value": _window_position(text, speed_kmh),
                },
            )
        )
    if re.search(r"座椅.{0,8}加热|加热.{0,8}座椅", text):
        calls.append(
            (
                "control_cabin_device",
                {
                    "device": "seat",
                    "zone": zone,
                    "action": "heat",
                    "value": _seat_level(text, "heat"),
                },
            )
        )
    if re.search(r"座椅.{0,8}通风|通风.{0,8}座椅", text):
        calls.append(
            (
                "control_cabin_device",
                {
                    "device": "seat",
                    "zone": zone,
                    "action": "ventilate",
                    "value": _seat_level(text, "ventilate"),
                },
            )
        )
    if "氛围灯" in text:
        if re.search(r"关闭氛围灯|关掉氛围灯", text):
            light_input: dict[str, object] = {
                "device": "ambient_light",
                "zone": "all",
                "action": "turn_off",
            }
        else:
            color = next(
                (
                    value
                    for label, value in {
                        "冰蓝": "ice_blue",
                        "蓝色": "ice_blue",
                        "暖橙": "warm_orange",
                        "橙色": "warm_orange",
                        "紫色": "violet",
                        "白色": "white",
                    }.items()
                    if label in text
                ),
                None,
            )
            brightness = re.search(
                r"亮度\s*(\d{1,3})\s*%|氛围灯.{0,12}?(\d{1,3})\s*%",
                text,
            )
            light_input = {
                "device": "ambient_light",
                "zone": "all",
                "action": "set_light" if color or brightness else "turn_on",
            }
            if color:
                light_input["color"] = color
            if brightness:
                light_input["value"] = min(100, int(brightness.group(1) or brightness.group(2)))
        calls.append(("control_cabin_device", light_input))
    if re.search(r"除霜|除雾", text) and (
        not re.search(r"后视镜", text) or re.search(r"前后|前挡|后挡|风挡|玻璃", text)
    ):
        if re.search(r"后挡|后风挡", text):
            defrost_zone = "rear"
        elif re.search(r"前后|全部|所有|都", text):
            defrost_zone = "all"
        else:
            defrost_zone = "front"
        calls.append(
            (
                "control_cabin_device",
                {
                    "device": "defrost",
                    "zone": defrost_zone,
                    "action": "turn_off" if re.search(r"关闭|关掉", text) else "turn_on",
                },
            )
        )
    return calls


def _media_query(text: str) -> str:
    match = re.search(
        r"(?:播放|放点|放首|放一首|来点|来首|来一首|听)(.+?)(?=并且|然后|同时|顺便|再导航|，|。|；|$)",
        text,
    )
    query = (match.group(1) if match else "").strip(" 一下点首的")
    if "轻音乐" in query and re.search(r"休息|放松|睡眠|舒缓", query):
        return "轻音乐 放松"
    if query in {"", "音乐", "歌曲", "歌"}:
        return "轻音乐"
    return query


def order_deterministic_tool_inputs(
    text: str,
    calls: list[tuple[str, dict[str, object]]],
) -> list[tuple[str, dict[str, object]]]:
    """Keep independent deterministic actions in the order spoken by the user."""

    def first_position(*keywords: str) -> int:
        positions = [
            text.find(keyword)
            for keyword in keywords
            if keyword and text.find(keyword) >= 0
        ]
        return min(positions) if positions else len(text) + 1

    def position(call: tuple[str, dict[str, object]]) -> int:
        name, arguments = call
        if name in {"get_climate_state", "set_climate"}:
            return first_position("空调", "温度", "风量", "内循环", "外循环")
        if name == "control_cabin_device":
            return first_position(
                {
                    "window": "车窗",
                    "seat": "座椅",
                    "ambient_light": "氛围灯",
                    "defrost": "除霜",
                }.get(str(arguments.get("device")), ""),
                "除雾" if arguments.get("device") == "defrost" else "",
            )
        return first_position(
            {
                "control_sunroof": "天窗",
                "control_door": "车门",
                "control_wiper": "雨刷",
                "control_mirror": "后视镜",
                "control_air_quality": "空气",
                "control_child_lock": "儿童锁",
                "control_charge_port": "充电口",
                "play_media": "播放",
                "control_media": "音量",
                "get_media_state": "播放",
            }.get(name, ""),
        )

    return sorted(calls, key=position)


def deterministic_extended_tool_inputs(text: str) -> list[tuple[str, dict[str, object]]]:
    """Parse high-value media/body commands so demonstrations do not depend on model phrasing."""

    calls: list[tuple[str, dict[str, object]]] = []
    media_state_query = bool(
        re.search(r"(?:正在|现在|当前).*(?:播放|听).*(?:什么|哪首)|这是什么歌|歌名", text)
    )
    if "天窗" in text and re.search(r"\d+\s*%|一半|半开|全开|完全打开|关闭|关上|关掉", text):
        if re.search(r"关闭|关上|关掉", text):
            target_percent = 0
        elif re.search(r"一半|半开", text):
            target_percent = 50
        elif re.search(r"全开|完全打开", text):
            target_percent = 100
        else:
            match = re.search(r"(\d{1,3})\s*%", text)
            target_percent = min(100, int(match.group(1))) if match else 0
        calls.append(
            (
                "control_sunroof",
                {"target_percent": target_percent, "confirmed": False},
            )
        )
    if re.search(r"(?:打开|开启|关闭|关上).{0,6}车门|开门|关门", text) and _has_window_zone(text):
        calls.append(
            (
                "control_door",
                {
                    "door": _tool_zone(text, "driver"),
                    "action": "close" if re.search(r"关闭|关上|关门", text) else "open",
                    "confirmed": False,
                },
            )
        )
    if re.search(r"雨刷|雨刮", text):
        if re.search(r"关闭|关掉|停止", text):
            mode = "off"
        elif re.search(r"暴雨|大雨|高速|最大", text):
            mode = "high"
        elif re.search(r"中速|中档|中挡", text):
            mode = "medium"
        elif re.search(r"低速|慢速|低档|低挡", text):
            mode = "slow"
        else:
            mode = "auto"
        calls.append(("control_wiper", {"mode": mode}))
    if "后视镜" in text:
        mirror_input: dict[str, object] = {"side": "both"}
        if re.search(r"加热|除雾|看不清", text):
            mirror_input["heating"] = not bool(re.search(r"关闭|关掉", text))
        if re.search(r"折叠|收起", text):
            mirror_input["folded"] = True
        elif re.search(r"展开|打开", text):
            mirror_input["folded"] = False
        if len(mirror_input) > 1:
            calls.append(("control_mirror", mirror_input))
    if re.search(r"空气净化|净化器|空气不好|异味|味儿|PM2\.5|香氛", text):
        air_input: dict[str, object] = {}
        if re.search(r"空气净化|净化器|空气不好|异味|味儿|PM2\.5", text):
            disabled = bool(re.search(r"关闭(?:空气净化|净化器)|关掉(?:空气净化|净化器)", text))
            air_input["purifier_enabled"] = not disabled
            if not disabled:
                level = re.search(
                    r"(?:净化(?:器)?.{0,6}([0-3一二三])\s*(?:档|挡)|"
                    r"([0-3一二三])\s*(?:档|挡).{0,4}净化(?:器)?)",
                    text,
                )
                mapping = {"一": 1, "二": 2, "三": 3}
                raw = next((group for group in level.groups() if group), "2") if level else "2"
                air_input["purifier_level"] = mapping.get(raw, int(raw) if raw.isdigit() else 2)
        if "香氛" in text:
            fragrance = "off" if re.search(r"关闭|关掉", text) else next(
                (value for label, value in {"森林": "forest", "海洋": "ocean", "柑橘": "citrus"}.items() if label in text),
                "forest",
            )
            air_input["fragrance"] = fragrance
        calls.append(("control_air_quality", air_input))
    if "儿童锁" in text:
        calls.append(("control_child_lock", {"enabled": not bool(re.search(r"关闭|关掉", text))}))
    if re.search(r"充电口|充电盖", text):
        calls.append(
            (
                "control_charge_port",
                {"action": "close" if re.search(r"关闭|关上|关掉", text) else "open"},
            )
        )
    if media_state_query:
        calls.append(("get_media_state", {}))
    elif re.search(r"下一首|切歌", text):
        calls.append(("control_media", {"action": "next"}))
    elif "上一首" in text:
        calls.append(("control_media", {"action": "previous"}))
    elif re.search(r"暂停(?:音乐|播放)?", text):
        calls.append(("control_media", {"action": "pause"}))
    elif re.search(r"停止(?:音乐|播放)?|关闭音乐", text):
        calls.append(("control_media", {"action": "stop"}))
    elif match := re.search(r"音量.{0,5}?(\d{1,3})", text):
        calls.append(("control_media", {"action": "set_volume", "value": min(100, int(match.group(1)))}))
    elif re.search(r"播放|放点|放首|放一首|来点|来首|来一首|听.*(?:歌|音乐)", text):
        calls.append(("play_media", {"query": _media_query(text), "limit": 6}))
    return calls


def navigation_query(text: str) -> str | None:
    match = re.search(r"(?:导航到|导航去|带我去|前往)\s*([^，。；;]+)", text)
    return match.group(1).strip() if match else None
