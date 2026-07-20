import ast
import hashlib
import json
import unittest
from pathlib import Path

from hidamari.config.columns import ALERT_CONDITION_COLUMNS
from hidamari.config.menu import (
    MENU_GROUPS_ADMIN,
    MENU_GROUPS_STAFF,
    canonical_menu_key,
    menu_display_label,
    standard_admin_category_for_menu,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "app.py"


class AlertConditionGuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _function_source(self, name):
        node = next(
            item for item in self.tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
        )
        return ast.get_source_segment(self.source, node)

    def _assignment_value(self, name):
        node = next(
            item for item in self.tree.body
            if isinstance(item, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in item.targets)
        )
        return ast.literal_eval(node.value)

    def test_internal_menu_key_is_unchanged_and_admin_only(self):
        admin_menus = [menu for menus in MENU_GROUPS_ADMIN.values() for menu in menus]
        staff_menus = [menu for menus in MENU_GROUPS_STAFF.values() for menu in menus]
        self.assertEqual(admin_menus.count("管理者支援"), 1)
        self.assertNotIn("申し送り・注意情報の抽出条件", admin_menus)
        self.assertNotIn("管理者支援", staff_menus)
        self.assertEqual(canonical_menu_key("申し送り・注意情報の抽出条件"), "管理者支援")
        self.assertEqual(menu_display_label("管理者支援"), "申し送り・注意情報の抽出条件")
        self.assertEqual(standard_admin_category_for_menu("管理者支援"), "マスタ・運用設定")

    def test_condition_storage_and_live_extraction_use_the_same_sqlite_master(self):
        self.assertEqual(self._assignment_value("SQLITE_TABLE_ALERT_CONDITIONS"), "alert_conditions")
        self.assertNotIn("alert_conditions", self._assignment_value("SUPABASE_CORE_TABLES"))
        self.assertIn(
            "load_sqlite_table(SQLITE_TABLE_ALERT_CONDITIONS, ALERT_CONDITION_COLUMNS)",
            self._function_source("load_alert_condition_master"),
        )
        self.assertIn(
            "save_sqlite_table(df, SQLITE_TABLE_ALERT_CONDITIONS, ALERT_CONDITION_COLUMNS",
            self._function_source("save_alert_condition_master"),
        )
        extract_source = self._function_source("build_handover_alerts_by_condition")
        self.assertIn("rules = load_alert_condition_master()", extract_source)
        self.assertIn("check_alert_condition(rule, health_df, ex_df, target_day, user)", extract_source)

    def test_condition_columns_are_unchanged(self):
        self.assertEqual(ALERT_CONDITION_COLUMNS, [
            "条件ID", "使用", "条件名", "重要度", "分類", "条件種別",
            "閾値1", "閾値2", "日数", "キーワード", "表示メッセージ", "並び順",
        ])

    def test_default_conditions_and_decision_logic_are_unchanged(self):
        defaults = self._assignment_value("DEFAULT_ALERT_CONDITIONS")
        defaults_digest = hashlib.sha256(
            json.dumps(defaults, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        decision_digest = hashlib.sha256(
            self._function_source("check_alert_condition").encode()
        ).hexdigest()
        self.assertEqual(len(defaults), 13)
        self.assertEqual(defaults_digest, "7db23dd8732231b51050ea8d04b0e8ec3b92727611a1703a1d6da0673d1a4341")
        self.assertEqual(decision_digest, "54681d087e7ec2162c921b3d8ac8930b1c32213f152c8efcdcebdd41e63c76bf")

    def test_excel_and_screen_results_share_the_live_extraction_function(self):
        auto_source = self._function_source("build_business_handover_auto_extract_text")
        self.assertIn("alert_df = build_handover_alerts_by_condition(target_day)", auto_source)
        self.assertIn('"Excel自動抽出情報": auto_extract_text', self.source)
        self.assertIn("alert_df = build_handover_alerts_by_condition(target_day)", self.source)

    def test_user_facing_wording_and_role_specific_guidance(self):
        self.assertNotIn("条件設定マスタに基づく抽出", self.source)
        self.assertIn("管理者が設定した申し送り・注意情報の抽出条件に基づいて表示しています", self.source)
        guidance = self._function_source("show_alert_condition_guidance")
        self.assertIn("マスタ・運用設定", guidance)
        self.assertIn("この情報の抽出条件は管理者が設定しています。", guidance)
        self.assertIn("if is_admin_user()", guidance)

    def test_save_failure_does_not_report_success(self):
        save_source = self._function_source("save_alert_condition_master")
        screen_source = self._function_source("show_alert_condition_master_menu")
        self.assertIn("return None if saved is False else df", save_source)
        self.assertIn("if saved_df is None:", screen_source)
        self.assertIn("抽出条件を保存できませんでした", screen_source)


if __name__ == "__main__":
    unittest.main()
