from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DASHBOARD_SETTINGS_TABLE = "dashboard_user_settings"
DASHBOARD_SETTINGS_SCHEMA_VERSION = 1


def normalize_dashboard_user_id(value) -> str:
    """既存認証のログインIDと同じ形式にそろえる。"""
    if value is None:
        return ""
    return str(value).strip().lower()[:255]


def normalize_dashboard_items(value, allowed_items: Iterable[str], default_items: Iterable[str]) -> list[str]:
    """保存値を既知項目だけの重複しない配列へ正規化する。"""
    allowed = list(allowed_items)
    allowed_set = set(allowed)
    defaults = [item for item in default_items if item in allowed_set]
    if not isinstance(value, (list, tuple, set)):
        return defaults

    result = []
    for item in value:
        if isinstance(item, str) and item in allowed_set and item not in result:
            result.append(item)
    return result


def encode_dashboard_settings(items, allowed_items: Iterable[str], default_items: Iterable[str]) -> str:
    payload = {
        "schema_version": DASHBOARD_SETTINGS_SCHEMA_VERSION,
        "enabled_items": normalize_dashboard_items(items, allowed_items, default_items),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_dashboard_settings(value, allowed_items: Iterable[str], default_items: Iterable[str]) -> list[str]:
    """JSON文字列・jsonb辞書・旧配列形式を安全に読み取る。"""
    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        payload = payload.get("enabled_items")
    return normalize_dashboard_items(payload, allowed_items, default_items)


class SQLiteDashboardSettingsStore:
    """Supabase未使用時と障害時に使う、同一スキーマのSQLite保存先。"""

    def __init__(self, db_path: str | Path, allowed_items: Iterable[str], default_items: Iterable[str]):
        self.db_path = Path(db_path)
        self.allowed_items = tuple(allowed_items)
        self.default_items = tuple(default_items)

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DASHBOARD_SETTINGS_TABLE} (
                user_id TEXT PRIMARY KEY,
                settings_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return conn

    def load(self, user_id: str) -> list[str] | None:
        user_id = normalize_dashboard_user_id(user_id)
        if not user_id:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT settings_json FROM {DASHBOARD_SETTINGS_TABLE} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return decode_dashboard_settings(row[0], self.allowed_items, self.default_items)

    def upsert(self, user_id: str, items) -> list[str]:
        user_id = normalize_dashboard_user_id(user_id)
        if not user_id:
            raise ValueError("user_id is required")
        clean_items = normalize_dashboard_items(items, self.allowed_items, self.default_items)
        settings_json = encode_dashboard_settings(clean_items, self.allowed_items, self.default_items)
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                f"""
                INSERT INTO {DASHBOARD_SETTINGS_TABLE} (user_id, settings_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, settings_json, now, now),
            )
            conn.commit()
        return clean_items

    def delete(self, user_id: str) -> None:
        user_id = normalize_dashboard_user_id(user_id)
        if not user_id:
            return
        with closing(self._connect()) as conn:
            conn.execute(f"DELETE FROM {DASHBOARD_SETTINGS_TABLE} WHERE user_id = ?", (user_id,))
            conn.commit()
