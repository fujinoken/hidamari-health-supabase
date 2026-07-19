-- 自分専用ダッシュボード設定（Supabase SQL Editorで実行）
-- 既存テーブルと同じ public / snake_case 規則を使用する。
create table if not exists public.dashboard_user_settings (
  user_id text primary key,
  settings_json jsonb not null default '{"schema_version":1,"enabled_items":[]}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.dashboard_user_settings is 'ログイン利用者ごとの自分専用ダッシュボード表示設定';
comment on column public.dashboard_user_settings.user_id is 'login_accounts.ログインID（小文字正規化済み）';
