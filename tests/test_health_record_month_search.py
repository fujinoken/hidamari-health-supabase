import ast
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def _app_functions(*names, globals_dict=None):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    missing = set(names) - {node.name for node in selected}
    if missing:
        raise AssertionError(f"missing app functions: {sorted(missing)}")
    namespace = dict(globals_dict or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


class HealthRecordMonthFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def normalize_name(value):
            return str(value or "").replace(" ", "").replace("　", "").replace("様", "").lower()

        cls.namespace = _app_functions(
            "_parse_record_datetime",
            "_record_datetime_series",
            "_filter_health_df_by_date_range",
            "_normalize_user_id",
            "_normalize_user_name",
            "_record_user_mask",
            "filter_health_records_for_month",
            globals_dict={
                "pd": pd,
                "date": date,
                "timedelta": timedelta,
                "re": __import__("re"),
                "normalize_user_name_for_match": normalize_name,
                "get_user_id_by_name": lambda name: {"対象 利用者": "u-1"}.get(name, ""),
            },
        )

    def test_month_boundaries_mixed_formats_user_and_no_deduplication(self):
        rows = [
            {"記録日": "2026-06-30", "利用者名": "対象 利用者", "user_id": "u-1", "値": "before"},
            {"記録日": "2026-07-01", "利用者名": "対象 利用者", "user_id": "u-1", "値": "first"},
            {"記録日": "2026-07-19T00:00:00", "利用者名": "対象 利用者", "user_id": "u-1", "値": "iso-a"},
            {"記録日": "2026-07-19T12:30:00", "利用者名": "対象 利用者", "user_id": "u-1", "値": "iso-b"},
            {"記録日": "2026/07/20", "利用者名": "対象 利用者様", "user_id": "", "値": "slash"},
            {"記録日": "2026-07-31T23:59:59", "利用者名": "対象 利用者", "user_id": "u-1", "値": "last"},
            {"記録日": "2026-08-01", "利用者名": "対象 利用者", "user_id": "u-1", "値": "after"},
            {"記録日": "2026-07-10", "利用者名": "別利用者", "user_id": "u-2", "値": "other"},
        ]
        result = self.namespace["filter_health_records_for_month"](
            pd.DataFrame(rows), 2026, 7, "対象 利用者"
        )
        self.assertEqual(result["値"].tolist(), ["first", "iso-a", "iso-b", "slash", "last"])
        self.assertEqual(len(result[result["記録日"].dt.day == 19]), 2)

    def test_more_than_twenty_records_and_excel_count_match(self):
        source = pd.DataFrame([
            {"記録日": f"2026-07-{day:02d}", "利用者名": "対象 利用者", "user_id": "u-1"}
            for day in range(1, 32)
        ])
        result = self.namespace["filter_health_records_for_month"](source, 2026, 7, "対象 利用者")
        self.assertEqual(len(result), 31)

        excel_ns = _app_functions("to_excel_download", globals_dict={"pd": pd, "BytesIO": BytesIO})
        exported = pd.read_excel(BytesIO(excel_ns["to_excel_download"](result)))
        self.assertEqual(len(exported), len(result))

    def test_sqlite_style_dataframe_uses_same_mixed_date_normalization(self):
        namespace = _app_functions(
            "_date_to_iso",
            "_parse_record_datetime",
            "_record_datetime_series",
            "_filter_health_df_by_date_range",
            globals_dict={"pd": pd, "timedelta": timedelta},
        )
        source = pd.DataFrame({
            "記録日": ["2026-06-30", "2026/07/01", "2026-07-31T23:59:59", "2026/08/01"],
            "値": ["before", "first", "last", "after"],
        })
        result = namespace["_filter_health_df_by_date_range"](
            source, "記録日", date(2026, 7, 1), date(2026, 7, 31)
        )
        self.assertEqual(result["値"].tolist(), ["first", "last"])

    def test_timezone_offsets_preserve_the_recorded_calendar_day(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-31T23:59:59+09:00", "利用者名": "対象 利用者", "user_id": "u-1"},
            {"記録日": "2026-08-01T00:00:00+09:00", "利用者名": "対象 利用者", "user_id": "u-1"},
        ])
        result = self.namespace["filter_health_records_for_month"](
            source, 2026, 7, "対象 利用者"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["記録日"].day, 31)

    def test_same_name_with_another_nonempty_user_id_is_excluded(self):
        source = pd.DataFrame([
            {"記録日": "2026-07-10", "利用者名": "対象 利用者", "user_id": "u-1", "値": "selected"},
            {"記録日": "2026-07-11", "利用者名": "対象 利用者", "user_id": "u-2", "値": "same-name-other-id"},
        ])
        result = self.namespace["filter_health_records_for_month"](
            source, 2026, 7, "対象 利用者"
        )
        self.assertEqual(result["値"].tolist(), ["selected"])


