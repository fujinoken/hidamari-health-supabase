# ひだまり健康チェック管理システム Ver4.5 Supabase upsert版

## Supabase正本
- users
- health_records
- excretion_records
- handover_logs

## SQLite補助
- LIFE
- 短期目標
- モニタリング
- AI分析
- 設定
- 監査ログ
- バックアップ履歴

## Streamlit Secrets
```toml
[supabase]
enabled = true
url = "https://huufblmiqvloudecqtjp.supabase.co"
key = "sb_publishable_xxxxxxxxxxxxxxxxx"
```

## 変更点
- Secrets読み込みを `[supabase]` と従来の `SUPABASE_URL` 形式の両方に対応
- users をSupabase対象に追加
- 4テーブルをupsert方式に変更
- Supabase接続診断画面を追加
- Supabase成功後もSQLiteへミラー保存
