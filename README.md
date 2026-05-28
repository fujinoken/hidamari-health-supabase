# hidamari-health-supabase

ひだまり健康チェック管理システム Ver4.5 Supabase対応版です。

## 方針

主要3機能だけをSupabase外部DBに保存します。

- 健康チェック: `health_records`
- 排泄チェック: `excretion_records`
- 業務全体申し送り: `handover_logs`

その他の機能は従来どおりSQLiteを補助保存・バックアップ用途として残します。

## GitHubへ入れるファイル

このフォルダ内をそのまま新リポジトリ `hidamari-health-supabase` にアップロードしてください。

```text
app.py
db/
requirements.txt
sql/supabase_tables.sql
.streamlit/secrets.example.toml
.gitignore
README.md
```

## Supabase側の準備

1. Supabaseで新規プロジェクト作成
2. SQL Editorを開く
3. `sql/supabase_tables.sql` の内容を実行
4. Streamlit Cloud の Secrets に以下を設定

```toml
[supabase]
enabled = true
url = "https://xxxxxxxxxxxxxxxxxxxx.supabase.co"
key = "YOUR_SUPABASE_SERVICE_ROLE_OR_ANON_KEY"
```

## Streamlit Cloud設定

- Main file path: `app.py`
- Python version: 標準で可
- Secrets: `.streamlit/secrets.example.toml` を参考に入力

## 注意

`data/` 内のSQLite DBはGitHubに上げないでください。Streamlit Cloudではローカル保存は永続化されないため、主要3機能はSupabaseを正本にします。
