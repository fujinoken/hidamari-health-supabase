"""実データを変更せず、管理者向け記録確認・修正入口を確認する。"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MENU_PATH = ROOT / "hidamari" / "config" / "menu.py"
APP_PATH = ROOT / "app.py"


def load_menu_module():
    spec = importlib.util.spec_from_file_location("hidamari_menu_record_entry_test", MENU_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


menu_config = load_menu_module()
entry_key = "記録確認・修正統合"

assert entry_key in menu_config.MENU_GROUPS_ADMIN["日常管理"]
assert all(entry_key not in menus for menus in menu_config.MENU_GROUPS_STAFF.values())
assert menu_config.MENU_DISPLAY_LABELS[entry_key] == "記録確認・修正"
assert menu_config.canonical_menu_key("記録確認・修正") == entry_key

expected_targets = {
    "健康記録": "過去データ管理",
    "排泄記録": "排泄詳細管理",
    "短期目標の実施記録": "実施履歴一覧",
    "申し送り": "業務全体申し送り",
    "未入力・注意記録": "未入力・注意記録",
}
assert tuple(expected_targets) == menu_config.ADMIN_RECORD_MANAGEMENT_OPTIONS
for record_type, target in expected_targets.items():
    assert menu_config.admin_record_management_target(record_type) == target
assert menu_config.admin_record_management_target("不正な値") == "過去データ管理"

app_source = APP_PATH.read_text(encoding="utf-8")
tree = ast.parse(app_source, filename=str(APP_PATH))
functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

entry_source = ast.get_source_segment(app_source, functions["show_admin_record_management_entry"])
assert 'require_admin_access("記録確認・修正統合")' in entry_source
assert 'st.header("記録確認・修正")' in entry_source
assert "確認する記録の種類を選択してください。既存の記録内容や保存方法は変更されません。" in entry_source
assert '"確認する記録"' in entry_source
assert 'key="admin_record_management_type"' in entry_source
assert "st.tabs(" not in entry_source

# 新入口は既存分岐へ解決し、旧入口・旧内部キーも残す。
branch_names = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "menu":
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                branch_names.add(comparator.value)
for target in ["過去データ管理", "排泄詳細管理", "実施履歴一覧", "業務全体申し送り"]:
    assert target in branch_names
assert 'selected_menu_entry == "記録確認・修正統合"' in app_source
assert 'resolved_menu_entry = show_admin_record_management_entry()' in app_source
assert 'st.session_state["past_data_mode"] = "健康チェック"' in app_source
assert 'st.session_state["past_data_mode"] = "入力状況"' in app_source

# ADMIN_ONLY_MENUSは管理者メニューから自動生成されるため、新入口も保護対象になる。
shared_node = next(
    node
    for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "SHARED_OPERATION_MENUS" for target in node.targets)
)
admin_only_node = next(
    node
    for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "ADMIN_ONLY_MENUS" for target in node.targets)
)
namespace = {"MENU_GROUPS_ADMIN": menu_config.MENU_GROUPS_ADMIN}
exec(compile(ast.Module(body=[shared_node, admin_only_node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
assert entry_key in namespace["ADMIN_ONLY_MENUS"]

# 職員向けの記録確認は既存どおり閲覧専用。
confirmation_source = ast.get_source_segment(app_source, functions["show_record_confirmation"])
assert 'st.form("staff_record_confirmation_form")' in confirmation_source
for forbidden in ["st.data_editor(", "st.download_button(", "削除する", "更新する"]:
    assert forbidden not in confirmation_source

print("record management entry checks: OK")
