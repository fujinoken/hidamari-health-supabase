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
# ログインユーザー管理をSupabase/PostgreSQLへ移行

## 変更ファイルと理由

- `hidamari/auth/app_users.py`: `app_users` テーブルでログインユーザー、パスワードハッシュ、初回変更フラグ、失敗回数、ロック期限、最終ログイン日時を管理します。
- `app.py`: 既存のログイン画面・初回パスワード変更画面・ログインID管理画面のUIを維持し、裏側の認証関数だけDB版へ差し替えました。
- `hidamari/auth/password.py`: 新規保存・変更時のパスワード保存をbcrypt必須にし、`must_change_password` カラムは保持しつつ現在はログイン制御には使わない形にしています。
- `requirements.txt`: PostgreSQLへ直接接続するため `psycopg2-binary` を追加しました。
- `sql/app_users_auth.sql`: Supabase SQL Editorで実行できる認証テーブル作成SQLです。

## 必要なSecrets

推奨はPostgreSQL直接接続です。Streamlit secrets または `.streamlit/secrets.toml` に次のいずれかを設定します。

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_DB_PASSWORD@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
```

既存のSupabase REST設定を使う場合は、`app_users` がパスワードハッシュを含むため、公開用キーではなくサーバー側だけで使う service role key を設定してください。

```toml
[supabase]
enabled = true
url = "https://YOUR_PROJECT_REF.supabase.co"
service_role_key = "YOUR_SERVICE_ROLE_KEY"
```

本番パスワード、DB接続文字列、service role key はGitHubへコミットしないでください。

## 初期テーブル作成

Supabase SQL Editorで `sql/app_users_auth.sql` を実行します。アプリ起動時に `app_users` が空の場合、初期ユーザーを自動作成します。

- `kanri` / 初期パスワードは `HIDAMARI_INITIAL_PASSWORD`、未設定時は既存どおり `rui`
- `staff` / 初期パスワードは `HIDAMARI_INITIAL_PASSWORD`、未設定時は既存どおり `rui`
- `must_change_password` カラムは残りますが、現在はログイン制御には使いません。

初期パスワードを変更したい場合は、Streamlit secrets または環境変数に次を設定します。

```toml
HIDAMARI_INITIAL_PASSWORD = "初回配布用の一時パスワード"
```

## 初期ユーザー作成手順

1. `sql/app_users_auth.sql` をSupabase SQL Editorで実行します。
2. `DATABASE_URL` または `[supabase].service_role_key` をStreamlit secretsに設定します。
3. `pip install -r requirements.txt` を実行します。
4. `streamlit run app.py` で起動します。
5. `kanri` と初期パスワードでログインします。
6. 初回パスワード変更画面は表示されず、そのまま通常画面へ進みます。
7. 管理画面の「ログイン・職員ID管理」から必要な職員IDを追加します。

## 改修後の確認項目

- 初期パスワードでログインできる。
- ログイン成功後、初回パスワード変更画面ではなく通常画面へ進む。
- `must_change_password = true` のユーザーでも、正しいID・パスワードならログインできる。
- ログイン成功時に、可能な範囲で `must_change_password` が `false` に戻る。
- アプリを再起動してもDB認証でログインできる。
- 5回失敗すると `failed_login_count` が5になり、`locked_until` に現在時刻+300秒が保存される。
- ロック中はログインできない。
- ロック解除後に正しいパスワードでログインでき、成功時に `failed_login_count = 0`、`locked_until = null` へ戻る。

健康記録・申し送り・利用者データの既存テーブルは変更していません。
# 認証DB設定とエラー表示

ログイン認証は `app_users` テーブルを使います。認証用DB接続情報が未設定、接続不可、または `app_users` テーブル未作成の場合、ログイン画面には管理者向けの短い案内だけを表示し、利用者画面には traceback や内部ファイルパスを表示しません。

## 初回パスワード変更強制の扱い

現在の運用では、`app_users` テーブルによるDB認証と `role` による管理者・職員区分は維持しつつ、初回パスワード変更画面の強制表示は無効化しています。

- `app_users.role` に `admin` / `staff` などを設定することで、管理者・職員の区分を行います。
- 初期ユーザーを作成する場合は、平文パスワードではなく `password_hash` を設定してください。
- `must_change_password` カラムは残していますが、現在はログイン制御には使いません。
- 既存データで `must_change_password = true` が残っていても、正しいID・パスワードでログインできれば通常画面へ進みます。
- ログイン成功時には、可能な範囲で `must_change_password` を `false` に戻します。

## Supabase SQL Editorでの手順

1. Supabase Dashboard を開きます。
2. 対象プロジェクトの SQL Editor を開きます。
3. `sql/app_users_auth.sql` の内容を貼り付けて実行します。
4. `public.app_users` が作成されたことを Table Editor で確認します。

## Streamlit Cloud Secretsの設定

Streamlit Cloud のアプリ設定から `Secrets` を開き、PostgreSQL接続文字列を設定します。値はプロジェクトごとの実値に置き換えてください。

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_DB_PASSWORD@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
```

`service_role_key` を使う場合は、公開用の anon/publishable key ではなく service role key をサーバー側のSecretsにだけ保存します。

```toml
[supabase]
enabled = true
url = "https://YOUR_PROJECT_REF.supabase.co"
service_role_key = "YOUR_SERVICE_ROLE_KEY"
```

`DATABASE_URL` や `service_role_key` は絶対にGitHubへコミットしないでください。READMEやコードには実値を書かず、Streamlit Cloud Secrets またはローカルの `.streamlit/secrets.toml` だけに保存します。

Secretsを保存した後は、Streamlit Cloudで `Reboot app` または `Rerun` を実行してください。再起動前は古いSecretsのまま動くことがあります。

## 認証まわりの確認項目

- Secrets未設定時に赤いtracebackではなく、認証用DB接続情報の案内が出る。
- `app_users` テーブル未作成時に、`sql/app_users_auth.sql` 実行案内が出る。
- `DATABASE_URL` 設定後にログイン画面が正常に動く。
- 正しいID・パスワードでログイン後、初回パスワード変更画面ではなく通常画面へ進む。
- `must_change_password = true` の既存ユーザーでもログインを妨げない。
- ログイン成功時に `failed_login_count` と `locked_until` がリセットされる。
- 5回失敗でロックされる。
