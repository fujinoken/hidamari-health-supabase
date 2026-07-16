"""実データを変更せず、健康・排泄記録の比較ルールだけを確認する。"""

import ast
import re
from datetime import date
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = {
    "_date_to_iso",
    "_filter_df_by_date_range",
    "_normalize_record_date",
    "_normalize_user_id",
    "_normalize_user_name",
    "_record_user_mask",
    "find_health_index",
    "_filter_excretion_records",
    "find_excretion_index",
}


def clean_text(value, default=""):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return default
    text = str(value).strip()
    return default if text.lower() in ["", "nan", "none", "nat"] else text


def normalize_user_name_for_match(value):
    text = re.sub(r"\s+", "", clean_text(value)).replace("　", "")
    return text.replace("様", "").replace("さん", "").replace("殿", "").lower()


def get_user_id_by_name(value):
    return {"山田": "official-u", "山田様": "official-u"}.get(clean_text(value), "")


app_source = (ROOT / "app.py").read_text(encoding="utf-8")
tree = ast.parse(app_source)
selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
namespace = {
    "pd": pd,
    "re": re,
    "clean_text": clean_text,
    "normalize_user_name_for_match": normalize_user_name_for_match,
    "get_user_id_by_name": get_user_id_by_name,
    "EXCRETION_COLUMNS": ["記録日", "利用者名", "user_id", "時間帯"],
}
exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / "app.py"), "exec"), namespace)

find_health_index = namespace["find_health_index"]
filter_excretion_records = namespace["_filter_excretion_records"]
find_excretion_index = namespace["find_excretion_index"]
filter_df_by_date_range = namespace["_filter_df_by_date_range"]

for date_value in [
    "2026-07-01T09:00:00",
    "2026-07-02",
    "2026/07/03",
    date(2026, 7, 4),
    pd.Timestamp("2026-07-05 18:30"),
]:
    single_date_df = pd.DataFrame({"記録日": [date_value]})
    filtered_date = filter_df_by_date_range(single_date_df, "記録日", date(2026, 7, 1), "2026/07/05")
    assert filtered_date.index.tolist() == [0]

inclusive_end_df = pd.DataFrame({"記録日": ["2026-07-04", "2026-07-05", "2026-07-06"]})
inclusive_end = filter_df_by_date_range(inclusive_end_df, "記録日", "2026-07-04", "2026-07-05")
assert inclusive_end.index.tolist() == [0, 1]

health = pd.DataFrame(
    [
        {"記録日": "2026-07-01", "利用者名": "旧表示名", "user_id": "u-1"},
        {"記録日": "2026/07/02", "利用者名": " 山田　様 ", "user_id": None},
        {"記録日": date(2026, 7, 3), "利用者名": "山田", "user_id": 123.0},
        {"記録日": pd.Timestamp("2026-07-04 09:30"), "利用者名": "山田", "user_id": "u-4"},
        {"記録日": "2026-07-05", "利用者名": "山田", "user_id": "別ID"},
        {"記録日": "2026-07-06", "利用者名": float("nan"), "user_id": None},
    ]
)

assert find_health_index(health, "2026-07-01", "現在名", "u-1") == 0
assert find_health_index(health, "2026-07-02", "山田", "official-u") == 1
assert find_health_index(health, pd.Timestamp("2026-07-03"), "山田", "123") == 2
assert find_health_index(health, date(2026, 7, 4), "山田", "u-4") == 3
assert find_health_index(health, "2026-07-05", "山田", "official-u") is None
assert find_health_index(health, "2026-07-06", "山田", "official-u") is None

excretion = pd.DataFrame(
    [
        {"記録日": "2026/07/02", "利用者名": " 山田　様 ", "user_id": None, "時間帯": "午前"},
        {"記録日": pd.Timestamp("2026-07-02 18:00"), "利用者名": "山田", "user_id": "official-u", "時間帯": "夜間"},
    ]
)
records = filter_excretion_records(excretion, date(2026, 7, 2), "山田", "official-u")
assert records.index.tolist() == [0, 1]
assert find_excretion_index(excretion, "2026-07-02", "山田", "午前", "official-u") == 0
assert find_excretion_index(excretion, "2026-07-02", "山田", "夜間", "official-u") == 1
assert find_excretion_index(excretion, "2026-07-02", "山田", "午後", "official-u") is None

menu_source = (ROOT / "hidamari" / "config" / "menu.py").read_text(encoding="utf-8")
menu_tree = ast.parse(menu_source)
staff_menu_node = next(
    node
    for node in menu_tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "MENU_GROUPS_STAFF" for target in node.targets)
)
staff_menu_groups = ast.literal_eval(staff_menu_node.value)
assert staff_menu_groups == {
    "今日の入力": [
        "業務全体申し送り",
        "日々のまとめ入力",
        "健康チェック入力",
        "排泄チェック入力",
        "記録の確認",
        "日々の実施チェック",
    ]
}
confirmation_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "show_record_confirmation")
confirmation_source = ast.get_source_segment(app_source, confirmation_node)
assert 'st.form("staff_record_confirmation_form")' in confirmation_source
assert 'st.form_submit_button("記録を表示"' in confirmation_source
for forbidden in ["st.data_editor(", "st.download_button(", "st.button(", "削除する", "更新する"]:
    assert forbidden not in confirmation_source

print("record matching checks: OK")
