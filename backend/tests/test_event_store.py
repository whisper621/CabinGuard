from cabinguard.event_store import EventStore


def test_evidence_ledger_round_trips_structured_payload() -> None:
    events = EventStore(":memory:")
    written = events.append(
        session_id="session-1",
        plan_id="plan-1",
        task_id="task-1",
        event_type="policy.decision",
        state_version=2,
        payload={"allowed": False, "code": "test"},
    )
    loaded = events.list_events("session-1")
    assert loaded[0]["id"] == written["id"]
    assert loaded[0]["payload"] == {"allowed": False, "code": "test"}
