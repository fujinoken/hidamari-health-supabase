import os
from datetime import timedelta

import pandas as pd
import streamlit as st

from hidamari.core.text_utils import clean_text
from hidamari.core.time_utils import format_now_jst


AI_ADMIN_REPORT_DISCLAIMER = "※このレポートは診断ではありません。記録を整理し、管理者の見落としを減らすための確認メモです。最終判断は必ず人が行ってください。"
AI_API_KEY_MISSING_MESSAGE = "OpenAI APIキーが未設定です。"
AI_LIBRARY_MISSING_MESSAGE = "OpenAIライブラリが未インストールです。requirements.txt に openai を追加してください。"


def _ai_secret_get(container, key, default=""):
    try:
        if container is None:
            return default
        if hasattr(container, "get"):
            return container.get(key, default)
        return container[key]
    except Exception:
        return default


def get_openai_api_key(input_key=""):
    """OpenAI APIキーを取得。Streamlit Secrets → 環境変数 → 画面入力の順で使います。"""
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    try:
        openai_section = st.secrets.get("openai", {})
        key = _ai_secret_get(openai_section, "api_key", "")
        if key:
            return str(key).strip()
    except Exception:
        pass
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        return key
    return clean_text(input_key)


def filter_records_by_period(df, date_col, start_day, end_day, user_name=None):
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame(columns=df.columns if df is not None else [])
    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    mask = (work[date_col].dt.date >= start_day) & (work[date_col].dt.date <= end_day)
    if user_name and user_name != "全員" and "利用者名" in work.columns:
        mask &= work["利用者名"].astype(str) == str(user_name)
    return work[mask].copy()


def text_contains_any(text, words):
    text = clean_text(text)
    return any(w in text for w in words)


