import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "app.py"


class AdminSupportLazyLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        start = cls.source.index('elif menu == "管理者支援":')
        end = cls.source.index('\n# =========================\n# 利用者マスタ管理', start)
        cls.section = cls.source[start:end]

    def _function_source(self, name):
        node = next(
            item for item in self.tree.body
            if isinstance(item, ast.FunctionDef) and item.name == name
        )
        return ast.get_source_segment(self.source, node)

    def test_admin_support_uses_single_view_selector_instead_of_tabs(self):
        self.assertIn('key="admin_support_view"', self.section)
        self.assertNotIn("st.tabs(", self.section)
        for view_name in [
            "申し送り・注意情報の抽出条件",
            "AI家族レポート",
            "バイタル推移グラフ",
            "気になる変化",
            "ChatGPT連携",
            "申し送り支援",
            "注意通知",
            "体重未測定確認",
        ]:
            self.assertIn(f'support_view == "{view_name}"', self.section)

    def test_initial_unselected_view_does_not_load_health_or_excretion(self):
        placeholder_start = self.section.index('if support_view == "表示する内容を選んでください":')
        first_view_start = self.section.index('elif support_view == "AI家族レポート":', placeholder_start)
        placeholder_block = self.section[placeholder_start:first_view_start]
        self.assertNotIn("load_health_data", placeholder_block)
        self.assertNotIn("load_excretion_data", placeholder_block)

    def test_admin_support_has_no_unbounded_health_or_excretion_load(self):
        self.assertNotIn("load_health_data()", self.section)
        self.assertNotIn("load_excretion_data()", self.section)
        self.assertIn("load_health_data(start_date=ai_start, end_date=ai_end)", self.section)
        self.assertIn("load_excretion_data(start_date=ai_start, end_date=ai_end)", self.section)
        self.assertIn("load_health_data(start_date=change_start_date, end_date=change_end_date)", self.section)

    def test_alert_extraction_loads_only_required_date_range(self):
        extract_source = self._function_source("build_handover_alerts_by_condition")
        self.assertIn("start_day, end_day = _alert_condition_date_range", extract_source)
        self.assertIn("load_health_data(start_date=start_day, end_date=end_day)", extract_source)
        self.assertIn("load_excretion_data(start_date=start_day, end_date=end_day)", extract_source)

    def test_condition_preview_reuses_loaded_records_and_alert_result(self):
        screen_source = self._function_source("show_alert_condition_master_menu")
        self.assertIn("health_df=preview_health_df", screen_source)
        self.assertIn("ex_df=preview_ex_df", screen_source)
        self.assertIn("alert_df=alert_df", screen_source)


if __name__ == "__main__":
    unittest.main()
