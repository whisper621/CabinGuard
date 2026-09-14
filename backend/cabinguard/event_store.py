"""Append-only SQLite evidence ledger for plans, policy decisions and receipts."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class EventStore:
    def __init__(self, path: str | Path = ".runtime/evidence.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    plan_id TEXT,
                    task_id TEXT,
                    event_type TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def append(
        self,
        *,
        session_id: str,
        event_type: str,
        state_version: int,
        payload: dict[str, Any],
        plan_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": f"evt-{uuid4().hex[:16]}",
            "sessionId": session_id,
            "planId": plan_id,
            "taskId": task_id,
            "eventType": event_type,
            "stateVersion": state_version,
            "payload": payload,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO evidence_events
                (id, session_id, plan_id, task_id, event_type, state_version, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    session_id,
                    plan_id,
                    task_id,
                    event_type,
                    state_version,
                    json.dumps(payload, ensure_ascii=False),
                    event["createdAt"],
                ),
            )
        return event

    def list_events(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM evidence_events WHERE session_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "sessionId": row["session_id"],
                "planId": row["plan_id"],
                "taskId": row["task_id"],
                "eventType": row["event_type"],
                "stateVersion": row["state_version"],
                "payload": json.loads(row["payload_json"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM evidence_events")