def analyze_structured_insights(health_df, ex_df, handover_df, goal_df, user_name, end_day, start_day=None, period_label=""):
    """OpenAIなしでも使える、記録ベースの管理者向け分析。診断はしない。"""
    if start_day is None:
        start_day = end_day - timedelta(days=6)
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    period_days = (end_day - start_day).days + 1
    period_label = period_label or f"直近{period_days}日"
    h = filter_records_by_period(health_df, "記録日", start_day, end_day, user_name)
    e = filter_records_by_period(ex_df, "記録日", start_day, end_day, user_name)
    b = filter_records_by_period(handover_df, "日付", start_day, end_day, None)
    g = filter_records_by_period(goal_df, "日付", start_day, end_day, user_name)

    findings = []
    checks = []
    goal_summary = []

    if not h.empty:
        change_items = []
        for col in ["気になる変化", "家族共有メモ", "LIFE補助メモ"]:
            if col in h.columns:
                change_items += [clean_text(x) for x in h[col].dropna().tolist() if clean_text(x)]
        if change_items:
            findings.append(f"{period_label}で、気になる変化・共有メモが {len(change_items)} 件記録されています。")
            checks.append("気になる変化が、どの時間帯・どの場面で出ているかを職員間でそろえて確認すると整理しやすくなります。")

        joined = " ".join(h.fillna("").astype(str).agg(" ".join, axis=1).tolist())
        keyword_map = {
            "食事量": ["食欲", "食事少", "摂取少", "食べない", "半量", "残し"],
            "水分": ["水分", "飲まない", "脱水", "濃縮"],
            "睡眠・夜間": ["不眠", "眠れ", "夜間", "覚醒", "徘徊"],
            "痛み": ["痛", "疼痛", "つらい"],
            "転倒リスク": ["ふらつ", "転倒", "歩行不安定", "立位不安定"],
            "気分・不安": ["不安", "拒否", "怒", "落ち着か", "涙"],
        }
        for label, words in keyword_map.items():
            if text_contains_any(joined, words):
                findings.append(f"{label}に関係する記録が見られます。")
                checks.append(f"{label}について、普段との違い・続いている日数・関わり方の差を確認してもよいかもしれません。")

        for meal_col in ["朝食摂取率", "昼食摂取率", "夕食摂取率"]:
            if meal_col in h.columns:
                low_count = int((pd.to_numeric(h[meal_col], errors="coerce") <= 50).sum())
                if low_count > 0:
                    findings.append(f"{meal_col}が50％以下の日が {low_count} 件あります。")
                    checks.append(f"{meal_col}の低下が一時的か、複数日続いているかを確認してください。")

        numeric_checks = [("体温", 37.5, "以上"), ("SpO2", 93, "以下"), ("血圧上", 160, "以上")]
        for col, threshold, direction in numeric_checks:
            if col in h.columns:
                vals = pd.to_numeric(h[col], errors="coerce")
                cnt = int((vals >= threshold).sum()) if direction == "以上" else int(((vals <= threshold) & (vals > 0)).sum())
                if cnt > 0:
                    findings.append(f"{col}が確認目安にかかる記録が {cnt} 件あります。")
                    checks.append(f"{col}について、入力ミスではないか、普段値との差があるかを確認してください。")
    else:
        findings.append(f"{period_label}の健康チェック記録が確認できません。")
        checks.append("記録漏れか、入力日・利用者名の表記ゆれがないか確認してください。")

    if not e.empty:
        stool_df = e[e.get("便量", "").astype(str).fillna("なし") != "なし"] if "便量" in e.columns else pd.DataFrame()
        if stool_df.empty:
            findings.append(f"{period_label}の排便記録が確認できません。")
            checks.append("排便記録の入力漏れか、実際に間隔が空いているのかを確認してください。")
        else:
            last_day = pd.to_datetime(stool_df["記録日"], errors="coerce").max()
            if pd.notna(last_day):
                days = (end_day - last_day.date()).days
                if days >= 3:
                    findings.append(f"排便記録の最終確認から {days} 日経過しています。")
                    checks.append("普段の排便間隔、水分・食事量、腹部症状の記録を確認してください。")
        if "尿性状" in e.columns and int((e["尿性状"].astype(str) == "濃縮尿").sum()) > 0:
            findings.append("濃縮尿の記録があります。")
            checks.append("水分摂取量や食事量の記録と合わせて確認してください。")
        if "便性状" in e.columns:
            loose_count = int(e["便性状"].astype(str).isin(["下痢便", "水様便"]).sum())
            if loose_count > 0:
                findings.append(f"下痢便・水様便の記録が {loose_count} 件あります。")
                checks.append("一時的な記録か、複数回続いているかを申し送りで共有してください。")

    if not b.empty:
        urgent = 0
        if "優先度" in b.columns:
            urgent += int(b["優先度"].astype(str).isin(["高", "至急", "重要"]).sum())
        if "対応状況" in b.columns:
            pending = int(b["対応状況"].astype(str).isin(["未対応", "確認中"]).sum())
            if pending > 0:
                findings.append(f"業務全体申し送りに未対応・確認中の記録が {pending} 件あります。")
                checks.append("利用者個別の変化と、全体申し送りの未対応事項が重なっていないか確認してください。")
        if urgent > 0:
            findings.append(f"業務全体申し送りに優先度の高い記録が {urgent} 件あります。")

    if not g.empty:
        for goal, grp in g.groupby("短期目標"):
            total = len(grp)
            done = int(grp["実施状況"].astype(str).isin(["実施", "一部実施", "できた", "○"]).sum()) if "実施状況" in grp.columns else 0
            partial = int((grp["実施状況"].astype(str) == "一部実施").sum()) if "実施状況" in grp.columns else 0
            not_done = int((grp["実施状況"].astype(str) == "未実施").sum()) if "実施状況" in grp.columns else 0
            rate = round(done / total * 100, 1) if total else 0
            goal_summary.append(f"{goal}：記録{total}回／実施・一部実施{done}回／未実施{not_done}回／実施率{rate}%")
            if rate < 70:
                findings.append(f"短期目標『{goal}』の実施率が {rate}% です。")
                checks.append(f"『{goal}』について、未実施理由・実施しにくい時間帯・職員間の見え方の差を確認してください。")
            if partial > 0:
                checks.append(f"『{goal}』は一部実施の記録があります。どこまでできたかを次回記録でそろえると分析しやすくなります。")
    else:
        checks.append("短期目標の実施記録がない場合は、ケアプランの短期目標と日々の記録がつながっているか確認してください。")

    if not findings:
        findings.append(f"{period_label}の記録上、大きな変化は目立っていません。")
    if not checks:
        checks.append("現在の記録を継続し、気になる変化が出た場合は早めに共有してください。")

    return {"findings": findings, "checks": checks, "goal_summary": goal_summary, "start_day": start_day, "end_day": end_day}


