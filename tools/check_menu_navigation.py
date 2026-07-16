"""実データを変更せず、管理者メニュー構成・互換性・権限ガードを確認する。"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MENU_PATH = ROOT / "hidamari" / "config" / "menu.py"
APP_PATH = ROOT / "app.py"


def load_menu_module():
    spec = importlib.util.spec_from_file_location("hidamari_menu_test", MENU_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


menu_config = load_menu_module()

assert list(menu_config.MENU_GROUPS_ADMIN) == [
    "日常管理",
    "日々の記録",
    "マスタ・運用設定",
    "データ管理",
    "システム管理",
]
assert menu_config.MENU_GROUPS_STAFF == {
    "今日の入力": [
        "業務全体申し送り",
        "日々のまとめ入力",
        "健康チェック入力",
        "排泄チェック入力",
        "記録の確認",
        "日々の実施チェック",
    ]
}

expected_admin_entries = {
    "管理者ダッシュボード",
    "記録確認・修正統合",
    "利用者マスタ管理",
    "ログイン・職員ID管理",
    "過去データ管理",
    "排泄詳細管理",
    "未入力・注意記録",
    "管理者支援",
    "LIFE入力標準化",
    "データダウンロード",
    "バックアップ管理",
    "監査ログ",
    "セキュリティ・保守管理",
    "利用者ID移行チェック",
    "利用者名ゆれ紐づけマスタ",
    "メニューカテゴリ設定",
    "システム設定",
}
admin_entries = {item for values in menu_config.MENU_GROUPS_ADMIN.values() for item in values}
assert expected_admin_entries <= admin_entries

# 新表示名と、表示名が保存された場合の内部キー復元。
assert menu_config.menu_display_label("過去データ管理") == "健康記録の確認・修正"
assert menu_config.menu_display_label("排泄詳細管理") == "排泄記録の確認・修正"
assert menu_config.menu_display_label("管理者支援") == "分析・確認支援"
assert menu_config.menu_display_label("セキュリティ・保守管理") == "セキュリティ・保守"
assert menu_config.menu_display_label("LIFE入力標準化") == "LIFE管理"
assert menu_config.menu_display_label("記録確認・修正統合") == "記録確認・修正"
assert menu_config.canonical_menu_key("記録確認・修正") == "記録確認・修正統合"
assert menu_config.canonical_menu_key("健康記録の確認・修正") == "過去データ管理"
assert menu_config.canonical_menu_key("分析・確認支援") == "管理者支援"

# 旧標準カテゴリはメニューごとの新しい所属先へ移し、独自カテゴリは維持する。
assert menu_config.canonical_menu_category("朝の確認", "管理者ダッシュボード") == "日常管理"
assert menu_config.canonical_menu_category("設定・保守", "システム設定") == "マスタ・運用設定"
assert menu_config.canonical_menu_category("設定・保守", "利用者ID移行チェック") == "システム管理"
assert menu_config.canonical_menu_category("施設独自", "システム設定") == "施設独自"
assert menu_config.valid_saved_menu_rows(None) == []
assert menu_config.valid_saved_menu_rows("broken") == []
assert menu_config.valid_saved_menu_rows(["broken", {"メニュー": "管理者ダッシュボード"}]) == [
    {"メニュー": "管理者ダッシュボード"}
]


app_source = APP_PATH.read_text(encoding="utf-8")
tree = ast.parse(app_source, filename=str(APP_PATH))
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

# 保存設定の読込を、DBへ接続せずスタブで確認する。
settings_namespace = {
    "pd": pd,
    "MENU_GROUPS_ADMIN": menu_config.MENU_GROUPS_ADMIN,
    "MENU_GROUPS_STAFF": menu_config.MENU_GROUPS_STAFF,
    "HIDDEN_MENUS": ["モニタリング下書き作成"],
    "MENU_CATEGORY_SETTINGS_FILE": Path("unused.json"),
    "canonical_menu_category": menu_config.canonical_menu_category,
    "canonical_menu_key": menu_config.canonical_menu_key,
    "valid_saved_menu_rows": menu_config.valid_saved_menu_rows,
    "clean_text": lambda value, default="": str(value).strip() if value is not None and str(value).strip() else default,
    "ensure_dirs": lambda: None,
    "migrate_json_file_setting_to_db": lambda *args, **kwargs: {},
}
settings_function_names = {
    "get_standard_menu_groups",
    "make_menu_category_rows_from_groups",
    "get_standard_menu_category_df",
    "normalize_menu_category_df",
    "load_menu_category_settings",
}
settings_nodes = [
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in settings_function_names
]
exec(compile(ast.Module(body=settings_nodes, type_ignores=[]), str(APP_PATH), "exec"), settings_namespace)

for broken_value in [None, "broken", {"unexpected": True}, ["broken-row"]]:
    settings_namespace["get_app_setting"] = lambda *args, value=broken_value, **kwargs: {"admin": value}
    fallback_df = settings_namespace["load_menu_category_settings"]("admin")
    assert set(fallback_df["カテゴリ"].tolist()) == set(menu_config.MENU_GROUPS_ADMIN)
    assert set(fallback_df["メニュー"].tolist()) == admin_entries

legacy_rows = [
    {"表示": True, "カテゴリ": "朝の確認", "メニュー": "管理者ダッシュボード", "並び順": 1, "備考": "旧設定"},
    {"表示": True, "カテゴリ": "設定・保守", "メニュー": "システム設定", "並び順": 2, "備考": "旧設定"},
    {"表示": True, "カテゴリ": "設定・保守", "メニュー": "利用者ID移行チェック", "並び順": 3, "備考": "旧設定"},
    {"表示": True, "カテゴリ": "壊れたカテゴリ", "メニュー": "存在しない画面", "並び順": 4, "備考": "不正"},
]
settings_namespace["get_app_setting"] = lambda *args, **kwargs: {"admin": legacy_rows}
legacy_df = settings_namespace["load_menu_category_settings"]("admin")
category_by_menu = dict(zip(legacy_df["メニュー"], legacy_df["カテゴリ"]))
assert category_by_menu["管理者ダッシュボード"] == "日常管理"
assert category_by_menu["システム設定"] == "マスタ・運用設定"
assert category_by_menu["利用者ID移行チェック"] == "システム管理"
assert "存在しない画面" not in category_by_menu


class StreamlitStub:
    def __init__(self, role="staff", username="staff"):
        self.session_state = {"role": role, "username": username}
        self.errors = []

    def error(self, message):
        self.errors.append(str(message))


namespace = {
    "MENU_GROUPS_ADMIN": menu_config.MENU_GROUPS_ADMIN,
    "HIDDEN_MENUS": ["モニタリング下書き作成"],
    "canonical_menu_key": menu_config.canonical_menu_key,
    "menu_display_label": menu_config.menu_display_label,
    "is_admin_identity": lambda role="", user="": role == "admin" or user == "kanri",
    "st": StreamlitStub(),
}

selected_nodes = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if names & {"SHARED_OPERATION_MENUS", "ADMIN_ONLY_MENUS"}:
            selected_nodes.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in {
        "is_admin_user",
        "filter_admin_menus",
        "require_admin_access",
        "guard_selected_menu",
    }:
        selected_nodes.append(node)

exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), str(APP_PATH), "exec"), namespace)

admin_only = set(namespace["ADMIN_ONLY_MENUS"])
for protected in expected_admin_entries - {"管理者ダッシュボード"}:
    assert protected in admin_only
assert "管理者ダッシュボード" in admin_only
for shared in menu_config.MENU_GROUPS_STAFF["今日の入力"]:
    if shared != "記録の確認":
        assert shared not in admin_only

staff_visible = namespace["filter_admin_menus"](
    ["健康チェック入力", "利用者マスタ管理", "データダウンロード", "AI管理者アシスタント"]
)
assert staff_visible == ["健康チェック入力"]
assert namespace["guard_selected_menu"]("健康チェック入力") is True
assert namespace["guard_selected_menu"]("健康記録の確認・修正") is False
assert namespace["guard_selected_menu"]("セキュリティ・保守") is False
assert namespace["st"].errors

namespace["st"] = StreamlitStub(role="admin", username="kanri")
assert namespace["guard_selected_menu"]("健康記録の確認・修正") is True
assert namespace["guard_selected_menu"]("AI管理者アシスタント") is True

# 旧内部キーの画面分岐と、新入口から既存画面への解決処理が残っている。
branch_names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "menu":
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                branch_names.add(comparator.value)
for old_key in [
    "管理者ダッシュボード",
    "過去データ管理",
    "排泄詳細管理",
    "管理者支援",
    "セキュリティ・保守管理",
    "家族向けレポート作成",
    "ひだまりレポートPDF",
]:
    assert old_key in branch_names
assert 'resolved_menu_entry == "未入力・注意記録"' in app_source
assert 'resolved_menu_entry in {"バックアップ管理", "監査ログ"}' in app_source

print("menu navigation and admin guard checks: OK")
