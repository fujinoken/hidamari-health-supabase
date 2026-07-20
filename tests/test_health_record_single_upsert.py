import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

from db import database


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
HEALTH_COLUMNS = [
    "記録日", "利用者名", "user_id", "体温", "血圧上", "血圧下", "脈拍", "SpO2", "体重",
    "朝食摂取率", "昼食摂取率", "夕食摂取率", "朝食摂取区分", "昼食摂取区分", "夕食摂取区分",
    "水分摂取量ml", "栄養リスク", "口腔状態", "義歯使用", "LIFE補助メモ", "家族共有メモ",
    "気になる変化", "登録日時", "入力者",
]


def _app_functions(*names, globals_dict=None):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    missing = set(names) - {node.name for node in selected}
    if missing:
        raise AssertionError(f"missing app functions: {sorted(missing)}")
    namespace = dict(globals_dict or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace


class SQLiteHealthRecordUpsertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.tmp.name) / "health.db"
        database.configure_database(self.tmp.name, self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def record(day, name, user_id, temperature):
        row = {column: "" for column in HEALTH_COLUMNS}
        row.update({"記録日": day, "利用者名": name, "user_id": user_id, "体温": temperature})
        return row

    def rows(self):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                'SELECT "record_key", "記録日", "利用者名", "user_id", "体温" '
                'FROM health_records ORDER BY "record_key"'
            ).fetchall()

    def test_new_update_and_unrelated_rows_are_preserved(self):
        records = [
            (self.record("2026-07-20", "同姓 太郎", "u-1", "36.5"), "2026-07-20__u-1"),
            (self.record("2026-07-20", "同姓 太郎", "u-2", "37.0"), "2026-07-20__u-2"),
            (self.record("2026-07-21", "同姓 太郎", "u-1", "36.7"), "2026-07-21__u-1"),
        ]
        for row, key in records:
            self.assertTrue(database.upsert_sqlite_health_record(row, key, "health_records", HEALTH_COLUMNS, ["記録日"]))

        updated = self.record("2026-07-20", "同姓 太郎", "u-1", "38.1")
        database.upsert_sqlite_health_record(updated, "2026-07-20__u-1", "health_records", HEALTH_COLUMNS, ["記録日"])

        rows = self.rows()
        self.assertEqual(len(rows), 3)
        self.assertIn(("2026-07-20__u-1", "2026-07-20", "同姓 太郎", "u-1", "38.1"), rows)
        self.assertIn(("2026-07-20__u-2", "2026-07-20", "同姓 太郎", "u-2", "37.0"), rows)
        self.assertIn(("2026-07-21__u-1", "2026-07-21", "同姓 太郎", "u-1", "36.7"), rows)

    def test_legacy_date_and_missing_user_id_are_updated_without_duplication(self):
        columns_sql = ", ".join(f'"{column}" TEXT' for column in HEALTH_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"CREATE TABLE health_records ({columns_sql})")
            conn.execute(
                'INSERT INTO health_records ("記録日", "利用者名", "user_id", "体温") VALUES (?, ?, ?, ?)',
                ("2026/07/20", "山田 花子様", "", "36.4"),
            )

        candidates = ["2026-07-20__user-9", "2026-07-20__山田花子"]
        resolved = database.find_sqlite_health_record_key(
            "health_records", HEALTH_COLUMNS, candidates, "2026-07-20", "user-9", "山田花子"
        )
        self.assertEqual(resolved, candidates[-1])
        database.upsert_sqlite_health_record(
            self.record("2026-07-20", "山田花子", "user-9", "37.2"),
            resolved,
            "health_records",
            HEALTH_COLUMNS,
            ["記録日"],
            candidates,
        )
        rows = self.rows()
        self.assertEqual(rows, [(resolved, "2026-07-20", "山田花子", "user-9", "37.2")])

    def test_existing_row_with_user_id_uses_current_key(self):
        columns_sql = ", ".join(f'"{column}" TEXT' for column in HEALTH_COLUMNS)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"CREATE TABLE health_records ({columns_sql})")
            conn.execute(
                'INSERT INTO health_records ("記録日", "利用者名", "user_id", "体温") VALUES (?, ?, ?, ?)',
                ("2026-07-20", "山田花子", "user-9", "36.4"),
            )
        candidates = ["2026-07-20__user-9", "2026-07-20__山田花子"]
        resolved = database.find_sqlite_health_record_key(
            "health_records", HEALTH_COLUMNS, candidates, "2026-07-20", "user-9", "山田花子"
        )
        self.assertEqual(resolved, candidates[0])

    def test_sqlite_single_upsert_source_has_no_delete(self):
        source = APP_PATH.parent.joinpath("db", "database.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upsert_sqlite_health_record")
        function_source = ast.get_source_segment(source, node)
        self.assertIn('ON CONFLICT("record_key") DO UPDATE', function_source)
        self.assertNotIn("DELETE FROM", function_source.upper())


