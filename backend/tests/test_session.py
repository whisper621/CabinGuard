import time
from uuid import uuid4

import pytest
from cabinguard.session import RATE_LIMIT, SessionStore


@pytest.mark.parametrize(
    ("scenario", "speed", "rain_probability"),
    [
        ("default", 82, 20),
        ("rain", 0, 70),
        ("moving", 35, 20),
    ],
)
def test_creates_isolated_scenarios(scenario: str, speed: int, rain_probability: int) -> None:
    store = SessionStore()
    session = store.create_session(scenario)  # type: ignore[arg-type]
    assert session.vehicle.speed == speed
    assert session.vehicle.rain_probability == rain_probability


def test_consumes_confirmation_once() -> None:
    store = SessionStore()
    session = store.create_session()
    store.create_sunroof_confirmation(session, 50)
    assert store.take_sunroof_confirmation(session).target_percent == 50  # type: ignore[union-attr]
    assert store.take_sunroof_confirmation(session) is None


def test_expires_confirmation() -> None:
    store = SessionStore()
    session = store.create_session()
    store.create_sunroof_confirmation(session, 30)
    assert session.pending_action is not None
    session.pending_action.expires_at = time.time() - 1
    assert store.take_sunroof_confirmation(session) is None


def test_rejects_request_after_rate_limit() -> None:
    store = SessionStore()
    key = f"test-{uuid4()}"
    for _ in range(RATE_LIMIT):
        assert store.consume_rate_limit(key)[0]
    allowed, retry_after = store.consume_rate_limit(key)
    assert not allowed
    assert retry_after >= 1


def test_missing_session_returns_none() -> None:
    assert SessionStore().get_session(str(uuid4())) is None
