from __future__ import annotations

import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

DATA_DIR = Path("data")
DB_FILE = DATA_DIR / "hidamari_health.db"
DB_BUSY_TIMEOUT_MS = 5000
DB_WRITE_LOCK = threading.Lock()
_LAST_INTEGRITY_RESULT = {"ok": True, "messages": ["DB整合性: 未確認"]}


def configure_database(data_dir: Path | str, db_file: Path | str) -> None:
    global DATA_DIR, DB_FILE
    DATA_DIR = Path(data_dir)
    DB_FILE = Path(db_file)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_sqlite_identifier(name: str) -> str:
    name = str(name or "").strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"invalid sqlite identifier: {name}")
    return name


def apply_sqlite_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")


@contextmanager
def hidamari_db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=DB_BUSY_TIMEOUT_MS / 1000)
    try:
        apply_sqlite_pragmas(conn)
        yield conn
    finally:
        conn.close()


@contextmanager
def hidamari_write_transaction():
    with DB_WRITE_LOCK:
        with hidamari_db_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def get_hidamari_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=DB_BUSY_TIMEOUT_MS / 1000)
    apply_sqlite_pragmas(conn)
    return conn


def initialize_sqlite_engine() -> bool:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with hidamari_db_connection() as conn:
        conn.execute("select 1")
    return True


def sqlite_table_exists(table_name: str) -> bool:
    table_name = validate_sqlite_identifier(table_name)
    with hidamari_db_connection() as conn:
        cur = conn.execute("select name from sqlite_master where type='table' and name=?", (table_name,))
        return cur.fetchone() is not None


def sqlite_table_row_count(table_name: str) -> int:
    try:
        table_name = validate_sqlite_identifier(table_name)
        if not sqlite_table_exists(table_name):
            return 0
        with hidamari_db_connection() as conn:
            cur = conn.execute(f"select count(*) from {table_name}")
            return int(cur.fetchone()[0])
    except Exception:
        return 0


def normalize_df_columns(df: Optional[pd.DataFrame], columns: Iterable[str]) -> pd.DataFrame:
    columns = list(columns)
    if df is None:
        df = pd.DataFrame(columns=columns)
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    return work[columns].copy()


def prepare_sqlite_dataframe(df: Optional[pd.DataFrame], columns: Iterable[str], date_cols=None) -> pd.DataFrame:
    work = normalize_df_columns(df, columns)
    date_cols = date_cols or []
    for col in date_cols:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    return work.fillna("").astype(str)


def _ensure_table(conn: sqlite3.Connection, table_name: str, columns: Iterable[str], unique_cols=None) -> None:
    table_name = validate_sqlite_identifier(table_name)
    columns = list(columns)
    col_defs = ", ".join([f'"{c}" TEXT' for c in columns]) or '"id" TEXT'
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs});")
    # 既存テーブルに不足列があれば追加
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cur.fetchall()}
    for col in columns:
        if col not in existing:
            conn.execute(f'ALTER TABLE {table_name} ADD COLUMN "{col}" TEXT;')


def _quote_sqlite_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _health_date_candidates(value) -> list[str]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        text = str(value or "").strip()
        return [text] if text else []
    return list(dict.fromkeys([
        parsed.strftime("%Y-%m-%d"),
        parsed.strftime("%Y/%m/%d"),
        parsed.strftime("%Y年%m月%d日"),
        parsed.strftime("%Y-%m-%d 00:00:00"),
        parsed.strftime("%Y-%m-%dT00:00:00"),
    ]))


def _normalize_health_user_id(value) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _normalize_health_user_name(value) -> str:
    text = str(value or "").strip().replace("　", "")
    text = re.sub(r"\s+", "", text)
    for suffix in ("さん", "様", "殿"):
        text = text.replace(suffix, "")
    return text.lower()


def _ensure_health_record_key_schema(conn: sqlite3.Connection, table_name: str, columns: Iterable[str]) -> None:
    """健康記録の既存行を変更せず、1件UPSERT用のキー列と一意索引だけを追加する。"""
    table_name = validate_sqlite_identifier(table_name)
    _ensure_table(conn, table_name, columns)
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if "record_key" not in existing:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN "record_key" TEXT;')
    index_name = validate_sqlite_identifier(f"ux_{table_name}_record_key")
    existing_index = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    ).fetchone()
    if existing_index and " WHERE " not in str(existing_index[0] or "").upper():
        return
    duplicate = conn.execute(
        f'SELECT "record_key", COUNT(*) FROM {table_name} '
        'WHERE "record_key" IS NOT NULL AND TRIM("record_key") <> \'\' '
        'GROUP BY "record_key" HAVING COUNT(*) > 1 LIMIT 1'
    ).fetchone()
    if duplicate:
        raise sqlite3.IntegrityError(f"duplicate health record_key: {duplicate[0]}")
    if existing_index and " WHERE " in str(existing_index[0] or "").upper():
        conn.execute(f"DROP INDEX {index_name}")
    conn.execute(
        f'CREATE UNIQUE INDEX IF NOT EXISTS {index_name} '
        f'ON {table_name}("record_key");'
    )


