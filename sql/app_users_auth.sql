-- Authentication table for the Streamlit app.
-- Run this in Supabase SQL Editor before enabling database-backed login.
-- Do not store plaintext passwords in this table.

create table if not exists public.app_users (
  id bigserial primary key,
  login_id text not null unique,
  display_name text not null,
  password_hash text not null,
  role text not null default 'staff',
  must_change_password boolean not null default true,
  failed_login_count integer not null default 0,
  locked_until timestamptz,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_app_users_login_id
  on public.app_users (login_id);

-- Recommended: keep this table private from public/anon clients.
alter table public.app_users enable row level security;

-- The Streamlit server should access this table with DATABASE_URL
-- or a Supabase service role key stored in Streamlit secrets.

