from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from .models import Scenario, VehicleState
from .policy_kernel import OccupantRole

SESSION_TTL_SECONDS = 30 * 60
CONFIRMATION_TTL_SECONDS = 2 * 60
RATE_WINDOW_SECONDS = 5 * 60
RATE_LIMIT = 30
MAX_SESSIONS = 300
MAX_OPERATIONS_PER_SESSION = 50

OperationStatus = Literal[
    "running",
    "awaiting_confirmation",
    "success",
    "blocked",
    "cancelled",
    "timed_out",
    "conflict",
    "failed",
]


@dataclass
class PendingSunroofAction:
    target_percent: int
    expires_at: float
    operation_id: str | None = None


@dataclass
class PendingDoorAction:
    door: str
    action: str
    expires_at: float
    operation_id: str | None = None


@dataclass
class OperationRecord:
    """Request-level write boundary used for replay, conflict and recovery evidence."""

    id: str
    idempotency_key: str
    expected_state_version: int | None
    state_version_before: int
    started_at: float
    deadline_at: float
    status: OperationStatus = "running"
    response: dict[str, Any] | None = None
    finished_at: float | None = None

    def public_dict(self, *, replayed: bool = False) -> dict[str, object]:
        return {
            "id": self.id,
            "idempotencyKey": self.idempotency_key,
            "status": self.status,
            "stateVersionBefore": self.state_version_before,
            "expectedStateVersion": self.expected_state_version,
            "replayed": replayed,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
        }


