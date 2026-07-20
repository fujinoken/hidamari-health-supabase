MENU_GROUPS_ADMIN = {
    "日常管理": [
        "管理者ダッシュボード",
        "記録確認・修正統合",
        "業務全体申し送り",
        "利用者マスタ管理",
        "ログイン・職員ID管理",
        "過去データ管理",
        "排泄詳細管理",
        "未入力・注意記録",
        "現場の気づき構造化・AI管理者支援",
        "AI管理者アシスタント",
        "自分専用ダッシュボード",
    ],
    "日々の記録": [
        "日々のまとめ入力",
        "健康チェック入力",
        "排泄チェック入力",
        "日々の実施チェック",
        "写真から半自動入力",
    ],
    "マスタ・運用設定": [
        "短期目標・モニタリング",
        "短期目標マスタ",
        "実施履歴一覧",
        "短期目標データ管理",
        "LIFE入力標準化",
        "管理者LIFE入力",
        "LIFE不足チェック",
        "LIFE CSV出力",
        "LIFE登録一覧",
        "加算シミュレーション",
        "管理者支援",
        "システム設定",
        "自分専用ダッシュボード設定",
    ],
    "データ管理": [
        "家族向けレポート作成",
        "ひだまりレポートPDF",
        "データダウンロード",
        "バックアップ管理",
        "監査ログ",
    ],
    "システム管理": [
        "セキュリティ・保守管理",
        "利用者ID移行チェック",
        "利用者名ゆれ紐づけマスタ",
        "メニューカテゴリ設定",
    ],
}

MENU_GROUPS_STAFF = {
    "今日の入力": [
        "業務全体申し送り",
        "日々のまとめ入力",
        "健康チェック入力",
        "排泄チェック入力",
        "記録の確認",
        "日々の実施チェック",
    ]
}

MENU_CATEGORY_LABELS = {
    "日常管理": "日常管理",
    "日々の記録": "日々の記録",
    "マスタ・運用設定": "マスタ・運用設定",
    "データ管理": "データ管理",
    "システム管理": "システム管理",
    "今日の入力": "今日の入力",
    # 保存済みの旧カテゴリを表示する場合の互換ラベル
    "朝の確認": "日常管理",
    "日々の入力": "日々の記録",
    "記録確認": "日常管理",
    "短期目標・LIFE": "マスタ・運用設定",
    "帳票・共有": "データ管理",
    "設定・保守": "システム管理",
}

MENU_DISPLAY_LABELS = {
    "自分専用ダッシュボード": "自分用ダッシュボード",
    "管理者ダッシュボード": "管理者ダッシュボード",
    "記録確認・修正統合": "記録確認・修正",
    "業務全体申し送り": "申し送りを書く・確認する",
    "管理者支援": "申し送り・注意情報の抽出条件",
    "日々のまとめ入力": "日々のまとめ入力",
    "健康チェック入力": "健康チェックを書く",
    "写真から半自動入力": "写真から入力補助",
    "排泄チェック入力": "排泄チェックを書く",
    "記録の確認": "記録の確認",
    "日々の実施チェック": "短期目標の実施チェック",
    "過去データ管理": "健康記録の確認・修正",
    "排泄詳細管理": "排泄記録の確認・修正",
    "未入力・注意記録": "未入力・注意記録",
    "実施履歴一覧": "短期目標の実施履歴",
    "短期目標データ管理": "短期目標データ確認",
    "短期目標・モニタリング": "短期目標・モニタリング",
    "短期目標マスタ": "短期目標の登録・管理",
    "LIFE入力標準化": "LIFE管理",
    "管理者LIFE入力": "LIFE月次入力",
    "LIFE不足チェック": "LIFE不足確認",
    "LIFE CSV出力": "LIFE CSV出力",
    "LIFE登録一覧": "LIFE登録一覧",
    "加算シミュレーション": "加算シミュレーション",
    "家族向けレポート作成": "帳票作成（家族向け）",
    "ひだまりレポートPDF": "帳票作成（PDF）",
    "データダウンロード": "データダウンロード",
    "バックアップ管理": "バックアップ管理",
    "監査ログ": "監査ログ",
    "利用者マスタ管理": "利用者情報の管理",
    "ログイン・職員ID管理": "ログイン・職員ID管理",
    "セキュリティ・保守管理": "セキュリティ・保守",
    "利用者ID移行チェック": "利用者ID移行チェック",
    "利用者名ゆれ紐づけマスタ": "利用者名ゆれの整理",
    "自分専用ダッシュボード設定": "ダッシュボード表示設定",
    "メニューカテゴリ設定": "メニュー表示設定",
    "システム設定": "システム設定",
    "現場の気づき構造化・AI管理者支援": "気づき整理・AI支援",
    "AI管理者アシスタント": "AI管理者レポート",
}