def _find_sqlite_health_row(
    conn: sqlite3.Connection,
    table_name: str,
    record_keys,
    record_date,
    user_id,
    user_name,
):
    table_name = validate_sqlite_identifier(table_name)
    keys = [str(key).strip() for key in record_keys or [] if str(key).strip()]
    if keys:
        placeholders = ",".join("?" for _ in keys)
        rows = conn.execute(
            f'SELECT rowid, "record_key", "記録日", "user_id", "利用者名" '
            f'FROM {table_name} WHERE "record_key" IN ({placeholders})',
            keys,
        ).fetchall()
        if len(rows) > 1:
            raise sqlite3.IntegrityError("multiple health rows match record_key candidates")
        if rows:
            return rows[0]

    date_values = _health_date_candidates(record_date)
    if not date_values:
        return None
    target_id = _normalize_health_user_id(user_id)
    target_name = _normalize_health_user_name(user_name)
    date_placeholders = ",".join("?" for _ in date_values)
    normalized_name_sql = (
        'LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE('
        'TRIM(COALESCE("利用者名", \'\')), \' \', \'\'), \'　\', \'\'), '
        '\'さん\', \'\'), \'様\', \'\'), \'殿\', \'\'))'
    )
    identity_sql = '0'
    identity_params = []
    if target_id and target_name:
        identity_sql = (
            '(TRIM(CAST(COALESCE("user_id", \'\') AS TEXT)) IN (?, ?) '
            f'OR (TRIM(CAST(COALESCE("user_id", \'\') AS TEXT)) = \'\' AND {normalized_name_sql} = ?))'
        )
        identity_params = [target_id, f"{target_id}.0", target_name]
    elif target_id:
        identity_sql = 'TRIM(CAST(COALESCE("user_id", \'\') AS TEXT)) IN (?, ?)'
        identity_params = [target_id, f"{target_id}.0"]
    elif target_name:
        identity_sql = f'{normalized_name_sql} = ?'
        identity_params = [target_name]
    matches = conn.execute(
        f'SELECT rowid, "record_key", "記録日", "user_id", "利用者名" '
        f'FROM {table_name} WHERE TRIM(CAST("記録日" AS TEXT)) IN ({date_placeholders}) '
        f'AND {identity_sql}',
        date_values + identity_params,
    ).fetchall()
    if len(matches) > 1:
        raise sqlite3.IntegrityError("multiple legacy health rows match the same date and user")
    return matches[0] if matches else None


def find_sqlite_health_record_key(
    table_name: str,
    columns: Iterable[str],
    record_keys,
    record_date,
    user_id,
    user_name,
) -> Optional[str]:
    """対象行だけを照合し、旧行なら呼出側が渡した互換キーを返す。"""
    with hidamari_write_transaction() as conn:
        _ensure_health_record_key_schema(conn, table_name, columns)
        row = _find_sqlite_health_row(conn, table_name, record_keys, record_date, user_id, user_name)
        if row is None:
            return None
        existing_key = str(row[1] or "").strip()
        keys = [str(key).strip() for key in record_keys or [] if str(key).strip()]
        if existing_key:
            return existing_key
        if not keys:
            return None
        return keys[0] if _normalize_health_user_id(row[3]) else keys[-1]


