-- Supabase SQL Editorで実行してください
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
