"""Consent-aware preference and trip-memory executor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .models import ToolExecution
from .preference_store import DEFAULT_PREFERENCE_TTL_DAYS, PreferenceStore
from .session import CabinSession, SessionStore
from .tools import EmptyInput, ManagePreferencesInput, ToolContext


def _blocked(session: CabinSession, reason: str, **extra: object) -> ToolExecution:
    return ToolExecution(
        vehicle=session.vehicle,
        status="blocked",
        output={"executed": False, "blocked": True, "reason": reason, **extra},
    )


class SessionMemoryExecutor:
    def __init__(self, store: SessionStore, preferences: PreferenceStore | None = None) -> None:
        self.store = store
        self.preferences = preferences or PreferenceStore()

    def _scope(self, session: CabinSession) -> str:
        if session.memory_consent and self.preferences.has_consent(session.memory_profile_id):
            return "consented_local_profile"
        return "current_demo_session"

    def _list_preferences(self, session: CabinSession) -> dict[str, str]:
        if self._scope(session) == "consented_local_profile":
            return self.preferences.list(session.memory_profile_id)
        return dict(session.preferences)

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
                    "preferences": self._list_preferences(session),
                    "scope": self._scope(session),
                    "retention": f"长期偏好仅在明确授权后保留，默认 {DEFAULT_PREFERENCE_TTL_DAYS} 天，可随时删除。",
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
            if self._scope(session) == "consented_local_profile":
                self.preferences.set(str(session.memory_profile_id), key, value)
            else:
                self.store.set_preference(session, key, value)
            return ToolExecution(
                vehicle=session.vehicle,
                status="success",
                output={
                    "executed": True,
                    "action": "remember",
                    "key": key,
                    "value": value,
                    "scope": self._scope(session),
                    "retention": "可在偏好设置中查看、撤销或删除。",
                },
            )

        removed = (
            self.preferences.forget(str(session.memory_profile_id), key)
            if self._scope(session) == "consented_local_profile"
            else self.store.forget_preference(session, key)
        )
        return ToolExecution(
            vehicle=session.vehicle,
            status="success",
            output={
                "executed": True,
                "action": "forget",
                "key": key,
                "removed": removed,
                "scope": self._scope(session),
            },
        )
