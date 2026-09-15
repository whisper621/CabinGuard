"""Deterministic normalization and slot checks for spoken cabin commands."""

import re

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
            r"主驾|驾驶位|司机位|副驾|前排乘客|左后|后排左|右后|后排右|全部车窗|所有车窗|全车车窗",
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

    if not missing:
        return None
    details = "；".join(missing)
    return (
        f"我已识别到组合任务，但为避免只执行其中一部分，暂未操作。请补充{details}。"
        "例如：打开主驾座椅通风 2 挡，开启紫色氛围灯，并把主驾车窗打开 20%。"
    )


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

    if re.search(r"全部车窗|所有车窗|全车车窗|全部座椅|所有座椅|全车座椅", text):
        return []
    zone = _tool_zone(text, occupant_role)
    calls: list[tuple[str, dict[str, object]]] = []
    if "车窗" in text and re.search(r"打开|开启|开到|关闭|关上|关掉", text):
        calls.append(
            (
                "control_cabin_device",
                {
                    "device": "window",
                    "zone": zone,
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
    return calls


def navigation_query(text: str) -> str | None:
    match = re.search(r"(?:导航到|导航去|带我去|前往)\s*([^，。；;]+)", text)
    return match.group(1).strip() if match else None