def build_ai_structured_context(health_df, ex_df, handover_df, goal_df, user_name, end_day, rule_result, start_day=None, period_label=""):
    if start_day is None:
        start_day = end_day - timedelta(days=6)
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    period_label = period_label or f"直近{(end_day - start_day).days + 1}日"
    h = filter_records_by_period(health_df, "記録日", start_day, end_day, user_name)
    e = filter_records_by_period(ex_df, "記録日", start_day, end_day, user_name)
    b = filter_records_by_period(handover_df, "日付", start_day, end_day, None)
    g = filter_records_by_period(goal_df, "日付", start_day, end_day, user_name)

    def table_text(df, max_rows=20):
        if df is None or df.empty:
            return "記録なし"
        show = df.tail(max_rows).copy()
        for col in show.columns:
            show[col] = show[col].apply(clean_text)
        return show.to_string(index=False)

    rules = "\n".join(["【記録上の気づき】"] + [f"- {x}" for x in rule_result.get("findings", [])] + ["【管理者確認ポイント】"] + [f"- {x}" for x in rule_result.get("checks", [])])
    goals = "\n".join(rule_result.get("goal_summary", [])) or "短期目標集計なし"

    return f"""
あなたは介護施設の管理者支援のための記録整理係です。
医療判断・診断・治療判断・受診判断の断定は禁止です。
記録に基づき、現場の気づきを構造化してください。

【分析対象】
利用者：{user_name}
対象期間：{start_day}〜{end_day}（{period_label}）

【ルールベース分析】
{rules}

【短期目標集計】
{goals}

【健康チェック記録】
{table_text(h)}

【排泄記録】
{table_text(e)}

【業務全体申し送り】
{table_text(b)}

【短期目標実施記録】
{table_text(g)}
""".strip()


def hidamari_ai_to_date_series(series):
    try:
        return pd.to_datetime(series, errors="coerce").dt.date
    except Exception:
        return pd.Series([None] * len(series))


def hidamari_ai_filter_period(df, date_col, user_name="", start_date=None, end_date=None):
    """利用者名と期間でDataFrameを安全に抽出する。"""
    if df is None or df.empty:
        return pd.DataFrame()
    work = df.copy()
    if date_col not in work.columns:
        return work.iloc[0:0].copy()
    work["_ai_date"] = hidamari_ai_to_date_series(work[date_col])
    if user_name and "利用者名" in work.columns:
        work = work[work["利用者名"].astype(str).str.strip() == str(user_name).strip()].copy()
    if start_date is not None:
        work = work[work["_ai_date"] >= start_date].copy()
    if end_date is not None:
        work = work[work["_ai_date"] <= end_date].copy()
    return work.drop(columns=["_ai_date"], errors="ignore")


def hidamari_ai_clean(value, default=""):
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in ["nan", "none", "nat"]:
        return default
    return text


def hidamari_ai_num(series):
    try:
        return pd.to_numeric(series, errors="coerce")
    except Exception:
        return pd.Series(dtype=float)


def hidamari_ai_mean_text(df, col, suffix=""):
    if df is None or df.empty or col not in df.columns:
        return "記録なし"
    vals = hidamari_ai_num(df[col]).dropna()
    if vals.empty:
        return "記録なし"
    return f"平均 {vals.mean():.1f}{suffix}（最小 {vals.min():.1f}／最大 {vals.max():.1f}）"


def hidamari_ai_percent_text(df, col):
    return hidamari_ai_mean_text(df, col, "%")


def hidamari_ai_text_join(values, limit=8):
    items = []
    for v in values:
        t = hidamari_ai_clean(v)
        if t and t not in items:
            items.append(t)
        if len(items) >= limit:
            break
    return "／".join(items) if items else "特記なし"


def hidamari_ai_detect_health_changes(health_df):
    lines = []
    if health_df is None or health_df.empty:
        return ["健康記録は対象期間内にありません。"]

    lines.append(f"健康チェック記録：{len(health_df)}件")
    for col, suffix in [("体温", "℃"), ("血圧上", ""), ("血圧下", ""), ("脈拍", "回/分"), ("SpO2", "%"), ("体重", "kg"), ("水分摂取量ml", "ml")]:
        if col in health_df.columns:
            lines.append(f"{col}：{hidamari_ai_mean_text(health_df, col, suffix)}")

    for col in ["朝食摂取率", "昼食摂取率", "夕食摂取率"]:
        if col in health_df.columns:
            lines.append(f"{col}：{hidamari_ai_percent_text(health_df, col)}")

    memo_cols = [c for c in ["気になる変化", "家族共有メモ", "LIFE補助メモ", "栄養リスク", "口腔状態"] if c in health_df.columns]
    memos = []
    for c in memo_cols:
        memos.extend(health_df[c].dropna().astype(str).tolist())
    if memos:
        lines.append("記録上の気になる記述：" + hidamari_ai_text_join(memos, limit=10))
    return lines


