import hashlib
import re

try:
    import bcrypt
except Exception:
    bcrypt = None

from hidamari.auth.login_state import INITIAL_ACCOUNT_PASSWORD, INITIAL_LOGIN_IDS
from hidamari.core.text_utils import clean_text


def is_bcrypt_available() -> bool:
    """bcryptライブラリが利用できるか確認する。"""
    return bcrypt is not None


def is_bcrypt_hash(password_hash: str) -> bool:
    """保存済みハッシュがbcrypt形式か判定する。"""
    h = clean_text(password_hash)
    return h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$")


def is_legacy_sha256_hash(password_hash: str) -> bool:
    """旧SHA256形式のハッシュか判定する。"""
    h = clean_text(password_hash)
    if h.startswith("sha256$"):
        return True
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", h))


def make_sha256_hash(password: str) -> str:
    """互換用SHA256ハッシュ。bcrypt未導入時の緊急フォールバックにも使う。"""
    password = clean_text(password)
    return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """
    パスワードをbcryptでハッシュ化して保存する。
    bcryptが未インストールの場合のみ、アプリ停止を避けるためSHA256形式で保存する。
    """
    password = clean_text(password)
    if is_bcrypt_available():
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    return make_sha256_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """入力パスワードと保存済みハッシュを照合する。bcrypt優先、旧SHA256互換。"""
    password = clean_text(password)
    stored = clean_text(password_hash)

    if not password or not stored:
        return False

    if is_bcrypt_hash(stored):
        if not is_bcrypt_available():
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False

    if is_legacy_sha256_hash(stored):
        raw = stored.replace("sha256$", "", 1)
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == raw

    return password == stored


def password_hash_needs_upgrade(password_hash: str) -> bool:
    """bcryptでないハッシュは、ログイン成功時にbcryptへ自動更新する。"""
    return is_bcrypt_available() and not is_bcrypt_hash(password_hash)


def uses_initial_password(login_id, password) -> bool:
    return clean_text(login_id).lower() in INITIAL_LOGIN_IDS and clean_text(password) == INITIAL_ACCOUNT_PASSWORD


def account_requires_password_change(account_row) -> bool:
    """アカウントが初回パスワード変更必須か判定する。"""
    if not isinstance(account_row, dict):
        try:
            account_row = account_row.to_dict()
        except Exception:
            return False
    value = clean_text(account_row.get("初回パスワード変更必須"))
    return value in ["はい", "必須", "1", "true", "True", "TRUE"]


def validate_new_password(login_id, new_password, confirm_password, current_hash=""):
    """商品化向けの最低限のパスワード安全性チェック。"""
    login_id = clean_text(login_id).lower()
    new_password = clean_text(new_password)
    confirm_password = clean_text(confirm_password)

    if not new_password:
        return False, "新しいパスワードを入力してください。"
    if new_password != confirm_password:
        return False, "確認用パスワードが一致しません。"
    if len(new_password) < 8:
        return False, "パスワードは8文字以上にしてください。"
    weak_passwords = {INITIAL_ACCOUNT_PASSWORD.lower(), "password", "password123", "12345678", "admin123"}
    if new_password.lower() in weak_passwords:
        return False, "推測されやすいパスワードは使用できません。"
    if login_id and login_id in new_password.lower():
        return False, "ログインIDを含むパスワードは使用できません。"
    if not re.search(r"[A-Za-z]", new_password) or not re.search(r"[0-9]", new_password):
        return False, "英字と数字を両方含めてください。"
    if current_hash and verify_password(new_password, current_hash):
        return False, "現在と同じパスワードは使用できません。"
    return True, ""
