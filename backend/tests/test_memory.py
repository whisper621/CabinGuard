from cabinguard.memory import SessionMemoryExecutor
from cabinguard.session import SessionStore
from cabinguard.tools import ToolContext


def test_preference_write_requires_explicit_authorization() -> None:
    store = SessionStore()
    session = store.create_session()
    executor = SessionMemoryExecutor(store)
    result = executor.execute(
        "manage_preferences",
        {"action": "remember", "key": "空调温度", "value": "22℃"},
        session,
        ToolContext(memory_write_authorized=False),
    )
    assert result.status == "blocked"
    assert session.preferences == {}


def test_preference_can_be_written_and_listed_in_current_session() -> None:
    store = SessionStore()
    session = store.create_session()
    executor = SessionMemoryExecutor(store)
    written = executor.execute(
        "manage_preferences",
        {"action": "remember", "key": "空调温度", "value": "22℃"},
        session,
        ToolContext(memory_write_authorized=True),
    )
    listed = executor.execute(
        "manage_preferences",
        {"action": "list"},
        session,
        ToolContext(),
    )
    assert written.status == "success"
    assert listed.output["preferences"] == {"空调温度": "22℃"}
    assert listed.output["scope"] == "current_demo_session"


def test_trip_history_is_derived_from_recorded_receipts() -> None:
    store = SessionStore()
    session = store.create_session()
    store.record_trip(
        session,
        {"destination": "昌平区政府", "distanceKm": 31.2, "etaMinutes": 38},
    )
    result = SessionMemoryExecutor(store).execute(
        "query_trip_history", {}, session, ToolContext()
    )
    assert result.status == "success"
    assert result.output["trips"][0]["destination"] == "昌平区政府"  # type: ignore[index]