class SupabaseHealthDateQueryTests(unittest.TestCase):
    def test_health_query_uses_hyphen_and_slash_half_open_ranges(self):
        calls = []

        def read_table(_table, _columns, _field, start, end, _limit):
            calls.append((start, end))
            return pd.DataFrame(columns=["記録日"])

        def cache_decorator(**_kwargs):
            return lambda func: func

        namespace = _app_functions(
            "_supabase_read_health_records_cached",
            globals_dict={
                "pd": pd,
                "SQLITE_TABLE_HEALTH": "health_records",
                "DEFAULT_QUERY_CACHE_TTL_SEC": 60,
                "cache_safe_master_read": cache_decorator,
                "_supabase_read_table_uncached": read_table,
            },
        )
        namespace["_supabase_read_health_records_cached"](
            ("記録日",), "記録日", "2026-07-01", "2026-07-31", 0
        )
        self.assertEqual(calls, [
            ("2026-07-01", "2026-07-31"),
            ("2026/07/01", "2026/07/31"),
        ])

    def test_hyphen_and_slash_text_ranges_do_not_overlap(self):
        hyphen_lower = "2026-07-01"
        hyphen_upper = "2026-08-01"
        slash_lower = "2026/07/01"
        slash_upper = "2026/08/01"
        self.assertLess(hyphen_lower, hyphen_upper)
        self.assertLess(hyphen_upper, slash_lower)
        self.assertLess(slash_lower, slash_upper)

    def test_exclusive_end_preserves_separator(self):
        namespace = _app_functions(
            "_parse_record_datetime",
            "_exclusive_end_date_text",
            globals_dict={"pd": pd, "timedelta": timedelta},
        )
        self.assertEqual(namespace["_exclusive_end_date_text"]("2026-07-31"), "2026-08-01")
        self.assertEqual(namespace["_exclusive_end_date_text"]("2026/07/31"), "2026/08/01")


