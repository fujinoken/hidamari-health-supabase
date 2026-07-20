-- ひだまり健康チェック管理システム Ver4.5 Supabase 4テーブル
-- SQL Editorで実行してください

create table if not exists public.users (
  record_key text primary key,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.health_records (
  record_key text primary key,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.excretion_records (
  record_key text primary key,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

create table if not exists public.handover_logs (
  record_key text primary key,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

-- 管理者・職員それぞれのロール共通メニュー設定
create table if not exists public.menu_role_settings (
  menu_scope text primary key
    check (menu_scope in ('admin', 'staff')),
  settings_json jsonb not null
    default '{"schema_version":1,"rows":[]}'::jsonb,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

grant usage on schema public to anon, authenticated;
grant select, insert, update on table public.menu_role_settings to anon, authenticated, service_role;

insert into public.menu_role_settings (menu_scope)
values ('admin'), ('staff')
on conflict (menu_scope) do nothing;
