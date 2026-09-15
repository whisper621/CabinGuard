import asyncio
from typing import Any

from cabinguard.agent import AgentService, DeepSeekError, ModelResult
from cabinguard.event_store import EventStore
from cabinguard.session import SessionStore


class CountingClient:
    model = "requested-test-model"

    def __init__(self, delay: float = 0) -> None:
        self.calls = 0
        self.delay = delay

    async def call(self, _messages: list[dict[str, Any]]) -> ModelResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return ModelResult(message={"content": "没有需要执行的动作。"}, model="resolved-test-model", usage={"total_tokens": 3})


class FailingClient:
    model = "requested-failing-model"

    async def call(self, _messages: list[dict[str, Any]]) -> ModelResult:
        raise DeepSeekError("provider unavailable")


def test_idempotency_replays_response_without_second_model_call() -> None:
    store = SessionStore()
    session = store.create_session()
    client = CountingClient()
    service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]

    first = asyncio.run(service.run(text="你好", session_id=session.id, idempotency_key="idem-key-0001"))
    second = asyncio.run(service.run(text="你好", session_id=session.id, idempotency_key="idem-key-0001"))

    assert client.calls == 1
    assert first["operation"]["status"] == "success"
    assert second["operation"]["replayed"] is True
    assert second["message"] == first["message"]


def test_stale_state_version_is_rejected_before_model_call() -> None:
    store = SessionStore()
    session = store.create_session()
    store.update_vehicle(session, session.vehicle.model_copy(update={"target_temperature": 23}))
    client = CountingClient()
    service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]

    result = asyncio.run(
        service.run(
            text="你好",
            session_id=session.id,
            idempotency_key="conflict-key-01",
            expected_state_version=1,
        )
    )

    assert client.calls == 0
    assert result["operation"]["status"] == "conflict"
    assert "状态" in result["message"]


def test_timeout_stops_operation_and_records_model_identity() -> None:
    store = SessionStore()
    session = store.create_session()
    client = CountingClient(delay=0.05)
    service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]

    result = asyncio.run(
        service.run(
            text="你好",
            session_id=session.id,
            idempotency_key="timeout-key-001",
            timeout_seconds=0.01,
        )
    )

    assert result["operation"]["status"] == "timed_out"
    assert result["requestedModel"] == "requested-test-model"
    assert result["resolvedModel"] is None
    assert result["executionSource"] == "operation-timeout"


def test_running_operation_can_be_cancelled_at_tool_boundary() -> None:
    async def exercise() -> dict[str, Any]:
        store = SessionStore()
        session = store.create_session()
        client = CountingClient(delay=0.05)
        service = AgentService(store, client, events=EventStore(":memory:"))  # type: ignore[arg-type]
        task = asyncio.create_task(
            service.run(
                text="你好",
                session_id=session.id,
                idempotency_key="cancel-key-001",
            )
        )
        await asyncio.sleep(0.01)
        operation = store.cancel_operation(session, idempotency_key="cancel-key-001")
        assert operation is not None
        return await task

    result = asyncio.run(exercise())
    assert result["operation"]["status"] == "cancelled"
    assert "已取消" in result["message"]


def test_failed_idempotent_operation_is_not_retried_as_an_empty_response() -> None:
    store = SessionStore()
    session = store.create_session()
    service = AgentService(store, FailingClient(), events=EventStore(":memory:"))  # type: ignore[arg-type]

    try:
        asyncio.run(service.run(text="你好", session_id=session.id, idempotency_key="failed-key-001"))
    except DeepSeekError:
        pass
    else:
        raise AssertionError("The first provider failure should propagate")

    replay = asyncio.run(service.run(text="你好", session_id=session.id, idempotency_key="failed-key-001"))

    assert replay["operation"]["status"] == "failed"
    assert replay["operation"]["replayed"] is True
    assert replay["resolvedModel"] is None
    assert replay["executionSource"] == "operation-lifecycle"
    assert "不会使用同一幂等键自动重试" in replay["message"]
