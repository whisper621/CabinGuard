from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from uuid import uuid4

from .models import Scenario, VehicleState

SESSION_TTL_SECONDS = 30 * 60
CONFIRMATION_TTL_SECONDS = 2 * 60
RATE_WINDOW_SECONDS = 5 * 60
RATE_LIMIT = 30
MAX_SESSIONS = 300


@dataclass
class PendingSunroofAction:
    target_percent: int
    expires_at: float


@dataclass
class CabinSession:
    id: str
    scenario: Scenario
    vehicle: VehicleState
    created_at: float
    expires_at: float
    pending_action: PendingSunroofAction | None = None
    place_candidates: dict[str, dict[str, object]] = field(default_factory=dict)
    preferences: dict[str, str] = field(default_factory=dict)
    trip_history: list[dict[str, object]] = field(default_factory=list)


@dataclass
class RateWindow:
    started_at: float
    count: int


def build_scenario(
    scenario: Scenario,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    accuracy_meters: float | None = None,
    allow_external_routing: bool = False,
) -> VehicleState:
    vehicle = VehicleState()
    if latitude is not None and longitude is not None:
        vehicle = vehicle.model_copy(
            update={
                "current_location": "浏览器授权位置",
                "latitude": latitude,
                "longitude": longitude,
                "location_source": "browser_geolocation",
                "location_accuracy_meters": accuracy_meters,
                "external_routing_consent": allow_external_routing,
            }
        )
    if scenario == "rain":
        return vehicle.model_copy(
            update={"speed": 0, "gear": "P", "weather": "小雨", "rain_probability": 70}
        )
    if scenario == "moving":
        return vehicle.model_copy(update={"speed": 35, "gear": "D"})
    return vehicle


class SessionStore:
    """In-memory demo state. A session id is not an authentication token."""

    def __init__(self) -> None:
        self._sessions: dict[str, CabinSession] = {}
        self._rate_windows: dict[str, RateWindow] = {}
        self._lock = threading.RLock()

    def _prune(self, now: float) -> None:
        expired_sessions = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired_sessions:
            self._sessions.pop(session_id, None)

        expired_windows = [
            key
            for key, window in self._rate_windows.items()
            if window.started_at + RATE_WINDOW_SECONDS <= now
        ]
        for key in expired_windows:
            self._rate_windows.pop(key, None)

        while len(self._sessions) >= MAX_SESSIONS:
            oldest_id = next(iter(self._sessions), None)
            if oldest_id is None:
                break
            self._sessions.pop(oldest_id, None)

    def create_session(
        self,
        scenario: Scenario = "default",
        *,
        latitude: float | None = None,
        longitude: float | None = None,
        accuracy_meters: float | None = None,
        allow_external_routing: bool = False,
    ) -> CabinSession:
        with self._lock:
            now = time.time()
            self._prune(now)
            session = CabinSession(
                id=str(uuid4()),
                scenario=scenario,
                vehicle=build_scenario(
                    scenario,
                    latitude=latitude,
                    longitude=longitude,
                    accuracy_meters=accuracy_meters,
                    allow_external_routing=allow_external_routing,
                ),
                created_at=now,
                expires_at=now + SESSION_TTL_SECONDS,
            )
            self._sessions[session.id] = session
            return session

    def get_session(self, session_id: str) -> CabinSession | None:
        with self._lock:
            now = time.time()
            self._prune(now)
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.expires_at = now + SESSION_TTL_SECONDS
            if session.pending_action and session.pending_action.expires_at <= now:
                session.pending_action = None
            return session

    def update_vehicle(self, session: CabinSession, vehicle: VehicleState) -> None:
        with self._lock:
            session.vehicle = vehicle
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def record_trip(self, session: CabinSession, trip: dict[str, object]) -> None:
        with self._lock:
            session.trip_history.append(trip)
            session.trip_history = session.trip_history[-10:]
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def set_preference(self, session: CabinSession, key: str, value: str) -> None:
        with self._lock:
            session.preferences[key] = value
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def forget_preference(self, session: CabinSession, key: str) -> bool:
        with self._lock:
            removed = session.preferences.pop(key, None) is not None
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session
            return removed

    def create_sunroof_confirmation(self, session: CabinSession, target_percent: int) -> None:
        with self._lock:
            session.pending_action = PendingSunroofAction(
                target_percent=target_percent,
                expires_at=time.time() + CONFIRMATION_TTL_SECONDS,
            )
            self._sessions[session.id] = session

    def take_sunroof_confirmation(self, session: CabinSession) -> PendingSunroofAction | None:
        with self._lock:
            pending = session.pending_action
            session.pending_action = None
            self._sessions[session.id] = session
            if pending is None or pending.expires_at <= time.time():
                return None
            return pending

    def clear_pending_action(self, session: CabinSession) -> None:
        with self._lock:
            session.pending_action = None
            self._sessions[session.id] = session

    def consume_rate_limit(self, key: str) -> tuple[bool, int]:
        with self._lock:
            now = time.time()
            self._prune(now)
            existing = self._rate_windows.get(key)
            if existing is None or existing.started_at + RATE_WINDOW_SECONDS <= now:
                self._rate_windows[key] = RateWindow(started_at=now, count=1)
                return True, 0
            if existing.count >= RATE_LIMIT:
                retry_after = max(
                    1,
                    int(existing.started_at + RATE_WINDOW_SECONDS - now + 0.999),
                )
                return False, retry_after
            existing.count += 1
            return True, 0

    def clear(self) -> None:
        """Reset demo state. Intended for deterministic tests only."""

        with self._lock:
            self._sessions.clear()
            self._rate_windows.clear()
