import ast
import math
import re
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
SUMMARY_COLUMNS = ["記録日", "利用者名", "排尿回数", "排便回数"]


def _app_functions(*names, globals_dict=None):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    missing = set(names) - {node.name for node in selected}
    if missing:
        raise AssertionError(f"missing app functions: {sorted(missing)}")
    namespace = dict(globals_dict or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


class ExcretionDailySummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def clean_text(value, default=""):
            if value is None or (not isinstance(value, str) and pd.isna(value)):
                return default
            text = str(value).strip()
            return text if text and text.lower() not in {"nan", "none", "nat"} else default

        def normalize_name(value):
            return clean_text(value).replace(" ", "").replace("　", "").replace("様", "").lower()

        cls.namespace = _app_functions(
            "_parse_record_datetime",
            "_record_datetime_series",
            "_normalize_user_id",
            "_normalize_user_name",
            "_record_user_mask",
            "is_present_excretion_value",
            "_excretion_value_count",
            "is_stool_present_row",
            "count_stool_records",
            "count_urine_records",
            "summarize_excretion",
            "filter_excretion_records_for_period",
            "build_daily_excretion_summary",
            "daily_excretion_summary_csv",
            globals_dict={
                "pd": pd,
                "math": math,
                "re": re,
                "timedelta": timedelta,
                "clean_text": clean_text,
                "normalize_user_name_for_match": normalize_name,
                "get_user_id_by_name": lambda name: {"同姓同名様": "u-1", "対象者様": "u-3"}.get(name, ""),
                "DAILY_EXCRETION_SUMMARY_COLUMNS": SUMMARY_COLUMNS,
                "EXCRETION_COLUMNS": [],
            },
        )

    def test_multiple_slots_are_one_row_and_counts_are_summed(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-04", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-04T12:30:00", "利用者名": "対象者様", "user_id": "u-3", "尿量": "2", "便量": "少", "便性状": "普通便"},
            {"記録日": "2026/07/04", "利用者名": "対象者様", "user_id": "u-3", "尿量": "なし", "便量": "2", "便性状": "普通便"},
        ])
        result = self.namespace["build_daily_excretion_summary"](source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0].to_dict(), {
            "記録日": "2026-07-04",
            "利用者名": "対象者様",
            "排尿回数": 3,
            "排便回数": 3,
        })

    def test_none_zero_blank_nan_and_unrecognized_values_are_not_added(self):
        values = ["なし", "0", "", float("nan"), "未入力", "変換不能"]
        counts = [self.namespace["_excretion_value_count"](value) for value in values]
        self.assertEqual(counts, [0, 0, 0, 0, 0, 0])

        source = pd.DataFrame([
            {"記録日": "2026-07-04", "利用者名": "対象者様", "user_id": "u-3", "尿量": value, "便量": "なし", "便性状": "なし"}
            for value in values[:-1]
        ])
        result = self.namespace["build_daily_excretion_summary"](source)
        self.assertEqual(int(result.iloc[0]["排尿回数"]), 0)
        self.assertEqual(int(result.iloc[0]["排便回数"]), 0)

    def test_existing_summary_rules_are_unchanged_for_normal_category_values(self):
        source = pd.DataFrame([
            {"尿量": "中", "尿性状": "普通尿", "便量": "少", "便量コード": "1", "便性状": "普通便", "便性状コード": "1"},
            {"尿量": "なし", "尿性状": "なし", "便量": "なし", "便量コード": "0", "便性状": "なし", "便性状コード": "0"},
        ])
        summary = self.namespace["summarize_excretion"](source)
        self.assertEqual(summary["排尿回数"], 1)
        self.assertEqual(summary["排便回数"], 1)
        self.assertEqual(summary["排便なし枠"], 1)

    def test_same_name_different_user_ids_and_multiple_users_do_not_mix(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-04", "利用者名": "同姓同名様", "user_id": "u-1", "尿量": "中", "便量": "少", "便性状": "普通便"},
            {"記録日": "2026-07-04", "利用者名": "同姓同名様", "user_id": "u-2", "尿量": "2", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-04", "利用者名": "対象者様", "user_id": "u-3", "尿量": "大", "便量": "なし", "便性状": "なし"},
        ])
        result = self.namespace["build_daily_excretion_summary"](source)
        self.assertEqual(len(result), 3)
        same_name = result[result["利用者名"] == "同姓同名様"]
        self.assertEqual(sorted(same_name["排尿回数"].tolist()), [1, 2])
        selected = self.namespace["filter_excretion_records_for_period"](
            source, date(2026, 7, 4), date(2026, 7, 4), "同姓同名様"
        )
        self.assertEqual(selected["user_id"].tolist(), ["u-1"])

    def test_newest_date_is_displayed_first(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-02", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-04", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-03", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
        ])
        result = self.namespace["build_daily_excretion_summary"](source)
        self.assertEqual(result["記録日"].tolist(), ["2026-07-04", "2026-07-03", "2026-07-02"])

    def test_period_and_user_filter_are_shared_by_screen_and_csv_data(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-03", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-04T23:59:59+09:00", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "少", "便性状": "普通便"},
            {"記録日": "2026-07-05", "利用者名": "対象者様", "user_id": "u-3", "尿量": "中", "便量": "なし", "便性状": "なし"},
            {"記録日": "2026-07-04", "利用者名": "別利用者様", "user_id": "u-9", "尿量": "大", "便量": "大", "便性状": "普通便"},
        ])
        filtered = self.namespace["filter_excretion_records_for_period"](
            source, date(2026, 7, 4), date(2026, 7, 4), "対象者様"
        )
        screen = self.namespace["build_daily_excretion_summary"](filtered)
        csv_bytes = self.namespace["daily_excretion_summary_csv"](screen)
        exported = pd.read_csv(BytesIO(csv_bytes))
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(screen.astype(str).to_dict("records"), exported.astype(str).to_dict("records"))
        self.assertEqual(screen["記録日"].tolist(), ["2026-07-04"])
        self.assertEqual(screen["利用者名"].tolist(), ["対象者様"])

    def test_empty_data_is_safe(self):
        result = self.namespace["build_daily_excretion_summary"](pd.DataFrame())
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), SUMMARY_COLUMNS)

    def test_screen_uses_daily_summary_for_both_table_and_csv(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn('st.subheader("日別の排泄集計")', source)
        self.assertIn("daily_summary = build_daily_excretion_summary(work)", source)
        self.assertIn("st.dataframe(daily_summary", source)
        self.assertIn("csv = daily_excretion_summary_csv(daily_summary)", source)
        self.assertIn('"日別排泄集計CSVをダウンロード"', source)
        self.assertIn('file_name="日別排泄集計.csv"', source)
        self.assertIn('st.subheader("排泄データの更新・削除")', source)


if __name__ == "__main__":
    unittest.main()
