# ひだまり健康チェック管理システム

Streamlitで動作する、介護・福祉施設向けの健康チェック、排泄チェック、申し送り、短期目標・モニタリング、LIFE関連支援、バックアップ管理をまとめた業務アプリです。

このリポジトリは、Supabaseを主保存先として使い、SQLiteをローカルバックアップとして併用する構成です。

## 主な機能

- 利用者マスタ管理
- 健康チェック記録
- 排泄チェック記録
- 業務申し送り
- 短期目標・モニタリング
- LIFE入力支援
- AIによる記録整理・分析支援
- PDF、Excel、CSV出力
- SQLiteバックアップ、復元、整合性確認
- Supabase接続診断
- ログイン・職員ID管理
- 監査ログ、バックアップ履歴

## データ保存方針

### Supabase

主な業務データはSupabase側へupsert保存します。

対象テーブル例:

- `users`
- `health_records`
- `excretion_records`
- `handover_logs`
- `short_goal_checks`
- `short_term_goals`
- `monitoring_drafts`

### SQLite

SQLiteはローカルバックアップ、復旧補助、Supabase未設定時の保存先として利用します。

主な用途:

- 起動時の補助データ読み込み
- ローカルバックアップ
- 復元処理
- 監査ログ
- アプリ設定
- ログイン履歴

## Streamlit Secrets設定例

```toml
[supabase]
enabled = true
url = "https://YOUR_PROJECT_REF.supabase.co"
key = "sb_publishable_xxxxxxxxxxxxxxxxx"

[openai]
api_key = "sk-xxxxxxxxxxxxxxxx"
model = "gpt-4o-mini"
model_vision = "gpt-4o-mini"
model_admin = "gpt-4.1-mini"
```

従来形式の `SUPABASE_URL`、`SUPABASE_KEY`、`OPENAI_API_KEY` にも対応しています。

## Supabaseテーブル作成

Supabase SQL Editorで以下のSQLを実行します。

- `sql/supabase_ver45_tables.sql`

すでに主要テーブルを作成済みで、ロール共通メニュー設定だけを追加する場合は、次のSQLを実行します。

- `sql/menu_role_settings.sql`

古い3テーブル構成のみが必要な場合は、参考として以下も残しています。

- `sql/supabase_tables.sql`

## 起動方法

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## 最小チェック

構文チェックと依存ライブラリのインポート確認を行う場合:

```powershell
python tools/minimal_check.py
```

確認内容:

- `app.py` の構文チェック
- `db/database.py` の構文チェック
- `requirements.txt` に記載された主要ライブラリのインポート確認

## 運用メモ

- 初期アカウントを利用する場合は、初回ログイン後に必ずパスワードを変更してください。
- バックアップ復元前には、アプリ側で復元前バックアップが作成されます。
- Supabase設定が有効な場合でも、SQLiteバックアップは復旧補助として残します。
- AI機能はOpenAI APIキーが未設定でも、ルールベース機能のみで利用できます。
- 写真や添付ファイルを含むバックアップはサイズが大きくなることがあります。
- 現場で使い始める前に、`docs/pre_operation_checklist.md` の実運用前チェックリストを確認してください。