class SupabasePagingTests(unittest.TestCase):
    def test_unlimited_query_pages_past_server_thousand_row_cap(self):
        first = [{"data": {"記録日": "2026-07-01"}} for _ in range(1000)]
        second = [{"data": {"記録日": "2026-07-02"}} for _ in range(5)]
        response1 = mock.Mock()
        response1.json.return_value = first
        response2 = mock.Mock()
        response2.json.return_value = second
        requests = mock.Mock()
        requests.get.side_effect = [response1, response2]

        class Timer:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        namespace = _app_functions(
            "_supabase_read_table_uncached",
            globals_dict={
                "pd": pd,
                "timedelta": timedelta,
                "requests": requests,
                "SQLITE_TABLE_HEALTH": "health_records",
                "_exclusive_end_date_text": lambda value: "2026-08-01",
                "_supabase_endpoint": lambda table: table,
                "_supabase_headers": lambda prefer="": {},
                "perf_timer": lambda *_args: Timer(),
                "diagnostic_log": lambda *_args, **_kwargs: None,
                "_normalize_supabase_df_from_rows": lambda rows, _columns: pd.DataFrame([item["data"] for item in rows]),
            },
        )
        result = namespace["_supabase_read_table_uncached"](
            "health_records", ("記録日",), "記録日", "2026-07-01", "2026-07-31", 0
        )
        self.assertEqual(len(result), 1005)
        self.assertEqual(requests.get.call_count, 2)
        self.assertEqual(requests.get.call_args_list[0].kwargs["headers"]["Range"], "0-999")
        self.assertEqual(requests.get.call_args_list[1].kwargs["headers"]["Range"], "1000-1999")

    def test_repeated_full_page_stops_without_adding_duplicates_forever(self):
        page = [
            {"record_key": f"key-{index:04d}", "data": {"記録日": "2026-07-01"}}
            for index in range(1000)
        ]
        response1 = mock.Mock()
        response1.json.return_value = page
        response2 = mock.Mock()
        response2.json.return_value = page
        requests = mock.Mock()
        requests.get.side_effect = [response1, response2]

        class Timer:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        namespace = _app_functions(
            "_supabase_read_table_uncached",
            globals_dict={
                "pd": pd,
                "requests": requests,
                "SQLITE_TABLE_HEALTH": "health_records",
                "_exclusive_end_date_text": lambda value: "2026-08-01",
                "_supabase_endpoint": lambda table: table,
                "_supabase_headers": lambda prefer="": {},
                "perf_timer": lambda *_args: Timer(),
                "diagnostic_log": lambda *_args, **_kwargs: None,
                "_normalize_supabase_df_from_rows": lambda rows, _columns: pd.DataFrame([item["data"] for item in rows]),
            },
        )
        result = namespace["_supabase_read_table_uncached"](
            "health_records", ("記録日",), "記録日", "2026-07-01", "2026-07-31", 0
        )
        self.assertEqual(len(result), 1000)
        self.assertEqual(requests.get.call_count, 2)

    def test_non_health_query_keeps_single_request_without_range_header(self):
        response = mock.Mock()
        response.json.return_value = [
            {"record_key": f"key-{index:04d}", "data": {"日付": "2026-07-01"}}
            for index in range(1000)
        ]
        requests = mock.Mock()
        requests.get.return_value = response

        class Timer:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        namespace = _app_functions(
            "_supabase_read_table_uncached",
            globals_dict={
                "pd": pd,
                "requests": requests,
                "SQLITE_TABLE_HEALTH": "health_records",
                "_exclusive_end_date_text": lambda value: "2026-08-01",
                "_supabase_endpoint": lambda table: table,
                "_supabase_headers": lambda prefer="": {},
                "perf_timer": lambda *_args: Timer(),
                "diagnostic_log": lambda *_args, **_kwargs: None,
                "_normalize_supabase_df_from_rows": lambda rows, _columns: pd.DataFrame([item["data"] for item in rows]),
            },
        )
        result = namespace["_supabase_read_table_uncached"](
            "handover_logs", ("日付",), "日付", "2026-07-01", "2026-07-31", 0
        )
        self.assertEqual(len(result), 1000)
        self.assertEqual(requests.get.call_count, 1)
        headers = requests.get.call_args.kwargs["headers"]
        self.assertNotIn("Range", headers)
        self.assertIn(("order", "updated_at.desc"), requests.get.call_args.kwargs["params"])


class AdminHealthRecordRouteTests(unittest.TestCase):
    def test_admin_health_record_entry_reaches_past_data_management_branch(self):
        from hidamari.config import menu as menu_config

        self.assertEqual(
            menu_config.admin_record_management_target("健康記録"),
            "過去データ管理",
        )
        self.assertEqual(
            menu_config.canonical_menu_key("健康記録の確認・修正"),
            "過去データ管理",
        )
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertIn('resolved_menu_entry = show_admin_record_management_entry()', source)
        self.assertIn('st.session_state["past_data_mode"] = "健康チェック"', source)
        self.assertIn('menu = resolved_menu_entry', source)
        self.assertIn('elif menu == "過去データ管理":', source)
        self.assertIn('st.subheader("一覧検索")', source)


if __name__ == "__main__":
    unittest.main()
