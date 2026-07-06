import os
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import streamlit as st

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:
    psycopg2 = None
    RealDictCursor = None

try:
    import requests
except Exception:
    requests = None

from hidamari.auth.login_state import INITIAL_ACCOUNT_PASSWORD, INITIAL_LOGIN_IDS, LOGIN_FAILURE_LIMIT, LOGIN_LOCK_SECONDS
from hidamari.auth.password import hash_password, password_hash_needs_upgrade, verify_password
from hidamari.config.columns import ACCOUNT_COLUMNS
from hidamari.core.text_utils import clean_text
from hidamari.core.time_utils import format_now_jst, now_jst_dt


APP_USER_TABLE = "app_users"

AUTH_CONFIG_MESSAGE = (
    "認証用DB接続情報が未設定です。管理者は Streamlit Cloud の Secrets に "
    "DATABASE_URL または [supabase].service_role_key を設定してください。"
)
AUTH_CONNECT_MESSAGE = "認証用DB接続情報が未設定または接続できません。管理者に確認してください。"
AUTH_TABLE_MESSAGE = (
    "認証用テーブル app_users が未作成です。管理者は Supabase SQL Editor で "
    "sql/app_users_auth.sql を実行してください。"
)
INVALID_LOGIN_MESSAGE = "IDまたはパスワードが違います。"


class AuthBackendError(Exception):
    public_message = AUTH_CONNECT_MESSAGE


class AuthConfigError(AuthBackendError):
    public_message = AUTH_CONFIG_MESSAGE


class AuthTableMissingError(AuthBackendError):
    public_message = AUTH_TABLE_MESSAGE


class AuthConnectionError(AuthBackendError):
    public_message = AUTH_CONNECT_MESSAGE


def auth_public_message(exc):
    return getattr(exc, "public_message", AUTH_CONNECT_MESSAGE)


def _log_auth_exception(message, exc=None):
    logger = logging.getLogger(__name__)
    if exc is None:
        logger.error(message)
    else:
        logger.exception(message)


def _looks_like_missing_table(exc_or_response):
    text = ""
    try:
        text = getattr(exc_or_response, "text", "") or str(exc_or_response)
    except Exception:
        text = ""
    text = text.lower()
    return (
        "app_users" in text
        and (
            "does not exist" in text
            or "undefinedtable" in text
            or "relation" in text
            or "42p01" in text
            or "pgrst205" in text
            or "not found" in text
        )
    )

COL_LOGIN_ID = ACCOUNT_COLUMNS[0]
COL_DISPLAY_NAME = ACCOUNT_COLUMNS[1]
COL_PASSWORD_HASH = ACCOUNT_COLUMNS[2]
COL_ROLE = ACCOUNT_COLUMNS[3]
COL_STATUS = ACCOUNT_COLUMNS[4]
COL_MEMO = ACCOUNT_COLUMNS[5]
COL_CREATED_AT = ACCOUNT_COLUMNS[6]
COL_UPDATED_AT = ACCOUNT_COLUMNS[7]
COL_MUST_CHANGE = ACCOUNT_COLUMNS[8]
COL_PASSWORD_CHANGED_AT = ACCOUNT_COLUMNS[9]

ACTIVE_STATUS = "譛牙柑"
INACTIVE_STATUS = "辟｡蜉ｹ"
YES_VALUE = "縺ｯ縺・"
NO_VALUE = "縺・＞縺・"


def _secret_get(container, key, default=""):
    try:
        if container is None:
            return default
        if hasattr(container, "get"):
            return container.get(key, default)
        return container[key] if key in container else default
    except Exception:
        return default


def _database_url():
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}

    for key in ("DATABASE_URL", "SUPABASE_DB_URL", "POSTGRES_URL"):
        value = _secret_get(secrets, key, "")
        if value:
            return str(value)
    postgres = _secret_get(secrets, "postgres", {})
    for key in ("url", "database_url", "connection_string"):
        value = _secret_get(postgres, key, "")
        if value:
            return str(value)
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or os.environ.get("POSTGRES_URL") or ""


