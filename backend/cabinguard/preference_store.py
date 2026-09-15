"""Consent-bound durable preference storage for the CabinGuard demo.

This is deliberately separate from the vehicle sandbox and from the anonymous
session store. A browser-created opaque profile id is not a production account;
it only lets a user inspect or erase preferences they explicitly opted to retain.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_PREFERENCE_TTL_DAYS = 90
MAX_PREFERENCE_TTL_DAYS = 365


class PreferenceStore:
    def __init__(self, path: Path | None = None) -> None:
        configured = os.getenv("CABINGUARD_PREFERENCE_DB")
        self.path = path or Path(configured or ".runtime/cabinguard-preferences.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS preference_profiles (
                    profile_id TEXT PRIMARY KEY,
                    consent_granted INTEGER NOT NULL,
                    consent_expires_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    profile_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(profile_id, preference_key)
                );
                """
            )

    @staticmethod
    def _expiry(ttl_days: int) -> float:
        bounded = min(max(ttl_days, 1), MAX_PREFERENCE_TTL_DAYS)
        return time.time() + bounded * 24 * 60 * 60

    def grant(self, profile_id: str, *, ttl_days: int = DEFAULT_PREFERENCE_TTL_DAYS) -> dict[str, object]:
        expires_at = self._expiry(ttl_days)
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO preference_profiles(profile_id, consent_granted, consent_expires_at, updated_at)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                  consent_granted = 1,
                  consent_expires_at = excluded.consent_expires_at,
                  updated_at = excluded.updated_at
                """,
                (profile_id, expires_at, now),
            )
        return {"granted": True, "expiresAt": expires_at, "ttlDays": min(max(ttl_days, 1), MAX_PREFERENCE_TTL_DAYS)}

    def revoke(self, profile_id: str, *, delete_preferences: bool = True) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO preference_profiles(profile_id, consent_granted, consent_expires_at, updated_at)
                VALUES (?, 0, 0, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                  consent_granted = 0,
                  consent_expires_at = 0,
                  updated_at = excluded.updated_at
                """,
                (profile_id, time.time()),
            )
            if delete_preferences:
                connection.execute("DELETE FROM preferences WHERE profile_id = ?", (profile_id,))

    def has_consent(self, profile_id: str | None) -> bool:
        if not profile_id:
            return False
        now = time.time()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT consent_granted, consent_expires_at FROM preference_profiles WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if row is None or not bool(row["consent_granted"]):
                return False
            if float(row["consent_expires_at"]) <= now:
                connection.execute("DELETE FROM preferences WHERE profile_id = ?", (profile_id,))
                connection.execute(
                    "UPDATE preference_profiles SET consent_granted = 0 WHERE profile_id = ?",
                    (profile_id,),
                )
                connection.commit()
                return False
            return True

    def list(self, profile_id: str | None) -> dict[str, str]:
        if not self.has_consent(profile_id) or not profile_id:
            return {}
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM preferences WHERE expires_at <= ?", (now,))
            rows = connection.execute(
                """SELECT preference_key, preference_value FROM preferences
                   WHERE profile_id = ? AND expires_at > ? ORDER BY updated_at DESC""",
                (profile_id, now),
            ).fetchall()
        return {str(row["preference_key"]): str(row["preference_value"]) for row in rows}

    def set(self, profile_id: str, key: str, value: str, *, ttl_days: int = DEFAULT_PREFERENCE_TTL_DAYS) -> bool:
        if not self.has_consent(profile_id):
            return False
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO preferences(profile_id, preference_key, preference_value, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, preference_key) DO UPDATE SET
                  preference_value = excluded.preference_value,
                  expires_at = excluded.expires_at,
                  updated_at = excluded.updated_at
                """,
                (profile_id, key, value, self._expiry(ttl_days), now),
            )
        return True

    def forget(self, profile_id: str, key: str) -> bool:
        if not self.has_consent(profile_id):
            return False
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM preferences WHERE profile_id = ? AND preference_key = ?",
                (profile_id, key),
            )
        return cursor.rowcount > 0

    def public_status(self, profile_id: str | None) -> dict[str, object]:
        consent = self.has_consent(profile_id)
        return {
            "scope": "consented_local_profile" if consent else "current_demo_session",
            "consentGranted": consent,
            "retention": (
                f"授权偏好默认保留 {DEFAULT_PREFERENCE_TTL_DAYS} 天并按条目续期。"
                if consent
                else "仅本次 30 分钟演示会话。"
            ),
            "preferences": self.list(profile_id) if consent else {},
            "deletion": "撤销授权会删除该匿名本地配置档中的全部长期偏好。",
        }