def hidamari_ai_detect_excretion(ex_df):
    lines = []
    if ex_df is None or ex_df.empty:
        return ["排泄記録は対象期間内にありません。"]

    lines.append(f"排泄チェック記録：{len(ex_df)}件")
    if "尿量" in ex_df.columns:
        urine_counts = ex_df["尿量"].fillna("").astype(str).value_counts().to_dict()
        lines.append("尿量内訳：" + "、".join([f"{k}:{v}件" for k, v in urine_counts.items() if k]))
    if "尿性状" in ex_df.columns:
        urine_type_counts = ex_df["尿性状"].fillna("").astype(str).value_counts().to_dict()
        lines.append("尿性状内訳：" + "、".join([f"{k}:{v}件" for k, v in urine_type_counts.items() if k]))

    stool_df = ex_df.copy()
    if "便量" in stool_df.columns:
        stool_yes = stool_df[~stool_df["便量"].fillna("").astype(str).isin(["", "なし", "0", "未記録"])]
        lines.append(f"排便あり記録：{len(stool_yes)}件")
        if not stool_yes.empty and "記録日" in stool_yes.columns:
            dts = pd.to_datetime(stool_yes["記録日"], errors="coerce").dropna()
            if not dts.empty:
                lines.append(f"最終排便記録日：{dts.max().strftime('%Y-%m-%d')}")
        stool_counts = stool_df["便量"].fillna("").astype(str).value_counts().to_dict()
        lines.append("便量内訳：" + "、".join([f"{k}:{v}件" for k, v in stool_counts.items() if k]))
    if "便性状" in ex_df.columns:
        stool_type_counts = ex_df["便性状"].fillna("").astype(str).value_counts().to_dict()
        lines.append("便性状内訳：" + "、".join([f"{k}:{v}件" for k, v in stool_type_counts.items() if k]))

    if "排泄メモ" in ex_df.columns:
        memos = ex_df["排泄メモ"].dropna().astype(str).tolist()
        if memos:
            lines.append("排泄メモ：" + hidamari_ai_text_join(memos, limit=10))
    return lines


def hidamari_ai_detect_handover(handover_df):
    lines = []
    if handover_df is None or handover_df.empty:
        return ["申し送り記録は対象期間内にありません。"]

    lines.append(f"申し送り記録：{len(handover_df)}件")
    if "優先度" in handover_df.columns:
        priority_counts = handover_df["優先度"].fillna("").astype(str).value_counts().to_dict()
        lines.append("優先度内訳：" + "、".join([f"{k}:{v}件" for k, v in priority_counts.items() if k]))
    if "対応状況" in handover_df.columns:
        status_counts = handover_df["対応状況"].fillna("").astype(str).value_counts().to_dict()
        lines.append("対応状況内訳：" + "、".join([f"{k}:{v}件" for k, v in status_counts.items() if k]))

    text_cols = [c for c in ["全体申し送り", "要確認事項", "Excel自動抽出情報"] if c in handover_df.columns]
    notes = []
    for _, row in handover_df.iterrows():
        date_text = hidamari_ai_clean(row.get("日付", ""))
        pri = hidamari_ai_clean(row.get("優先度", ""))
        status = hidamari_ai_clean(row.get("対応状況", ""))
        body = "／".join([hidamari_ai_clean(row.get(c, "")) for c in text_cols if hidamari_ai_clean(row.get(c, ""))])
        if body:
            notes.append(f"{date_text} {pri} {status}：{body}")
    if notes:
        lines.append("気になる申し送り抜粋：" + "\n- " + "\n- ".join(notes[:10]))
    return lines


def hidamari_ai_detect_short_goals(goal_df, goal_check_df):
    lines = []
    if (goal_df is None or goal_df.empty) and (goal_check_df is None or goal_check_df.empty):
        return ["短期目標関連記録は対象期間内にありません。"]

    if goal_df is not None and not goal_df.empty:
        lines.append(f"短期目標マスタ：{len(goal_df)}件")
        if "短期目標" in goal_df.columns:
            lines.append("登録中の短期目標：" + hidamari_ai_text_join(goal_df["短期目標"].tolist(), limit=6))

    if goal_check_df is not None and not goal_check_df.empty:
        lines.append(f"短期目標実施チェック：{len(goal_check_df)}件")
        if "実施状況" in goal_check_df.columns:
            counts = goal_check_df["実施状況"].fillna("").astype(str).value_counts().to_dict()
            lines.append("実施状況内訳：" + "、".join([f"{k}:{v}件" for k, v in counts.items() if k]))
            done = sum(v for k, v in counts.items() if "実施" in str(k) and "未" not in str(k))
            total = sum(v for k, v in counts.items() if str(k).strip())
            if total:
                lines.append(f"概算実施率：{done / total * 100:.1f}%")
        memo_cols = [c for c in ["本人の様子", "未実施理由", "職員メモ"] if c in goal_check_df.columns]
        memos = []
        for c in memo_cols:
            memos.extend(goal_check_df[c].dropna().astype(str).tolist())
        if memos:
            lines.append("実施記録メモ：" + hidamari_ai_text_join(memos, limit=10))
    return lines


