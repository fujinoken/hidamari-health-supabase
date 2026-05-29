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