class HealthRecordSaveFlowTests(unittest.TestCase):
    def _namespace(self, db_engine, supabase_enabled=True, supabase_key="", supabase_save=True):
        calls = {"cache": 0, "audit": 0, "supabase_save": 0}

        def clean_text(value, default=""):
            text = str(value or "").strip()
            return text if text else default

        globals_dict = {
            "HEALTH_COLUMNS": HEALTH_COLUMNS,
            "SQLITE_TABLE_HEALTH": "health_records",
            "db_engine": db_engine,
            "ensure_user_id_value": lambda uid, name: uid or f"id-{name}",
            "_health_record_key_candidates": lambda record: [f"2026-07-20__{record['user_id']}", f"2026-07-20__{record['利用者名']}"],
            "supabase_is_enabled": lambda: supabase_enabled,
            "_find_supabase_health_record_key": lambda keys: supabase_key,
            "_upsert_supabase_health_record": lambda record, key: calls.__setitem__("supabase_save", calls["supabase_save"] + 1) or supabase_save,
            "clear_health_record_read_cache": lambda: calls.__setitem__("cache", calls["cache"] + 1),
            "add_audit_log": lambda *args: calls.__setitem__("audit", calls["audit"] + 1),
            "make_date_user_key": lambda day, name: f"{day}__{name}",
            "_mark_sqlite_backup_error": lambda *args: None,
            "_show_sqlite_backup_warning_once": lambda *args: None,
            "st": SimpleNamespace(session_state={}, error=lambda *args: None),
            "clean_text": clean_text,
        }
        namespace = _app_functions("upsert_health_record", globals_dict=globals_dict)
        return namespace, calls

    @staticmethod
    def record():
        return {"記録日": "2026-07-20", "利用者名": "山田花子", "体温": 36.5}

    def test_new_save_uses_one_record_without_full_history_load(self):
        db_engine = mock.Mock()
        db_engine.find_sqlite_health_record_key.return_value = None
        db_engine.upsert_sqlite_health_record.return_value = True
        namespace, calls = self._namespace(db_engine)
        self.assertEqual(namespace["upsert_health_record"](self.record()), "登録")
        saved_record = db_engine.upsert_sqlite_health_record.call_args.args[0]
        self.assertIsInstance(saved_record, dict)
        self.assertEqual(saved_record["user_id"], "id-山田花子")
        self.assertEqual(calls["supabase_save"], 1)
        self.assertEqual(calls["cache"], 1)
        self.assertNotIn("load_health_data", namespace)

    def test_existing_record_key_is_reported_as_update(self):
        db_engine = mock.Mock()
        db_engine.find_sqlite_health_record_key.return_value = None
        namespace, _ = self._namespace(db_engine, supabase_key="2026-07-20__id-山田花子")
        self.assertEqual(namespace["upsert_health_record"](self.record()), "更新")
        self.assertEqual(db_engine.upsert_sqlite_health_record.call_args.args[1], "2026-07-20__id-山田花子")

    def test_supabase_failure_does_not_write_sqlite_or_clear_cache(self):
        db_engine = mock.Mock()
        db_engine.find_sqlite_health_record_key.return_value = None
        namespace, calls = self._namespace(db_engine, supabase_save=False)
        self.assertEqual(namespace["upsert_health_record"](self.record()), "")
        db_engine.upsert_sqlite_health_record.assert_not_called()
        self.assertEqual(calls["cache"], 0)
        self.assertEqual(calls["audit"], 0)

    def test_sqlite_failure_after_supabase_success_keeps_primary_success(self):
        db_engine = mock.Mock()
        db_engine.find_sqlite_health_record_key.return_value = None
        db_engine.upsert_sqlite_health_record.side_effect = sqlite3.OperationalError("locked")
        namespace, calls = self._namespace(db_engine)
        self.assertEqual(namespace["upsert_health_record"](self.record()), "登録")
        self.assertEqual(calls["supabase_save"], 1)
        self.assertEqual(calls["cache"], 1)

    def test_sqlite_only_failure_is_not_success(self):
        db_engine = mock.Mock()
        db_engine.find_sqlite_health_record_key.return_value = None
        db_engine.upsert_sqlite_health_record.side_effect = sqlite3.OperationalError("locked")
        namespace, calls = self._namespace(db_engine, supabase_enabled=False)
        self.assertEqual(namespace["upsert_health_record"](self.record()), "")
        self.assertEqual(calls["cache"], 0)


