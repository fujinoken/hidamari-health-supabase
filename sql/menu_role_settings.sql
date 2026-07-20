-- 管理者・職員それぞれのロール共通メニュー設定（Supabase SQL Editorで実行）
create table if not exists public.menu_role_settings (
  menu_scope text primary key
    check (menu_scope in ('admin', 'staff')),
  settings_json jsonb not null
    default '{"schema_version":1,"rows":[]}'::jsonb,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.menu_role_settings is '管理者・職員それぞれのロール共通メニュー表示設定';
comment on column public.menu_role_settings.menu_scope is 'admin または staff（各1行）';
comment on column public.menu_role_settings.updated_by is '最後に保存した管理者の正規化ログインID';

-- publishable/anon key と Supabase Auth のどちらでもREST APIから読み書きできるよう明示する。
grant usage on schema public to anon, authenticated;
grant select, insert, update on table public.menu_role_settings to anon, authenticated, service_role;

-- 未保存のロールもDBから正常に読めるよう、安全な標準値を表す行を用意する。
-- rows=[] はアプリ側で現在の標準メニュー一式に補完される。
insert into public.menu_role_settings (menu_scope)
values ('admin'), ('staff')
on conflict (menu_scope) do nothing;
