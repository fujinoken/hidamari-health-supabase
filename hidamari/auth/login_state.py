import os

import streamlit as st

from hidamari.core.text_utils import clean_text
from hidamari.core.time_utils import now_jst_dt


INITIAL_ACCOUNT_PASSWORD = os.environ.get("HIDAMARI_INITIAL_PASSWORD", "rui").strip() or "rui"
INITIAL_LOGIN_IDS = {"kanri", "staff"}
LOGIN_FAILURE_LIMIT = 5
LOGIN_LOCK_SECONDS = 300


def login_failure_key(login_id):
    login_id = clean_text(login_id).lower()
    return login_id or "__blank__"


def login_failure_store():
    if "login_failures" not in st.session_state:
        st.session_state["login_failures"] = {}
    return st.session_state["login_failures"]


def is_login_temporarily_locked(login_id):
    store = login_failure_store()
    item = store.get(login_failure_key(login_id), {})
    locked_until = float(item.get("locked_until", 0) or 0)
    if locked_until <= 0:
        return False, 0
    now_ts = now_jst_dt().timestamp()
    if now_ts >= locked_until:
        store.pop(login_failure_key(login_id), None)
        return False, 0
    return True, int(locked_until - now_ts)


def record_login_failure(login_id):
    store = login_failure_store()
    key = login_failure_key(login_id)
    item = store.get(key, {"count": 0, "locked_until": 0})
    count = int(item.get("count", 0) or 0) + 1
    locked_until = 0
    if count >= LOGIN_FAILURE_LIMIT:
        locked_until = now_jst_dt().timestamp() + LOGIN_LOCK_SECONDS
    store[key] = {"count": count, "locked_until": locked_until}
    return count, max(LOGIN_FAILURE_LIMIT - count, 0), int(LOGIN_LOCK_SECONDS if locked_until else 0)


def clear_login_failures(login_id):
    try:
        login_failure_store().pop(login_failure_key(login_id), None)
    except Exception:
        pass