class SupabaseAndCacheTests(unittest.TestCase):
    def test_supabase_payload_contains_exactly_one_row(self):
        response = mock.Mock()
        requests = mock.Mock()
        requests.post.return_value = response
        namespace = _app_functions(
            "_upsert_supabase_health_record",
            globals_dict={
                "HEALTH_COLUMNS": HEALTH_COLUMNS,
                "SQLITE_TABLE_HEALTH": "health_records",
                "_sb_json_safe": lambda value: value,
                "format_now_jst": lambda fmt: "2026-07-20T12:00:00+09:00",
                "requests": requests,
                "_supabase_endpoint": lambda table, query="": table + query,
                "_supabase_headers": lambda prefer="": {"Prefer": prefer},
                "st": SimpleNamespace(error=lambda *args: None),
            },
        )
        self.assertTrue(namespace["_upsert_supabase_health_record"]({"記録日": "2026-07-20"}, "key-1"))
        payload = requests.post.call_args.kwargs["json"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["record_key"], "key-1")

    def test_cache_clear_targets_health_only(self):
        captured = []
        namespace = _app_functions(
            "clear_health_record_read_cache",
            globals_dict={"_clear_cached_functions": lambda names: captured.extend(names)},
        )
        namespace["clear_health_record_read_cache"]()
        self.assertEqual(captured, ["_supabase_read_health_records_cached"])

    def test_generic_health_cache_clear_does_not_clear_other_tables(self):
        captured = []
        namespace = _app_functions(
            "clear_hidamari_read_cache",
            globals_dict={
                "_clear_cached_functions": lambda names: captured.extend(names) or list(names),
                "st": SimpleNamespace(cache_data=SimpleNamespace(clear=lambda: self.fail("global cache cleared"))),
            },
        )
        namespace["clear_hidamari_read_cache"]("健康チェック保存")
        self.assertEqual(captured, ["_supabase_read_health_records_cached"])

    def test_health_input_and_admin_edit_still_use_same_save_entrypoint(self):
        source = APP_PATH.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("action = upsert_health_record(record)"), 2)
        self.assertIn('elif menu == "健康チェック入力":', source)
        self.assertIn('st.subheader("健康チェックデータ")', source)


if __name__ == "__main__":
    unittest.main()