LEGACY_ADMIN_CATEGORIES = {
    "朝の確認",
    "日々の入力",
    "記録確認",
    "短期目標・LIFE",
    "帳票・共有",
    "設定・保守",
}

MENU_KEY_COMPAT_ALIASES = {
    "記録確認・修正": "記録確認・修正統合",
    "健康記録の確認・修正": "過去データ管理",
    "排泄記録の確認・修正": "排泄詳細管理",
    "分析・確認支援": "管理者支援",
    "セキュリティ・保守": "セキュリティ・保守管理",
    "LIFE管理": "LIFE入力標準化",
    "メニュー表示設定": "メニューカテゴリ設定",
    "利用者情報の管理": "利用者マスタ管理",
    "利用者名ゆれの整理": "利用者名ゆれ紐づけマスタ",
}

ADMIN_RECORD_MANAGEMENT_OPTIONS = (
    "健康記録",
    "排泄記録",
    "短期目標の実施記録",
    "申し送り",
    "未入力・注意記録",
)

ADMIN_RECORD_MANAGEMENT_TARGETS = {
    "健康記録": "過去データ管理",
    "排泄記録": "排泄詳細管理",
    "短期目標の実施記録": "実施履歴一覧",
    "申し送り": "業務全体申し送り",
    "未入力・注意記録": "未入力・注意記録",
}


def admin_record_management_target(record_type):
    """共通入口の選択値を、既存画面の内部キーへ解決する。"""
    return ADMIN_RECORD_MANAGEMENT_TARGETS.get(str(record_type or "").strip(), "過去データ管理")


def canonical_menu_key(menu_name):
    """表示名や新名称で保存された値を、既存の内部メニューキーへ戻す。"""
    menu_name = str(menu_name or "").strip()
    if not menu_name:
        return ""
    if menu_name in MENU_KEY_COMPAT_ALIASES:
        return MENU_KEY_COMPAT_ALIASES[menu_name]
    # 過去に表示ラベルがそのまま保存された場合も、重複しないものは復元する。
    reverse_labels = {}
    duplicate_labels = set()
    for key, label in MENU_DISPLAY_LABELS.items():
        if label in reverse_labels:
            duplicate_labels.add(label)
        else:
            reverse_labels[label] = key
    if menu_name in reverse_labels and menu_name not in duplicate_labels:
        return reverse_labels[menu_name]
    return menu_name


def standard_admin_category_for_menu(menu_name):
    menu_name = canonical_menu_key(menu_name)
    for category, menus in MENU_GROUPS_ADMIN.items():
        if menu_name in menus:
            return category
    return ""


def canonical_menu_category(category, menu_name="", role="admin"):
    """旧標準カテゴリだけを新5カテゴリへ移し、独自カテゴリは維持する。"""
    category = str(category or "").strip() or "その他"
    if role != "admin" or category not in LEGACY_ADMIN_CATEGORIES:
        return category
    return standard_admin_category_for_menu(menu_name) or MENU_CATEGORY_LABELS.get(category, category)


def valid_saved_menu_rows(rows):
    """保存設定が行辞書の配列でない場合は、標準設定へ戻せる空配列を返す。"""
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def menu_category_label(category):
    return MENU_CATEGORY_LABELS.get(category, category)


def menu_display_label(menu_name):
    return MENU_DISPLAY_LABELS.get(canonical_menu_key(menu_name), menu_name)
