import asyncio
from collections import Counter
from typing import Any

from cabinguard.agent import AgentService, DeepSeekError, ModelResult
from cabinguard.event_store import EventStore
from cabinguard.session import SessionStore


class FakeModelClient:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.calls = 0
        self.received_messages: list[list[dict[str, Any]]] = []

    async def call(self, _messages: list[dict[str, Any]]) -> ModelResult:
        self.received_messages.append(_messages)
        message = self.messages[self.calls]
        self.calls += 1
        return ModelResult(
            message=message,
            model="fake-model",
            usage={"total_tokens": 10},
        )


class FailingModelClient:
    async def call(self, _messages: list[dict[str, Any]]) -> ModelResult:
        raise DeepSeekError("provider unavailable")


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


def test_agent_enforces_rear_child_policy_and_writes_evidence() -> None:
    store = SessionStore()
    session = store.create_session(occupant_role="rear_child")
    events = EventStore(":memory:")
    client = FakeModelClient(
        [
            {
                "tool_calls": [
                    {"id": "state", "function": {"name": "get_vehicle_state", "arguments": "{}"}}
                ]
            },
            {
                "tool_calls": [
                    {
                        "id": "window",
                        "function": {
                            "name": "control_cabin_device",
                            "arguments": '{"device":"window","zone":"rear_left","action":"set_position","value":50}',
                        },
                    }
                ]
            },
            {"content": "儿童乘员的写操作需要监护授权。"},
        ]
    )
    service = AgentService(store, client, events=events)  # type: ignore[arg-type]
    result = asyncio.run(service.run(text="把左后车窗打开一半", session_id=session.id))

    assert result["vehicle"]["windows"]["rearLeft"] == 0
    assert result["traces"][-1]["policyCode"] == "guardian_authorization_required"
    assert result["traces"][-1]["status"] == "blocked"
    assert Counter(item["eventType"] for item in events.list_events(session.id)) == {
        "plan.created": 1,
        "policy.decision": 2,
        "tool.receipt": 2,
    }


def test_agent_blocks_tool_outside_compiled_plan() -> None:
    store = SessionStore()
    session = store.create_session()
    client = FakeModelClient(
        [
            {
                "tool_calls": [
                    {
                        "id": "malicious",
                        "function": {"name": "control_trunk", "arguments": '{"action":"open"}'},
                    }
                ]
            },
            {"content": "该动作不属于本轮请求，未执行。"},
        ]
    )
    service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]
    result = asyncio.run(service.run(text="你好", session_id=session.id))
    assert result["vehicle"]["trunkOpen"] is False
    assert result["traces"][0]["policyCode"] == "tool_outside_task_plan"


def test_agent_resolves_safe_defaults_for_filler_heavy_multi_device_request() -> None:
    store = SessionStore()
    session = store.create_session()
    client = FakeModelClient([{"content": "已按安全默认值处理组合请求。"}])
    service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]

    result = asyncio.run(
        service.run(
            text="并且嗯打开座椅通风打开氛围灯打开前橱窗嗯注意安全",
            session_id=session.id,
        )
    )

    assert result["model"] == "fake-model"
    assert result["turns"] == 2
    assert [trace["name"] for trace in result["traces"]] == [
        "get_vehicle_state",
        "control_cabin_device",
        "control_cabin_device",
        "control_cabin_device",
    ]
    assert result["vehicle"]["windows"]["driver"] == 10
    assert result["vehicle"]["seats"]["driverVentilation"] == 1
    assert result["vehicle"]["ambientLight"]["enabled"] is True
    assert "座椅加热/通风挡位=1挡" in result["message"]
    assert "车窗开度=10%" in result["message"]
    user_message = next(
        message for message in client.received_messages[0] if message["role"] == "user"
    )
    assert "用户未指定的普通舒适参数" in user_message["content"]
    assert client.calls == 1


def test_agent_returns_tool_receipts_when_final_model_call_fails() -> None:
    store = SessionStore()
    session = store.create_session()
    service = AgentService(
        store,
        FailingModelClient(),  # type: ignore[arg-type]
        events=EventStore(":memory:"),
    )

    result = asyncio.run(
        service.run(
            text="嗯打开主驾驶座椅加热并打开座椅通风，打开氛围灯和前车窗",
            session_id=session.id,
        )
    )

    assert result["model"] == "cabinguard-receipt-fallback"
    assert result["vehicle"]["windows"]["driver"] == 10
    assert result["vehicle"]["seats"]["driverHeating"] == 1
    assert result["vehicle"]["seats"]["driverVentilation"] == 1
    assert result["vehicle"]["ambientLight"]["enabled"] is True
    assert len(result["traces"]) == 5
    assert all(trace["status"] == "success" for trace in result["traces"])
