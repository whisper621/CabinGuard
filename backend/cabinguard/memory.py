"""Session-scoped preference and trip-memory executor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .models import ToolExecution
from .session import CabinSession, SessionStore
from .tools import EmptyInput, ManagePreferencesInput, ToolContext


def _blocked(session: CabinSession, reason: str, **extra: object) -> ToolExecution:
    return ToolExecution(
        vehicle=session.vehicle,
        status="blocked",
        output={"executed": False, "blocked": True, "reason": reason, **extra},
    )


class SessionMemoryExecutor:
    def __init__(self, store: SessionStore) -> None:
        self.store = store

    def execute(
        self,
        name: str,
        raw_input: Mapping[str, Any],
        session: CabinSession,
        context: ToolContext,
    ) -> ToolExecution:
        try:
            if name == "query_trip_history":
                EmptyInput.model_validate(dict(raw_input))
                return ToolExecution(
                    vehicle=session.vehicle,
                    status="success",
                    output={
                        "trips": list(reversed(session.trip_history)),
                        "scope": "current_demo_session",
                    },
                )

            parsed = ManagePreferencesInput.model_validate(dict(raw_input))
        except ValidationError as error:
            return _blocked(
                session,
                "记忆工具参数无效",
                code="invalid_tool_arguments",
                issues=error.errors(include_url=False),
            )

        if parsed.action == "list":
            return ToolExecution(
                vehicle=session.vehicle,
                status="success",
                output={
                    "preferences": dict(session.preferences),
                    "scope": "current_demo_session",
                },
            )

        if not context.memory_write_authorized:
            return _blocked(
                session,
                "用户没有明确要求写入或删除偏好",
                code="memory_write_not_authorized",
            )

        if not parsed.key:
            return _blocked(session, "记忆操作缺少 key", code="missing_preference_key")

        key = parsed.key.strip()
        if parsed.action == "remember":
            if not parsed.value:
                return _blocked(
                    session,
                    "记住偏好时必须提供 value",
                    code="missing_preference_value",
                )
            value = parsed.value.strip()
            self.store.set_preference(session, key, value)
            return ToolExecution(
                vehicle=session.vehicle,
                status="success",
                output={
                    "executed": True,
                    "action": "remember",
                    "key": key,
                    "value": value,
                    "scope": "current_demo_session",
                },
            )

        removed = self.store.forget_preference(session, key)
        return ToolExecution(
            vehicle=session.vehicle,
            status="success",
            output={
                "executed": True,
                "action": "forget",
                "key": key,
                "removed": removed,
                "scope": "current_demo_session",
            },
        )
