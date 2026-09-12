import pytest
from cabinguard.models import Trace
from cabinguard.policy import (
    classify_confirmation,
    ground_agent_message,
    is_navigation_requested,
)


@pytest.mark.parametrize("text", ["确认继续", "我确认", "可以打开", "好的", "打开吧"])
def test_accepts_explicit_confirmation(text: str) -> None:
    assert classify_confirmation(text) == "confirm"


@pytest.mark.parametrize("text", ["取消", "不要打开", "好吧，不要打开了", "不好", "我不同意"])
def test_cancellation_wins(text: str) -> None:
    assert classify_confirmation(text) == "cancel"


@pytest.mark.parametrize("text", ["天气好吗？", "为什么有风险？", "我再想想", "打开天窗安全吗？"])
def test_does_not_infer_authorization(text: str) -> None:
    assert classify_confirmation(text) == "none"


def test_distinguishes_search_from_navigation() -> None:
    assert not is_navigation_requested("帮我找一个顺路快充站")
    assert is_navigation_requested("找个顺路快充并导航")


def test_replaces_ungrounded_success_claim() -> None:
    assert "不能确认" in ground_agent_message("已帮你打开天窗。", [])


def test_keeps_grounded_success_claim() -> None:
    trace = Trace(
        id="1",
        name="control_sunroof",
        input={},
        output={"executed": True},
        status="success",
    )
    assert ground_agent_message("已帮你打开天窗。", [trace]) == "已帮你打开天窗。"


def test_surfaces_the_latest_block_reason() -> None:
    trace = Trace(
        id="1",
        name="control_sunroof",
        input={},
        output={"reason": "正在下雨"},
        status="blocked",
    )
    assert ground_agent_message("已经打开。", [trace]) == "本次操作未执行：正在下雨。"
