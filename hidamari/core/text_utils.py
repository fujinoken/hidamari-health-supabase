import html

import pandas as pd


def clean_text(value, default=""):
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    text = str(value).strip()
    if text.lower() in ["nan", "none", "nat"]:
        return default
    return text


def html_escape_text(value, default=""):
    return html.escape(clean_text(value, default), quote=True)


def safe_float(value, default=0.0):
    try:
        if pd.isna(value) or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        if pd.isna(value) or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def to_number(series):
    return pd.to_numeric(series, errors="coerce")


def make_date_user_key(record_date, user_name):
    d = pd.to_datetime(record_date, errors="coerce")
    if pd.isna(d):
        return ""
    return f"{d.strftime('%Y-%m-%d')}__{clean_text(user_name)}"


def make_excretion_key(record_date, user_name, slot):
    d = pd.to_datetime(record_date, errors="coerce")
    if pd.isna(d):
        return ""
    return f"{d.strftime('%Y-%m-%d')}__{clean_text(user_name)}__{clean_text(slot)}"


def get_option_index(options, value, default="なし"):
    value = clean_text(value, default)
    if value in options:
        return options.index(value)
    if default in options:
        return options.index(default)
    return 0


def get_life_option_index(options, value, default_index=0):
    value = clean_text(value)
    if value in options:
        return options.index(value)
    if value:
        code = value.split(":")[0].strip()
        for i, opt in enumerate(options):
            if opt.split(":")[0].strip() == code:
                return i
    return default_index


def meal_option_from_percent(percent):
    value = safe_int(percent, 80)
    if value >= 90:
        return "1: 全量（90%以上）"
    if value >= 70:
        return "2: 7〜8割（70〜89%）"
    if value >= 40:
        return "3: 半量（40〜69%）"
    if value >= 1:
        return "4: 1〜3割（1〜39%）"
    return "5: 未摂取（0%）"


def option_code(option_text):
    return clean_text(option_text).split(":")[0].strip()