def upsert_sqlite_health_record(
    record: dict,
    record_key: str,
    table_name: str,
    columns: Iterable[str],
    date_cols=None,
    legacy_record_keys=None,
) -> bool:
    """健康記録を1行だけ INSERT ... ON CONFLICT DO UPDATE で保存する。"""
    table_name = validate_sqlite_identifier(table_name)
    columns = list(columns)
    work = prepare_sqlite_dataframe(pd.DataFrame([record]), columns, date_cols=date_cols)
    if len(work) != 1 or not str(record_key or "").strip():
        raise ValueError("one health record and record_key are required")
    values = work.iloc[0].to_dict()
    resolved_key = str(record_key).strip()
    candidates = list(dict.fromkeys([resolved_key] + list(legacy_record_keys or [])))

    with hidamari_write_transaction() as conn:
        _ensure_health_record_key_schema(conn, table_name, columns)
        existing = _find_sqlite_health_row(
            conn,
            table_name,
            candidates,
            values.get("記録日", ""),
            values.get("user_id", ""),
            values.get("利用者名", ""),
        )
        if existing is not None and not str(existing[1] or "").strip():
            conn.execute(
                f'UPDATE {table_name} SET "record_key"=? WHERE rowid=? AND ("record_key" IS NULL OR TRIM("record_key")=\'\')',
                (resolved_key, existing[0]),
            )

        insert_columns = ["record_key"] + columns
        quoted_columns = ", ".join(_quote_sqlite_identifier(col) for col in insert_columns)
        placeholders = ", ".join("?" for _ in insert_columns)
        updates = ", ".join(
            f'{_quote_sqlite_identifier(col)}=excluded.{_quote_sqlite_identifier(col)}' for col in columns
        )
        conn.execute(
            f'INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders}) '
            f'ON CONFLICT("record_key") DO UPDATE SET {updates}',
            [resolved_key] + [values.get(col, "") for col in columns],
        )
    return True


def db_write_dataframe(df: pd.DataFrame, table_name: str, columns: Iterable[str], unique_cols=None, sort_cols=None) -> None:
    save_sqlite_table(df, table_name, columns, unique_cols=unique_cols, sort_cols=sort_cols)


def db_read_dataframe(table_name: str, columns: Iterable[str], date_cols=None) -> pd.DataFrame:
    return load_sqlite_table(table_name, columns, date_cols=date_cols)


def save_sqlite_table(df: Optional[pd.DataFrame], table_name: str, columns: Iterable[str], date_cols=None, unique_cols=None, sort_cols=None) -> None:
    table_name = validate_sqlite_identifier(table_name)
    columns = list(columns)
    work = prepare_sqlite_dataframe(df, columns, date_cols=date_cols)
    if sort_cols:
        available = [c for c in sort_cols if c in work.columns]
        if available:
            work = work.sort_values(available)
    if unique_cols:
        available = [c for c in unique_cols if c in work.columns]
        if available and not work.empty:
            work = work.drop_duplicates(subset=available, keep="last")
    with hidamari_write_transaction() as conn:
        _ensure_table(conn, table_name, columns, unique_cols=unique_cols)
        conn.execute(f"DELETE FROM {table_name};")
        if not work.empty:
            work.to_sql(table_name, conn, if_exists="append", index=False)


def load_sqlite_table(table_name: str, columns: Iterable[str], date_cols=None) -> pd.DataFrame:
    table_name = validate_sqlite_identifier(table_name)
    columns = list(columns)
    try:
        with hidamari_db_connection() as conn:
            if not sqlite_table_exists(table_name):
                _ensure_table(conn, table_name, columns)
                return pd.DataFrame(columns=columns)
            _ensure_table(conn, table_name, columns)
            select_cols = ", ".join([f'"{str(c).replace(chr(34), chr(34) + chr(34))}"' for c in columns]) or "*"
            df = pd.read_sql_query(f"SELECT {select_cols} FROM {table_name}", conn)
    except Exception:
        df = pd.DataFrame(columns=columns)
    df = normalize_df_columns(df, columns)
    if date_cols:
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def run_db_integrity_check(auto_repair: bool = True) -> dict:
    global _LAST_INTEGRITY_RESULT
    messages = []
    ok = True
    try:
        with hidamari_db_connection() as conn:
            result = conn.execute("PRAGMA quick_check;").fetchone()[0]
            messages.append(f"quick_check: {result}")
            ok = (str(result).lower() == "ok")
            if auto_repair:
                conn.execute("PRAGMA wal_checkpoint(FULL);")
                messages.append("wal_checkpoint: done")
    except Exception as e:
        ok = False
        messages.append(str(e))
    _LAST_INTEGRITY_RESULT = {"ok": ok, "messages": messages}
    return _LAST_INTEGRITY_RESULT


def get_last_integrity_result() -> dict:
    return dict(_LAST_INTEGRITY_RESULT)


def get_db_integrity_status_text() -> str:
    status = "OK" if _LAST_INTEGRITY_RESULT.get("ok", True) else "注意"
    return "DB整合性: " + status + " / " + " / ".join(_LAST_INTEGRITY_RESULT.get("messages", []))
