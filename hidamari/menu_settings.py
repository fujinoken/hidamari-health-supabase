from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from hidamari.dashboard_settings import normalize_dashboard_user_id


MENU_SETTINGS_TABLE = "menu_role_settings"
MENU_SETTINGS_SCHEMA_VERSION = 1
MENU_SETTINGS_SCOPES = ("admin", "staff")


def normalize_menu_scope(value) -> str:
    scope = str(value or "").strip().lower()
    if scope not in MENU_SETTINGS_SCOPES:
        raise ValueError("menu_scope must be admin or staff")
    return scope


def menu_settings_cache_key(menu_scope) -> str:
    """管理者・職員のロール共通設定用session_stateキーを返す。"""
    return f"menu_role_settings::{normalize_menu_scope(menu_scope)}"


def get_legacy_role_rows(settings_all, menu_scope) -> list[dict]:
    """旧menu_category_settings_allからロール共通行だけを安全に取り出す。"""
    if not isinstance(settings_all, dict):
        return []
    rows = settings_all.get(normalize_menu_scope(menu_scope), [])
    return rows if isinstance(rows, list) else []


def _safe_text(value, default="", max_length=500, allow_empty=True) -> str:
    text = str(value or "").strip()
    if any(ord(char) < 32 for char in text) or len(text) > max_length:
        return default
    if not text and not allow_empty:
        return default
    return text


def _safe_visible(value, default=True) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "on", "表示", "有"}:
        return True
    if text in {"false", "0", "no", "off", "非表示", "無"}:
        return False
    return bool(default)


def _safe_sort_order(value, default=9999.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(number) or number < -1_000_000 or number > 1_000_000:
        return float(default)
    return number


def _standard_menu_rows(standard_rows: Iterable[dict]) -> list[dict]:
    result = []
    seen = set()
    for index, row in enumerate(standard_rows or []):
        if not isinstance(row, dict):
            continue
        menu_key = _safe_text(row.get("menu_key"), max_length=200, allow_empty=False)
        if not menu_key or menu_key in seen:
            continue
        seen.add(menu_key)
        result.append({
            "menu_key": menu_key,
            "visible": _safe_visible(row.get("visible"), True),
            "category": _safe_text(row.get("category"), "その他", 100, False),
            "sort_order": _safe_sort_order(row.get("sort_order"), (index + 1) * 10),
            "note": _safe_text(row.get("note"), "", 500, True),
        })
    return result


def normalize_menu_setting_rows(value, standard_rows: Iterable[dict], required_visible: Iterable[str] = ()) -> list[dict]:
    """保存値を現行メニューだけへ正規化し、新規メニューを標準値で補完する。"""
    standards = _standard_menu_rows(standard_rows)
    standard_by_key = {row["menu_key"]: row for row in standards}
    required = {str(key or "").strip() for key in required_visible}

    try:
        payload = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        payload = payload.get("rows")
    if not isinstance(payload, list):
        payload = []

    saved_by_key = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        menu_key = _safe_text(row.get("menu_key"), max_length=200, allow_empty=False)
        standard = standard_by_key.get(menu_key)
        if standard is None:
            continue
        saved_by_key[menu_key] = {
            "menu_key": menu_key,
            "visible": _safe_visible(row.get("visible"), standard["visible"]),
            "category": _safe_text(row.get("category"), standard["category"], 100, False),
            "sort_order": _safe_sort_order(row.get("sort_order"), standard["sort_order"]),
            "note": _safe_text(row.get("note"), standard["note"], 500, True),
        }

    result = []
    standard_index = {row["menu_key"]: index for index, row in enumerate(standards)}
    for standard in standards:
        row = dict(saved_by_key.get(standard["menu_key"], standard))
        if row["menu_key"] in required:
            row["visible"] = True
        result.append(row)
    return sorted(result, key=lambda row: (row["sort_order"], standard_index[row["menu_key"]]))


def encode_menu_settings(rows, standard_rows: Iterable[dict], required_visible: Iterable[str] = ()) -> str:
    payload = {
        "schema_version": MENU_SETTINGS_SCHEMA_VERSION,
        "rows": normalize_menu_setting_rows(rows, standard_rows, required_visible),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_menu_settings(value, standard_rows: Iterable[dict], required_visible: Iterable[str] = ()) -> list[dict]:
    return normalize_menu_setting_rows(value, standard_rows, required_visible)


class SQLiteMenuRoleSettingsStore:
    """Supabase障害時とローカル環境で使うロール共通SQLiteミラー。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MENU_SETTINGS_TABLE} (
                menu_scope TEXT PRIMARY KEY CHECK (menu_scope IN ('admin', 'staff')),
                settings_json TEXT NOT NULL,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return conn

    def load(self, menu_scope, standard_rows, required_visible=()) -> list[dict] | None:
        menu_scope = normalize_menu_scope(menu_scope)
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT settings_json FROM {MENU_SETTINGS_TABLE} WHERE menu_scope = ?",
                (menu_scope,),
            ).fetchone()
        if row is None:
            return None
        return decode_menu_settings(row[0], standard_rows, required_visible)

    def upsert(self, menu_scope, updated_by, rows, standard_rows, required_visible=()) -> list[dict]:
        menu_scope = normalize_menu_scope(menu_scope)
        updated_by = normalize_dashboard_user_id(updated_by)
        clean_rows = normalize_menu_setting_rows(rows, standard_rows, required_visible)
        settings_json = encode_menu_settings(clean_rows, standard_rows, required_visible)
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                f"""
                INSERT INTO {MENU_SETTINGS_TABLE}
                    (menu_scope, settings_json, updated_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(menu_scope) DO UPDATE SET
                    settings_json = excluded.settings_json,
                    updated_by = COALESCE(excluded.updated_by, updated_by),
                    updated_at = excluded.updated_at
                """,
                (menu_scope, settings_json, updated_by or None, now, now),
            )
            conn.commit()
        return clean_rows
