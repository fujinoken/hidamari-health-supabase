import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from hidamari.dashboard_settings import (
    SQLiteDashboardSettingsStore,
    decode_dashboard_settings,
    normalize_dashboard_items,
    normalize_dashboard_user_id,
)


ITEMS = ["申し送り", "注意利用者", "LIFE"]
DEFAULTS = ["申し送り", "注意利用者"]


class DashboardSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "hidamari_health.db"
        self.store = SQLiteDashboardSettingsStore(self.db_path, ITEMS, DEFAULTS)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_users_are_isolated_and_upsert_does_not_duplicate(self):
        self.store.upsert("Admin-A", ["申し送り"])
        self.store.upsert("admin-b", ["LIFE"])
        self.store.upsert("admin-a", ["注意利用者"])
        self.assertEqual(self.store.load("ADMIN-A"), ["注意利用者"])
        self.assertEqual(self.store.load("admin-b"), ["LIFE"])
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT count(*) FROM dashboard_user_settings").fetchone()[0]
        self.assertEqual(count, 2)

    def test_relogin_and_restart_restore_from_same_database(self):
        self.store.upsert("admin-a", ["LIFE", "申し送り"])
        restarted_store = SQLiteDashboardSettingsStore(self.db_path, ITEMS, DEFAULTS)
        self.assertEqual(restarted_store.load("admin-a"), ["LIFE", "申し送り"])

    def test_unsaved_user_uses_standard_setting(self):
        self.assertIsNone(self.store.load("new-user"))
        self.assertEqual(normalize_dashboard_items(None, ITEMS, DEFAULTS), DEFAULTS)

    def test_reset_to_standard_is_immediate_and_persistent(self):
        self.store.upsert("admin-a", ["LIFE"])
        self.store.upsert("admin-a", DEFAULTS)
        self.assertEqual(self.store.load("admin-a"), DEFAULTS)

    def test_invalid_and_retired_values_do_not_break_loading(self):
        self.assertEqual(decode_dashboard_settings("not json", ITEMS, DEFAULTS), DEFAULTS)
        payload = json.dumps({"schema_version": 1, "enabled_items": ["LIFE", "廃止項目", "LIFE", 123]})
        self.assertEqual(decode_dashboard_settings(payload, ITEMS, DEFAULTS), ["LIFE"])
        self.assertEqual(normalize_dashboard_user_id(" Admin-A "), "admin-a")

    def test_empty_selection_is_preserved(self):
        self.store.upsert("admin-a", [])
        self.assertEqual(self.store.load("admin-a"), [])


if __name__ == "__main__":
    unittest.main()
