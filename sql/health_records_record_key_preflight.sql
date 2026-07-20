-- Supabase SQL Editorで実行する健康記録UPSERTの事前確認SQLです。
-- このファイルはアプリから自動実行しません。

-- 1. record_key の主キー・一意制約を確認
select
  c.conname as constraint_name,
  c.contype as constraint_type,
  pg_get_constraintdef(c.oid) as definition
from pg_constraint c
join pg_class t on t.oid = c.conrelid
join pg_namespace n on n.oid = t.relnamespace
where n.nspname = 'public'
  and t.relname = 'health_records'
  and c.contype in ('p', 'u');

-- 2. 追加前に必ず重複を確認（0行であること）
select record_key, count(*) as duplicate_count
from public.health_records
group by record_key
having count(*) > 1;

-- 3. NULL・空キーを確認（主キーなら0件のはず）
select count(*) as missing_record_key_count
from public.health_records
where record_key is null or btrim(record_key) = '';

-- 上記2・3がともに0件で、1に record_key の主キーまたは一意制約がない場合だけ、
-- 次のSQLを別途実行してください。制約名が既に使われていないことも確認してください。
-- alter table public.health_records
--   add constraint health_records_record_key_key unique (record_key);