def hidamari_ai_detect_monitoring(monitoring_df):
    lines = []
    if monitoring_df is None or monitoring_df.empty:
        return ["モニタリング下書きは対象期間内にありません。"]

    lines.append(f"モニタリング下書き：{len(monitoring_df)}件")
    for col in ["実施率", "本人の様子まとめ", "未実施理由まとめ", "モニタリング下書き", "今後の方向性"]:
        if col in monitoring_df.columns:
            vals = [hidamari_ai_clean(v) for v in monitoring_df[col].tolist()]
            vals = [v for v in vals if v]
            if vals:
                lines.append(f"{col}：" + hidamari_ai_text_join(vals, limit=5))
    return lines


def hidamari_ai_build_admin_report(user_name, start_date, end_date, records):
    period_text = f"{start_date}〜{end_date}"
    health_lines = hidamari_ai_detect_health_changes(records.get("health"))
    ex_lines = hidamari_ai_detect_excretion(records.get("excretion"))
    handover_lines = hidamari_ai_detect_handover(records.get("handover"))
    goal_lines = hidamari_ai_detect_short_goals(records.get("short_goal_master"), records.get("short_goal_checks"))
    mon_lines = hidamari_ai_detect_monitoring(records.get("monitoring"))

    check_points = []
    joined = "\n".join(health_lines + ex_lines + handover_lines + goal_lines + mon_lines)
    if "濃縮尿" in joined or "水分" in joined:
        check_points.append("水分摂取量・尿性状・声かけ状況を確認する。")
    if "排便あり記録：0件" in joined or "便量内訳：なし" in joined:
        check_points.append("排便間隔、腹部症状、食事量、下剤等の情報を確認する。")
    if "未対応" in joined or "対応中" in joined:
        check_points.append("申し送りの未対応・対応中項目に、次の一手と担当が残っているか確認する。")
    if "概算実施率" in joined:
        check_points.append("短期目標の実施率だけでなく、本人の様子と未実施理由をあわせて確認する。")
    if not check_points:
        check_points.append("大きな偏りは記録上目立ちません。継続して通常観察を行う。")

    family_summary = [
        "記録に基づく共有では、診断や断定を避け、事実・変化・今後の見守り方針を分けて説明する。",
        "家族共有メモや申し送りの要確認事項がある場合は、生活上の変化としてやわらかく伝える。",
    ]

    monitoring_draft = [
        f"{period_text}の記録を確認したところ、健康チェック・排泄チェック・申し送り・短期目標実施状況をもとに、生活状況を継続観察している。",
        "体調・食事水分・排泄・本人の様子に関する記録をもとに、必要時は職員間で共有し、次回確認につなげる。",
        "医療的判断は行わず、気になる変化が続く場合は管理者・看護職・主治医等へ確認する。",
    ]

    def bullet(lines):
        return "\n".join([f"- {x}" for x in lines if hidamari_ai_clean(x)])

    return f"""# ひだまりAI管理者レポート

対象利用者：{user_name}
対象期間：{period_text}
作成日時：{format_now_jst("%Y-%m-%d %H:%M:%S")}

{AI_ADMIN_REPORT_DISCLAIMER}

## 1. この期間の体調変化
{bullet(health_lines)}

## 2. 排泄リズムの変化
{bullet(ex_lines)}

## 3. 食事・水分・睡眠の傾向
- 食事は健康チェックの朝食・昼食・夕食摂取率を中心に確認しています。
- 水分は「水分摂取量ml」の記録を中心に確認しています。
- 睡眠項目が記録欄にない場合は、申し送り・気になる変化欄の記述から補助的に確認してください。

## 4. 気になる申し送り
{bullet(handover_lines)}

## 5. 短期目標の実施状況
{bullet(goal_lines)}

## 6. 家族説明用まとめ
{bullet(family_summary)}

## 7. モニタリング下書き
{bullet(monitoring_draft)}
{bullet(mon_lines)}

## 8. 管理者確認ポイント
{bullet(check_points)}
"""