@dataclass
class CabinSession:
    id: str
    scenario: Scenario
    vehicle: VehicleState
    created_at: float
    expires_at: float
    pending_action: PendingSunroofAction | PendingDoorAction | None = None
    place_candidates: dict[str, dict[str, object]] = field(default_factory=dict)
    preferences: dict[str, str] = field(default_factory=dict)
    trip_history: list[dict[str, object]] = field(default_factory=list)
    occupant_role: OccupantRole = "driver"
    state_version: int = 1
    active_plan_id: str | None = None
    memory_profile_id: str | None = None
    memory_consent: bool = False
    operations: dict[str, OperationRecord] = field(default_factory=dict)
    active_operation_id: str | None = None


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
    if scenario == "highway":
        return vehicle.model_copy(update={"speed": 110, "gear": "D", "battery": 58, "range": 328})
    if scenario == "low_battery":
        return vehicle.model_copy(update={"speed": 35, "gear": "D", "battery": 12, "range": 48})
    if scenario == "child":
        return vehicle.model_copy(update={"speed": 0, "gear": "P", "child_lock": True})
    if scenario == "pickup":
        return vehicle.model_copy(update={"speed": 0, "gear": "P"})
    if scenario == "rest":
        return vehicle.model_copy(
            update={
                "speed": 0,
                "gear": "P",
                "target_temperature": 22,
                "ambient_light": vehicle.ambient_light.model_copy(
                    update={"enabled": True, "color": "violet", "brightness": 35}
                ),
            }
        )
    if scenario == "air_quality":
        return vehicle.model_copy(
            update={
                "speed": 20,
                "gear": "D",
                "weather": "轻度污染",
                "air_quality": vehicle.air_quality.model_copy(update={"pm25": 168}),
            }
        )
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
        occupant_role: OccupantRole = "driver",
        memory_profile_id: str | None = None,
        memory_consent: bool = False,
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
                occupant_role=occupant_role,
                memory_profile_id=memory_profile_id,
                memory_consent=memory_consent and bool(memory_profile_id),
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
            if session.vehicle != vehicle:
                session.state_version += 1
            session.vehicle = vehicle
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def set_active_plan(self, session: CabinSession, plan_id: str) -> None:
        with self._lock:
            session.active_plan_id = plan_id
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

    def create_sunroof_confirmation(
        self, session: CabinSession, target_percent: int, operation_id: str | None = None
    ) -> None:
        with self._lock:
            session.pending_action = PendingSunroofAction(
                target_percent=target_percent,
                expires_at=time.time() + CONFIRMATION_TTL_SECONDS,
                operation_id=operation_id,
            )
            self._sessions[session.id] = session

    def take_sunroof_confirmation(self, session: CabinSession) -> PendingSunroofAction | None:
        with self._lock:
            pending = session.pending_action
            if pending is not None and not isinstance(pending, PendingSunroofAction):
                return None
            session.pending_action = None
            self._sessions[session.id] = session
            if pending is None or pending.expires_at <= time.time():
                return None
            return pending

    def create_door_confirmation(
        self, session: CabinSession, door: str, action: str, operation_id: str | None = None
    ) -> None:
        with self._lock:
            session.pending_action = PendingDoorAction(
                door=door,
                action=action,
                expires_at=time.time() + CONFIRMATION_TTL_SECONDS,
                operation_id=operation_id,
            )
            self._sessions[session.id] = session

    def take_door_confirmation(self, session: CabinSession) -> PendingDoorAction | None:
        with self._lock:
            pending = session.pending_action
            if pending is not None and not isinstance(pending, PendingDoorAction):
                return None
            session.pending_action = None
            self._sessions[session.id] = session
            if pending is None or pending.expires_at <= time.time():
                return None
            return pending

    def clear_pending_action(self, session: CabinSession) -> None:
        with self._lock:
            session.pending_action = None
            self._sessions[session.id] = session

    def set_memory_consent(self, session: CabinSession, granted: bool) -> None:
        with self._lock:
            session.memory_consent = granted and bool(session.memory_profile_id)
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def begin_operation(
        self,
        session: CabinSession,
        *,
        idempotency_key: str,
        expected_state_version: int | None,
        timeout_seconds: float,
    ) -> tuple[OperationRecord, Literal["started", "replayed", "conflict"]]:
        """Open a request operation without allowing a stale client to overwrite state."""

        with self._lock:
            existing = session.operations.get(idempotency_key)
            if existing is not None:
                session.expires_at = time.time() + SESSION_TTL_SECONDS
                self._sessions[session.id] = session
                return existing, "replayed"
            active = next(
                (
                    item
                    for item in session.operations.values()
                    if item.id == session.active_operation_id and item.status == "running"
                ),
                None,
            )
            if active is not None:
                now = time.time()
                return (
                    OperationRecord(
                        id=str(uuid4()),
                        idempotency_key=idempotency_key,
                        expected_state_version=expected_state_version,
                        state_version_before=session.state_version,
                        started_at=now,
                        deadline_at=now,
                        status="conflict",
                        finished_at=now,
                    ),
                    "conflict",
                )
            if expected_state_version is not None and expected_state_version != session.state_version:
                record = OperationRecord(
                    id=str(uuid4()),
                    idempotency_key=idempotency_key,
                    expected_state_version=expected_state_version,
                    state_version_before=session.state_version,
                    started_at=time.time(),
                    deadline_at=time.time(),
                    status="conflict",
                    finished_at=time.time(),
                )
                return record, "conflict"
            now = time.time()
            record = OperationRecord(
                id=str(uuid4()),
                idempotency_key=idempotency_key,
                expected_state_version=expected_state_version,
                state_version_before=session.state_version,
                started_at=now,
                deadline_at=now + timeout_seconds,
            )
            session.operations[idempotency_key] = record
            session.operations = dict(list(session.operations.items())[-MAX_OPERATIONS_PER_SESSION:])
            session.active_operation_id = record.id
            session.expires_at = now + SESSION_TTL_SECONDS
            self._sessions[session.id] = session
            return record, "started"

    def complete_operation(
        self,
        session: CabinSession,
        operation: OperationRecord,
        *,
        status: OperationStatus,
        response: dict[str, Any],
    ) -> None:
        with self._lock:
            operation.status = status
            operation.response = dict(response)
            operation.finished_at = time.time()
            session.operations[operation.idempotency_key] = operation
            if session.active_operation_id == operation.id:
                session.active_operation_id = None
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            self._sessions[session.id] = session

    def mark_operation_awaiting_confirmation(
        self, session: CabinSession, operation_id: str | None
    ) -> None:
        if operation_id is None:
            return
        with self._lock:
            operation = next((item for item in session.operations.values() if item.id == operation_id), None)
            if operation is None:
                return
            operation.status = "awaiting_confirmation"
            operation.finished_at = time.time()
            if session.active_operation_id == operation_id:
                session.active_operation_id = None
            self._sessions[session.id] = session

    def cancel_active_operation(self, session: CabinSession) -> OperationRecord | None:
        with self._lock:
            if session.active_operation_id is None:
                return None
            operation = next(
                (item for item in session.operations.values() if item.id == session.active_operation_id),
                None,
            )
            if operation is None:
                return None
            operation.status = "cancelled"
            operation.finished_at = time.time()
            session.active_operation_id = None
            self._sessions[session.id] = session
            return operation

    def cancel_operation(
        self, session: CabinSession, *, idempotency_key: str | None = None
    ) -> OperationRecord | None:
        """Mark the active or named operation cancelled; the runner checks before each tool."""

        with self._lock:
            operation = (
                session.operations.get(idempotency_key)
                if idempotency_key is not None
                else next(
                    (
                        item
                        for item in session.operations.values()
                        if item.id == session.active_operation_id
                    ),
                    None,
                )
            )
            if operation is None or operation.status != "running":
                return None
            operation.status = "cancelled"
            operation.finished_at = time.time()
            if session.active_operation_id == operation.id:
                session.active_operation_id = None
            self._sessions[session.id] = session
            return operation

    def operation_cancelled(self, session: CabinSession, operation_id: str | None) -> bool:
        if operation_id is None:
            return False
        with self._lock:
            return any(
                item.id == operation_id and item.status == "cancelled"
                for item in session.operations.values()
            )

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
