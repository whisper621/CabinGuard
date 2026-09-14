from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from .models import Trace

ConfirmationDecision = Literal["confirm", "cancel", "none"]

CANCEL_SIGNALS = (
    "取消",
    "不要",
    "别开",
    "停止",
    "算了",
    "不确认",
    "不同意",
    "不可以",
    "不行",
    "不好",
    "否",
)

EXPLICIT_CONFIRMATIONS = {
    "确认",
    "我确认",
    "确认继续",
    "继续",
    "继续执行",
    "继续打开",
    "可以",
    "可以打开",
    "同意",
    "我同意",
    "是",
    "是的",
    "好",
    "好的",
    "打开",
    "打开吧",
}

_PUNCTUATION = re.compile(r"[\s，。！？、,.!?；;：:“”'‘’]")
_NAVIGATION = re.compile(
    r"导航|带我去|送我去|我要去|去往|带路|规划路线|开始路线|怎么去|"
    r"前往.*(?:充电|超充|能源站)|去.*(?:充电|超充|能源站)"
)
_PLACE_SEARCH = re.compile(
    r"(?:查找|搜索|搜|找|附近).*(?:地点|地址|餐厅|饭店|咖啡|停车场|商场|医院|景点|公园|酒店)"
)
_SIDE_EFFECT = re.compile(
    r"已(?:经)?(?:将|为|帮|开始|完成|打开|关闭|设置|切换)|导航已开始|操作成功"
)


def _normalize(text: str) -> str:
    return _PUNCTUATION.sub("", text.strip().lower())


def classify_confirmation(text: str) -> ConfirmationDecision:
    """Only an explicit whole reply authorizes a pending high-risk action."""

    normalized = _normalize(text)
    if not normalized:
        return "none"
    if any(signal in normalized for signal in CANCEL_SIGNALS):
        return "cancel"
    return "confirm" if normalized in EXPLICIT_CONFIRMATIONS else "none"


def is_navigation_requested(text: str) -> bool:
    return bool(_NAVIGATION.search(text))


def is_place_search_requested(text: str) -> bool:
    return is_navigation_requested(text) or bool(_PLACE_SEARCH.search(text))


def ground_agent_message(message: str, traces: Sequence[Trace]) -> str:
    """Prevent a model from claiming a side effect without a successful receipt."""

    if not _SIDE_EFFECT.search(message):
        return message

    verified = any(
        trace.status == "success"
        and (trace.output.get("executed") is True or trace.output.get("navigation_started") is True)
        for trace in traces
    )
    if verified:
        return message

    blocked_reason = next(
        (
            trace.output.get("reason")
            for trace in reversed(traces)
            if trace.status == "blocked" and trace.output.get("reason")
        ),
        None,
    )
    if blocked_reason:
        return f"本次操作未执行：{blocked_reason}。"
    return "本次没有获得可核验的工具执行结果，因此我不能确认操作已经完成。"
