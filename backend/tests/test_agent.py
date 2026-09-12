import asyncio
from typing import Any

from cabinguard.agent import AgentService, ModelResult
from cabinguard.session import SessionStore


class FakeModelClient:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.calls = 0

    async def call(self, _messages: list[dict[str, Any]]) -> ModelResult:
        message = self.messages[self.calls]
        self.calls += 1
        return ModelResult(
            message=message,
            model="fake-model",
            usage={"total_tokens": 10},
        )


def test_multi_turn_agent_executes_read_then_write() -> None:
    store = SessionStore()
    session = store.create_session()
    client = FakeModelClient(
        [
            {
                "tool_calls": [
                    {
                        "id": "read",
                        "function": {
                            "name": "get_climate_state",
                            "arguments": "{}",
                        },
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "id": "write",
                        "function": {
                            "name": "set_climate",
                            "arguments": (
                                '{"target_temperature_c":23,"fan_level":3,"circulation":"外循环"}'
                            ),
                        },
                    }
                ]
            },
            {"content": "已将空调调到 23℃，风量 3 档并切换外循环。"},
        ]
    )
    service = AgentService(store, client)  # type: ignore[arg-type]
    result = asyncio.run(service.run(text="把空调调到23度", session_id=session.id))

    assert [trace["name"] for trace in result["traces"]] == [
        "get_climate_state",
        "set_climate",
    ]
    assert result["vehicle"]["targetTemperature"] == 23
    assert result["turns"] == 3
    assert result["totalTokens"] == 30


def test_agent_replaces_ungrounded_success_claim() -> None:
    store = SessionStore()
    session = store.create_session()
    client = FakeModelClient([{"content": "已经帮你打开天窗。"}])
    service = AgentService(store, client)  # type: ignore[arg-type]
    result = asyncio.run(service.run(text="你好", session_id=session.id))
    assert "不能确认" in result["message"]


def test_agent_creates_server_side_sunroof_confirmation() -> None:
    store = SessionStore()
    session = store.create_session()
    client = FakeModelClient(
        [
            {
                "tool_calls": [
                    {
                        "id": "state",
                        "function": {"name": "get_vehicle_state", "arguments": "{}"},
                    },
                    {
                        "id": "weather",
                        "function": {"name": "get_weather", "arguments": "{}"},
                    },
                ]
            },
            {
                "tool_calls": [
                    {
                        "id": "sunroof",
                        "function": {
                            "name": "control_sunroof",
                            "arguments": '{"target_percent":50,"confirmed":false}',
                        },
                    }
                ]
            },
            {"content": "当前高速行驶，需要你明确确认后才能打开天窗。"},
        ]
    )
    service = AgentService(store, client)  # type: ignore[arg-type]
    result = asyncio.run(service.run(text="把天窗开一半", session_id=session.id))

    assert result["traces"][-1]["status"] == "blocked"
    assert session.pending_action is not None
    assert session.pending_action.target_percent == 50
    assert result["vehicle"]["sunroof"] == 0