def _supabase_config():
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}
    section = _secret_get(secrets, "supabase", {})
    url = _secret_get(section, "url", "") or _secret_get(secrets, "SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    key = (
        _secret_get(section, "service_role_key", "")
        or _secret_get(section, "service_key", "")
        or _secret_get(secrets, "SUPABASE_SERVICE_ROLE_KEY", "")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )
    if not url or not key:
        return None
    return {"url": str(url).rstrip("/"), "key": str(key)}


def _pg_conn():
    url = _database_url()
    if not url or psycopg2 is None:
        return None
    try:
        if "sslmode=" in url:
            return psycopg2.connect(url, cursor_factory=RealDictCursor)
        return psycopg2.connect(url, sslmode=os.environ.get("PGSSLMODE", "require"), cursor_factory=RealDictCursor)
    except Exception as exc:
        _log_auth_exception("Failed to connect to authentication database.", exc)
        raise AuthConnectionError() from exc


def _has_direct_db():
    return bool(_database_url() and psycopg2 is not None)


def _rest_headers(prefer="return=representation"):
    cfg = _supabase_config()
    if not cfg:
        raise AuthConfigError()
    return {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _rest_endpoint(query=""):
    cfg = _supabase_config()
    if not cfg:
        raise AuthConfigError()
    return f"{cfg['url']}/rest/v1/{APP_USER_TABLE}{query}"


def _require_auth_backend():
    if _has_direct_db():
        return "postgres"
    if requests is not None and _supabase_config():
        return "rest"
    raise AuthConfigError()


def ensure_app_users_table():
    backend = _require_auth_backend()
    if backend == "postgres":
        conn = _pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT 1 FROM public.{APP_USER_TABLE} LIMIT 1")
        except AuthBackendError:
            raise
        except Exception as exc:
            conn.rollback()
            _log_auth_exception("Failed to prepare authentication table.", exc)
            if _looks_like_missing_table(exc):
                raise AuthTableMissingError() from exc
            raise AuthConnectionError() from exc
        finally:
            cur.close()
            conn.close()

    if not load_accounts_raw():
        now = now_jst_dt()
        for login_id, role, label in (("kanri", "admin", "管理者"), ("staff", "staff", "職員")):
            upsert_app_user(
                {
                    "login_id": login_id,
                    "display_name": label,
                    "password_hash": hash_password(INITIAL_ACCOUNT_PASSWORD),
                    "role": role,
                    "must_change_password": True,
                    "failed_login_count": 0,
                    "locked_until": None,
                    "last_login_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )


def _to_iso(value):
    if value in ("", None):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_row(row):
    row = dict(row or {})
    row["login_id"] = clean_text(row.get("login_id")).lower()
    row["display_name"] = clean_text(row.get("display_name"), row["login_id"])
    row["role"] = clean_text(row.get("role"), "staff")
    row["password_hash"] = clean_text(row.get("password_hash"))
    row["must_change_password"] = bool(row.get("must_change_password"))
    row["failed_login_count"] = int(row.get("failed_login_count") or 0)
    return row


def load_accounts_raw():
    backend = _require_auth_backend()
    if backend == "postgres":
        conn = _pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                SELECT id, login_id, display_name, password_hash, role, must_change_password,
                       failed_login_count, locked_until, last_login_at, created_at, updated_at
                FROM public.{APP_USER_TABLE}
                ORDER BY login_id
                """
            )
            return [_normalize_row(row) for row in cur.fetchall()]
        except AuthBackendError:
            raise
        except Exception as exc:
            _log_auth_exception("Failed to read authentication users.", exc)
            if _looks_like_missing_table(exc):
                raise AuthTableMissingError() from exc
            raise AuthConnectionError() from exc
        finally:
            cur.close()
            conn.close()

    try:
        res = requests.get(_rest_endpoint("?select=*&order=login_id.asc"), headers=_rest_headers(prefer=""), timeout=20)
    except AuthBackendError:
        raise
    except Exception as exc:
        _log_auth_exception("Failed to read authentication users through Supabase REST.", exc)
        raise AuthConnectionError() from exc
    if res.status_code >= 400:
        _log_auth_exception(f"Supabase REST returned {res.status_code} while reading app_users.")
        if _looks_like_missing_table(res):
            raise AuthTableMissingError()
        raise AuthConnectionError()
    return [_normalize_row(row) for row in (res.json() or [])]


def get_app_user(login_id):
    ensure_app_users_table()
    login_id = clean_text(login_id).lower()
    if not login_id:
        return None
    backend = _require_auth_backend()
    if backend == "postgres":
        conn = _pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                SELECT id, login_id, display_name, password_hash, role, must_change_password,
                       failed_login_count, locked_until, last_login_at, created_at, updated_at
                FROM public.{APP_USER_TABLE}
                WHERE login_id = %s
                LIMIT 1
                """,
                (login_id,),
            )
            row = cur.fetchone()
            return _normalize_row(row) if row else None
        except AuthBackendError:
            raise
        except Exception as exc:
            _log_auth_exception("Failed to read authentication user.", exc)
            if _looks_like_missing_table(exc):
                raise AuthTableMissingError() from exc
            raise AuthConnectionError() from exc
        finally:
            cur.close()
            conn.close()

    try:
        res = requests.get(
            _rest_endpoint(f"?login_id=eq.{quote(login_id, safe='')}&select=*&limit=1"),
            headers=_rest_headers(prefer=""),
            timeout=20,
        )
    except AuthBackendError:
        raise
    except Exception as exc:
        _log_auth_exception("Failed to read authentication user through Supabase REST.", exc)
        raise AuthConnectionError() from exc
    if res.status_code >= 400:
        _log_auth_exception(f"Supabase REST returned {res.status_code} while reading app_user.")
        if _looks_like_missing_table(res):
            raise AuthTableMissingError()
        raise AuthConnectionError()
    rows = res.json() if res.status_code < 400 else []
    return _normalize_row(rows[0]) if rows else None


def upsert_app_user(row):
    backend = _require_auth_backend()
    payload = {
        "login_id": clean_text(row.get("login_id")).lower(),
        "display_name": clean_text(row.get("display_name"), clean_text(row.get("login_id")).lower()),
        "password_hash": clean_text(row.get("password_hash")),
        "role": clean_text(row.get("role"), "staff"),
        "must_change_password": bool(row.get("must_change_password")),
        "failed_login_count": int(row.get("failed_login_count") or 0),
        "locked_until": _to_iso(row.get("locked_until")),
        "last_login_at": _to_iso(row.get("last_login_at")),
        "updated_at": _to_iso(row.get("updated_at") or now_jst_dt()),
    }
    if row.get("created_at"):
        payload["created_at"] = _to_iso(row.get("created_at"))

    if backend == "postgres":
        conn = _pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                INSERT INTO public.{APP_USER_TABLE}
                    (login_id, display_name, password_hash, role, must_change_password,
                     failed_login_count, locked_until, last_login_at, created_at, updated_at)
                VALUES
                    (%(login_id)s, %(display_name)s, %(password_hash)s, %(role)s, %(must_change_password)s,
                     %(failed_login_count)s, %(locked_until)s, %(last_login_at)s,
                     COALESCE(%(created_at)s::timestamptz, now()), %(updated_at)s)
                ON CONFLICT (login_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    must_change_password = EXCLUDED.must_change_password,
                    failed_login_count = EXCLUDED.failed_login_count,
                    locked_until = EXCLUDED.locked_until,
                    last_login_at = EXCLUDED.last_login_at,
                    updated_at = EXCLUDED.updated_at
                """,
                {**payload, "created_at": payload.get("created_at")},
            )
            conn.commit()
        except AuthBackendError:
            raise
        except Exception as exc:
            conn.rollback()
            _log_auth_exception("Failed to save authentication user.", exc)
            if _looks_like_missing_table(exc):
                raise AuthTableMissingError() from exc
            raise AuthConnectionError() from exc
        finally:
            cur.close()
            conn.close()
        return True

    try:
        res = requests.post(
            _rest_endpoint("?on_conflict=login_id"),
            headers=_rest_headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=[payload],
            timeout=20,
        )
    except AuthBackendError:
        raise
    except Exception as exc:
        _log_auth_exception("Failed to save authentication user through Supabase REST.", exc)
        raise AuthConnectionError() from exc
    if res.status_code >= 400:
        _log_auth_exception(f"Supabase REST returned {res.status_code} while saving app_user.")
        if _looks_like_missing_table(res):
            raise AuthTableMissingError()
        raise AuthConnectionError()
    return True


def delete_app_user(login_id):
    login_id = clean_text(login_id).lower()
    if not login_id or login_id == "kanri":
        return False
    backend = _require_auth_backend()
    if backend == "postgres":
        conn = _pg_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"DELETE FROM public.{APP_USER_TABLE} WHERE login_id = %s", (login_id,))
            conn.commit()
            return cur.rowcount > 0
        except AuthBackendError:
            raise
        except Exception as exc:
            conn.rollback()
            _log_auth_exception("Failed to delete authentication user.", exc)
            if _looks_like_missing_table(exc):
                raise AuthTableMissingError() from exc
            raise AuthConnectionError() from exc
        finally:
            cur.close()
            conn.close()
    try:
        res = requests.delete(
            _rest_endpoint(f"?login_id=eq.{quote(login_id, safe='')}"),
            headers=_rest_headers(prefer="return=minimal"),
            timeout=20,
        )
    except AuthBackendError:
        raise
    except Exception as exc:
        _log_auth_exception("Failed to delete authentication user through Supabase REST.", exc)
        raise AuthConnectionError() from exc
    if res.status_code >= 400:
        _log_auth_exception(f"Supabase REST returned {res.status_code} while deleting app_user.")
        if _looks_like_missing_table(res):
            raise AuthTableMissingError()
        raise AuthConnectionError()
    return True


def _legacy_account_row(row):
    now_text = format_now_jst("%Y-%m-%d %H:%M:%S")
    created_at = _parse_dt(row.get("created_at"))
    updated_at = _parse_dt(row.get("updated_at"))
    last_login_at = _parse_dt(row.get("last_login_at"))
    return {
        COL_LOGIN_ID: row.get("login_id", ""),
        COL_DISPLAY_NAME: row.get("display_name", row.get("login_id", "")),
        COL_PASSWORD_HASH: row.get("password_hash", ""),
        COL_ROLE: row.get("role", "staff"),
        COL_STATUS: ACTIVE_STATUS,
        COL_MEMO: "",
        COL_CREATED_AT: created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else now_text,
        COL_UPDATED_AT: updated_at.strftime("%Y-%m-%d %H:%M:%S") if updated_at else now_text,
        COL_MUST_CHANGE: YES_VALUE if row.get("must_change_password") else NO_VALUE,
        COL_PASSWORD_CHANGED_AT: "" if row.get("must_change_password") else (last_login_at.strftime("%Y-%m-%d %H:%M:%S") if last_login_at else ""),
    }


def load_accounts():
    ensure_app_users_table()
    return pd.DataFrame([_legacy_account_row(row) for row in load_accounts_raw()], columns=ACCOUNT_COLUMNS)


def _row_from_legacy(record):
    login_id = clean_text(record.get(COL_LOGIN_ID)).lower()
    status = clean_text(record.get(COL_STATUS), ACTIVE_STATUS)
    return {
        "login_id": login_id,
        "display_name": clean_text(record.get(COL_DISPLAY_NAME), login_id),
        "password_hash": clean_text(record.get(COL_PASSWORD_HASH)),
        "role": clean_text(record.get(COL_ROLE), "staff"),
        "must_change_password": clean_text(record.get(COL_MUST_CHANGE)) in {YES_VALUE, "true", "True", "1", "yes"},
        "failed_login_count": 0,
        "locked_until": None,
        "last_login_at": None,
        "created_at": _parse_dt(record.get(COL_CREATED_AT)) or now_jst_dt(),
        "updated_at": now_jst_dt(),
        "active": status != INACTIVE_STATUS,
    }


def save_accounts(df):
    ensure_app_users_table()
    work = df.copy() if df is not None else pd.DataFrame(columns=ACCOUNT_COLUMNS)
    for col in ACCOUNT_COLUMNS:
        if col not in work.columns:
            work[col] = ""
    seen = set()
    for _, record in work[ACCOUNT_COLUMNS].iterrows():
        row = _row_from_legacy(record)
        if not row["login_id"] or not row["active"]:
            if row["login_id"] != "kanri":
                delete_app_user(row["login_id"])
            continue
        seen.add(row["login_id"])
        upsert_app_user(row)

    for row in load_accounts_raw():
        login_id = row.get("login_id", "")
        if login_id and login_id not in seen and login_id != "kanri":
            delete_app_user(login_id)
    return True


def update_account_password(login_id, new_password, force_change=NO_VALUE):
    ensure_app_users_table()
    login_id = clean_text(login_id).lower()
    user = get_app_user(login_id)
    if not user:
        return False, "アカウントが見つかりません。"
    must_change = force_change in (True, YES_VALUE, "1", "true", "True")
    user["password_hash"] = hash_password(new_password)
    user["must_change_password"] = bool(must_change)
    user["failed_login_count"] = 0
    user["locked_until"] = None
    user["updated_at"] = now_jst_dt()
    upsert_app_user(user)
    return True, "パスワードを更新しました。"


def is_login_temporarily_locked(login_id):
    user = get_app_user(login_id)
    if not user:
        return False, 0
    locked_until = _parse_dt(user.get("locked_until"))
    if not locked_until:
        return False, 0
    now = now_jst_dt()
    if locked_until.tzinfo is None and now.tzinfo is not None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if now >= locked_until:
        user["failed_login_count"] = 0
        user["locked_until"] = None
        user["updated_at"] = now
        upsert_app_user(user)
        return False, 0
    return True, max(int((locked_until - now).total_seconds()), 1)


def record_login_failure(login_id):
    user = get_app_user(login_id)
    if not user:
        return 1, LOGIN_FAILURE_LIMIT - 1, 0
    count = int(user.get("failed_login_count") or 0) + 1
    locked_seconds = LOGIN_LOCK_SECONDS if count >= LOGIN_FAILURE_LIMIT else 0
    user["failed_login_count"] = count
    user["locked_until"] = now_jst_dt().timestamp() + LOGIN_LOCK_SECONDS if locked_seconds else None
    if user["locked_until"]:
        user["locked_until"] = datetime.fromtimestamp(user["locked_until"], tz=now_jst_dt().tzinfo)
    user["updated_at"] = now_jst_dt()
    upsert_app_user(user)
    return count, max(LOGIN_FAILURE_LIMIT - count, 0), locked_seconds


def clear_login_failures(login_id):
    user = get_app_user(login_id)
    if not user:
        return
    user["failed_login_count"] = 0
    user["locked_until"] = None
    user["last_login_at"] = now_jst_dt()
    user["updated_at"] = now_jst_dt()
    upsert_app_user(user)


def upgrade_account_password_hash(login_id, password):
    user = get_app_user(login_id)
    if user and password_hash_needs_upgrade(user.get("password_hash", "")):
        user["password_hash"] = hash_password(password)
        user["updated_at"] = now_jst_dt()
        upsert_app_user(user)


def authenticate_user(login_id, password):
    ensure_app_users_table()
    login_id = clean_text(login_id).lower()
    password = clean_text(password)
    user = get_app_user(login_id)
    if not user:
        return None, INVALID_LOGIN_MESSAGE
    try:
        password_ok = verify_password(password, user.get("password_hash", ""))
    except Exception as exc:
        _log_auth_exception("Password verification failed unexpectedly.", exc)
        raise AuthConnectionError() from exc
    if not password_ok:
        return None, INVALID_LOGIN_MESSAGE
    if password_hash_needs_upgrade(user.get("password_hash", "")):
        user["password_hash"] = hash_password(password)
    user["must_change_password"] = False
    user["failed_login_count"] = 0
    user["locked_until"] = None
    user["last_login_at"] = now_jst_dt()
    user["updated_at"] = now_jst_dt()
    upsert_app_user(user)
    legacy = _legacy_account_row(user)
    legacy.update(
        {
            "id": user.get("id"),
            "login_id": login_id,
            "display_name": user.get("display_name", login_id),
            "password_hash": user.get("password_hash", ""),
            "role": user.get("role", "staff"),
            "must_change_password": bool(user.get("must_change_password")),
            "failed_login_count": int(user.get("failed_login_count") or 0),
            "locked_until": user.get("locked_until"),
            "last_login_at": user.get("last_login_at"),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        }
    )
    return legacy, ""
