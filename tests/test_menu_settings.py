import json
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from hidamari.config.menu import MENU_GROUPS_ADMIN, MENU_GROUPS_STAFF, canonical_menu_key
from hidamari.menu_settings import (
    SQLiteMenuRoleSettingsStore,
    decode_menu_settings,
    get_legacy_role_rows,
    menu_settings_cache_key,
    normalize_menu_scope,
    normalize_menu_setting_rows,
)


ADMIN_STANDARD = [
    {"menu_key": "dashboard", "visible": True, "category": "日常管理", "sort_order": 10, "note": "標準"},
    {"menu_key": "menu_settings", "visible": True, "category": "システム管理", "sort_order": 20, "note": "復旧用"},
    {"menu_key": "system_settings", "visible": True, "category": "システム管理", "sort_order": 30, "note": "復旧用"},
]
STAFF_STANDARD = [
    {"menu_key": "health_input", "visible": True, "category": "今日の入力", "sort_order": 10, "note": "職員"},
]
REQUIRED_ADMIN = ("menu_settings", "system_settings")


class MenuSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "hidamari_health.db"
        self.store = SQLiteMenuRoleSettingsStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_setting_saved_by_admin_a_is_shared_with_admin_b(self):
        self.store.upsert("admin", "Admin-A", [{"menu_key": "dashboard", "category": "管理者共通"}], ADMIN_STANDARD, REQUIRED_ADMIN)
        admin_b_view = self.store.load("admin", ADMIN_STANDARD, REQUIRED_ADMIN)
        self.assertEqual(admin_b_view[0]["category"], "管理者共通")

    def test_staff_setting_saved_by_admin_a_is_shared_with_staff_b(self):
        self.store.upsert("staff", "Admin-A", [{"menu_key": "health_input", "visible": False}], STAFF_STANDARD)
        staff_b_view = self.store.load("staff", STAFF_STANDARD)
        self.assertFalse(staff_b_view[0]["visible"])

    def test_scopes_are_isolated_and_upsert_does_not_duplicate(self):
        self.store.upsert("admin", "admin-a", [{"menu_key": "dashboard", "category": "初回"}], ADMIN_STANDARD, REQUIRED_ADMIN)
        self.store.upsert("staff", "admin-a", [{"menu_key": "health_input", "visible": False}], STAFF_STANDARD)
        self.store.upsert("admin", "admin-b", [{"menu_key": "dashboard", "category": "更新後"}], ADMIN_STANDARD, REQUIRED_ADMIN)

        self.assertEqual(self.store.load("admin", ADMIN_STANDARD, REQUIRED_ADMIN)[0]["category"], "更新後")
        self.assertFalse(self.store.load("staff", STAFF_STANDARD)[0]["visible"])
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("SELECT count(*) FROM menu_role_settings").fetchone()[0]
        self.assertEqual(count, 2)

    def test_updated_by_and_updated_at_change_on_resave(self):
        self.store.upsert("admin", "Admin-A", ADMIN_STANDARD, ADMIN_STANDARD, REQUIRED_ADMIN)
        with closing(sqlite3.connect(self.db_path)) as conn:
            first = conn.execute(
                "SELECT updated_by, updated_at FROM menu_role_settings WHERE menu_scope = 'admin'"
            ).fetchone()
        time.sleep(0.002)
        self.store.upsert("admin", "Admin-B", [{"menu_key": "dashboard", "category": "更新"}], ADMIN_STANDARD, REQUIRED_ADMIN)
        with closing(sqlite3.connect(self.db_path)) as conn:
            second = conn.execute(
                "SELECT updated_by, updated_at FROM menu_role_settings WHERE menu_scope = 'admin'"
            ).fetchone()
        self.assertEqual(first[0], "admin-a")
        self.assertEqual(second[0], "admin-b")
        self.assertNotEqual(first[1], second[1])

    def test_restart_restores_role_setting(self):
        rows = [{"menu_key": "dashboard", "visible": False, "category": "朝", "sort_order": 88, "note": "共通"}]
        self.store.upsert("admin", "admin-a", rows, ADMIN_STANDARD, REQUIRED_ADMIN)
        restarted = SQLiteMenuRoleSettingsStore(self.db_path)
        restored = restarted.load("admin", ADMIN_STANDARD, REQUIRED_ADMIN)
        dashboard = next(row for row in restored if row["menu_key"] == "dashboard")
        self.assertEqual((dashboard["visible"], dashboard["category"], dashboard["sort_order"], dashboard["note"]), (False, "朝", 88.0, "共通"))

    def test_unsaved_scope_has_no_row_and_standard_is_safe(self):
        self.assertIsNone(self.store.load("admin", ADMIN_STANDARD, REQUIRED_ADMIN))
        self.assertEqual(normalize_menu_setting_rows(None, ADMIN_STANDARD, REQUIRED_ADMIN), ADMIN_STANDARD)

    def test_reset_to_standard_is_shared_and_persistent(self):
        self.store.upsert("staff", "admin-a", [{"menu_key": "health_input", "visible": False}], STAFF_STANDARD)
        self.store.upsert("staff", "admin-b", STAFF_STANDARD, STAFF_STANDARD)
        self.assertEqual(self.store.load("staff", STAFF_STANDARD), STAFF_STANDARD)

    def test_legacy_common_settings_are_selected_by_scope(self):
        legacy = {
            "admin": [{"メニュー": "dashboard", "表示": False}],
            "staff": [{"メニュー": "health_input", "カテゴリ": "職員共通"}],
        }
        self.assertEqual(get_legacy_role_rows(legacy, "admin"), legacy["admin"])
        self.assertEqual(get_legacy_role_rows(legacy, "staff"), legacy["staff"])
        self.assertEqual(get_legacy_role_rows({"admin": "broken"}, "admin"), [])

    def test_new_menu_is_supplemented_from_standard(self):
        old_rows = ADMIN_STANDARD[:2]
        saved = normalize_menu_setting_rows(old_rows, ADMIN_STANDARD, REQUIRED_ADMIN)
        self.assertEqual({row["menu_key"] for row in saved}, {"dashboard", "menu_settings", "system_settings"})

    def test_retired_invalid_duplicate_and_bad_order_are_safe(self):
        payload = json.dumps({"rows": [
            {"menu_key": "retired", "visible": True},
            {"menu_key": "dashboard", "category": "最初", "sort_order": 5},
            {"menu_key": "dashboard", "category": "", "sort_order": "not-number"},
        ]})
        rows = decode_menu_settings(payload, ADMIN_STANDARD, REQUIRED_ADMIN)
        dashboard = next(row for row in rows if row["menu_key"] == "dashboard")
        self.assertEqual(dashboard["category"], "日常管理")
        self.assertEqual(dashboard["sort_order"], 10.0)
        self.assertNotIn("retired", {row["menu_key"] for row in rows})
        self.assertEqual(decode_menu_settings("not-json", ADMIN_STANDARD, REQUIRED_ADMIN), ADMIN_STANDARD)

    def test_recovery_menus_cannot_be_hidden(self):
        rows = normalize_menu_setting_rows([
            {"menu_key": "menu_settings", "visible": False},
            {"menu_key": "system_settings", "visible": False},
        ], ADMIN_STANDARD, REQUIRED_ADMIN)
        for row in rows:
            if row["menu_key"] in REQUIRED_ADMIN:
                self.assertTrue(row["visible"])

    def test_invalid_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_menu_scope("other")

    def test_cache_and_preview_use_only_the_selected_scope(self):
        self.assertEqual(menu_settings_cache_key("admin"), "menu_role_settings::admin")
        self.assertEqual(menu_settings_cache_key("staff"), "menu_role_settings::staff")
        self.assertNotEqual(menu_settings_cache_key("admin"), menu_settings_cache_key("staff"))

        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn("preview_groups = build_menu_groups_from_settings(role_key)", app_source)
        self.assertIn("menu = render_sidebar_menu(st.session_state.role", app_source)
        self.assertIn('def load_menu_category_settings(role="admin", force_reload=False):', app_source)

    def test_staff_cannot_open_settings_and_internal_keys_are_preserved(self):
        admin_menus = {menu for menus in MENU_GROUPS_ADMIN.values() for menu in menus}
        staff_menus = {menu for menus in MENU_GROUPS_STAFF.values() for menu in menus}
        self.assertEqual(canonical_menu_key("メニュー表示設定"), "メニューカテゴリ設定")
        self.assertIn("メニューカテゴリ設定", admin_menus)
        self.assertIn("システム設定", admin_menus)
        self.assertNotIn("メニューカテゴリ設定", staff_menus)

    def test_supabase_sql_creates_seeds_and_grants_role_settings(self):
        repo_root = Path(__file__).resolve().parents[1]
        dedicated_sql = (repo_root / "sql" / "menu_role_settings.sql").read_text(encoding="utf-8").lower()
        primary_sql = (repo_root / "sql" / "supabase_ver45_tables.sql").read_text(encoding="utf-8").lower()
        for sql_source in (dedicated_sql, primary_sql):
            self.assertIn("create table if not exists public.menu_role_settings", sql_source)
            self.assertIn("grant select, insert, update on table public.menu_role_settings", sql_source)
            self.assertIn("values ('admin'), ('staff')", sql_source)

    def test_supabase_read_failure_is_logged_and_success_clears_warning(self):
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('"MENU_SETTINGS",\n                "supabase read failed"', app_source)
        self.assertIn('st.session_state.pop(f"menu_supabase_read_warning::{menu_scope}", None)', app_source)
        self.assertIn('"項目": MENU_SETTINGS_TABLE', app_source)


if __name__ == "__main__":
    unittest.main()
