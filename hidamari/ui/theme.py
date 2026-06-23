import streamlit as st

from hidamari.core.text_utils import clean_text


APP_VERSION = "Ver4.6 AI管理者アシスタント版"
APP_COPY = "押し間違えず、迷わず、観察して次につなぐ 現場OS"

UI_COLORS = {
    "staff": {"bg": "#FFFDF7", "surface": "#FFFFFF", "surface_soft": "#FFF7EC", "accent": "#C9705C", "accent_dark": "#8F4C3E", "sub": "#6A5B52", "border": "#E8D7C5"},
    "admin": {"bg": "#F6F8F7", "surface": "#FFFFFF", "surface_soft": "#EEF4F1", "accent": "#2F6F5E", "accent_dark": "#244D43", "sub": "#52605B", "border": "#C9DAD2"},
}

_get_app_setting = None


def configure_theme_settings(get_app_setting):
    global _get_app_setting
    _get_app_setting = get_app_setting


def get_color_settings():
    """色設定をSQLiteから取得し、UI_COLORSへ反映するための値を返す。"""
    default = {
        "staff_bg": UI_COLORS["staff"]["bg"],
        "staff_accent": UI_COLORS["staff"]["accent"],
        "admin_bg": UI_COLORS["admin"]["bg"],
        "admin_accent": UI_COLORS["admin"]["accent"],
        "alert": "#C9705C",
        "success": "#2F6F5E",
    }
    saved = _get_app_setting("color_settings", default) if callable(_get_app_setting) else default
    if not isinstance(saved, dict):
        saved = default
    merged = {**default, **saved}
    return merged


def get_ui_theme():
    role_now = st.session_state.get("role", "staff")
    base = dict(UI_COLORS["admin"] if role_now == "admin" else UI_COLORS["staff"])
    colors = get_color_settings()
    if role_now == "admin":
        base["bg"] = clean_text(colors.get("admin_bg"), base["bg"])
        base["accent"] = clean_text(colors.get("admin_accent"), base["accent"])
        base["accent_dark"] = clean_text(colors.get("admin_accent"), base["accent_dark"])
    else:
        base["bg"] = clean_text(colors.get("staff_bg"), base["bg"])
        base["accent"] = clean_text(colors.get("staff_accent"), base["accent"])
        base["accent_dark"] = clean_text(colors.get("staff_accent"), base["accent_dark"])
    return base


def apply_design():
    """共通デザイン。色・余白・ボタン・iPad表示をここで一元管理する。"""
    theme = get_ui_theme()
    st.markdown(
        f"""
        <style>
        :root {{
            --hidamari-bg: {theme['bg']};
            --hidamari-surface: {theme['surface']};
            --hidamari-soft: {theme['surface_soft']};
            --hidamari-accent: {theme['accent']};
            --hidamari-accent-dark: {theme['accent_dark']};
            --hidamari-sub: {theme['sub']};
            --hidamari-border: {theme['border']};
        }}
        .stApp {{ background: var(--hidamari-bg); }}
        h1, h2, h3 {{ color: var(--hidamari-accent-dark); letter-spacing: .01em; }}
        h1 {{ font-size: 2rem; }} h2 {{ font-size: 1.55rem; }} h3 {{ font-size: 1.22rem; }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, var(--hidamari-soft) 0%, #FFFFFF 100%);
            border-right: 1px solid var(--hidamari-border);
        }}
        [data-testid="stSidebar"] * {{ font-size: 0.98rem; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1280px; }}
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button,
        button[kind="primary"], button[kind="secondary"] {{
            min-height: 48px; border-radius: 14px !important; font-weight: 700 !important;
            border: 1px solid var(--hidamari-border) !important;
        }}
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover {{
            border-color: var(--hidamari-accent) !important; color: var(--hidamari-accent-dark) !important;
        }}
        div[data-baseweb="select"] > div, input, textarea {{ min-height: 46px; border-radius: 12px !important; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; flex-wrap: wrap; }}
        .stTabs [data-baseweb="tab"] {{
            background: #ffffff; border: 1px solid var(--hidamari-border); border-radius: 999px; padding: 8px 14px;
        }}
        .stTabs [aria-selected="true"] {{ background: var(--hidamari-soft) !important; color: var(--hidamari-accent-dark) !important; font-weight: 800; }}
        .info-box, .ui-card {{
            background: var(--hidamari-surface); padding: 16px 18px; border-radius: 18px;
            border: 1px solid var(--hidamari-border); margin: 10px 0 14px 0;
            box-shadow: 0 6px 18px rgba(45, 64, 55, 0.05);
        }}
        .ui-card-soft {{ background: var(--hidamari-soft); padding: 14px 16px; border-radius: 16px; border: 1px solid var(--hidamari-border); margin: 8px 0 12px 0; }}
        .ui-section-title {{ display:flex; align-items:center; gap:10px; margin:14px 0 8px 0; color:var(--hidamari-accent-dark); font-size:1.25rem; font-weight:850; }}
        .ui-section-caption {{ color: var(--hidamari-sub); margin-bottom: 12px; line-height: 1.65; }}
        .ui-badge {{ display:inline-block; background:#ffffffcc; border:1px solid var(--hidamari-border); color:var(--hidamari-accent-dark); border-radius:999px; padding:5px 11px; margin:3px 5px 3px 0; font-size:.86rem; font-weight:700; }}
        .sidebar-title {{ font-weight:900; color:var(--hidamari-accent-dark); font-size:1.08rem; margin-bottom:2px; }}
        .sidebar-sub {{ color:var(--hidamari-sub); font-size:.82rem; line-height:1.45; margin-bottom:8px; }}
        .hidamari-hero {{
            background: linear-gradient(135deg, #F7F2EA 0%, #EEF5EF 58%, #EAF1F5 100%);
            border: 1px solid rgba(88, 112, 96, 0.16); border-radius: 28px; padding: 28px 26px;
            margin: 8px auto 22px auto; max-width: 880px; text-align: center; box-shadow: 0 10px 28px rgba(55, 64, 58, 0.08); position: relative; overflow: hidden;
        }}
        .hidamari-hero-title {{ font-size: 2.25rem; line-height: 1.25; font-weight: 800; color: #2F6F5E; margin-bottom: 8px; letter-spacing: 0.02em; }}
        .hidamari-hero-sub {{ color: #64706A; font-size: 1.05rem; margin-bottom: 14px; }}
        .hidamari-illust-row {{ display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; }}
        .hidamari-illust-card {{ flex: 1 1 210px; background: rgba(255,255,255,0.78); border: 1px solid rgba(0,0,0,0.06); border-radius: 22px; padding: 14px 16px; display: flex; align-items: center; gap: 12px; min-height: 92px; }}
        .hidamari-emoji {{ width:58px; height:58px; border-radius:50%; background:#fff3d6; display:flex; align-items:center; justify-content:center; font-size:34px; flex:0 0 auto; }}
        .hidamari-card-title {{ font-weight:800; color:#3d463d; margin-bottom:4px; }}
        .hidamari-card-text {{ color:#666; font-size:.9rem; line-height:1.45; }}
        .staff-welcome {{ background:linear-gradient(135deg, #F7EFE8 0%, #FAF7F1 100%); border:1px solid #E6C9B7; border-radius:18px; padding:14px 16px; margin:10px 0 16px 0; color:#6A5142; }}
        .admin-welcome {{ background:linear-gradient(135deg, #EAF1F5 0%, #F7FAFA 100%); border:1px solid #BFD0D8; border-radius:18px; padding:14px 16px; margin:10px 0 16px 0; color:#405766; }}
        .mini-badge {{ display:inline-block; background:#ffffffcc; border:1px solid rgba(0,0,0,.08); border-radius:999px; padding:5px 10px; margin:3px 4px 3px 0; font-size:.86rem; }}
        .mindset-box {{ background:#FFFDF7; border:1px solid var(--hidamari-border); border-left:6px solid var(--hidamari-accent); border-radius:16px; padding:13px 15px; margin:10px 0 14px 0; color:var(--hidamari-sub); line-height:1.65; }}
        .mindset-title {{ color:var(--hidamari-accent-dark); font-weight:850; margin-bottom:4px; }}
        .check-card {{ background:#FFFFFF; border:1px solid var(--hidamari-border); border-radius:14px; padding:12px 14px; margin:7px 0; }}
        .stop-card {{ background:#FFF7EC; border:1px solid #E6C9B7; border-radius:14px; padding:12px 14px; margin:7px 0; }}
        @media (max-width: 900px) {{
            .block-container {{ padding-left:.8rem; padding-right:.8rem; }}
            h1 {{ font-size:1.55rem; }} h2 {{ font-size:1.35rem; }} h3 {{ font-size:1.12rem; }}
            div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {{ min-height:52px; font-size:1rem; }}
            .hidamari-hero {{ padding:20px 16px; border-radius:20px; }}
            .hidamari-hero-title {{ font-size:1.55rem; }}
            .hidamari-illust-card {{ flex:1 1 100%; }}
            .hidamari-emoji {{ width:48px; height:48px; font-size:28px; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_product_ui_ux():
    """
    余白を守るOS UI。
    目的：情報密度を下げ、白背景・行間・カード余白・ボタン間隔を広げ、
    現場が焦らず操作できる画面にする。
    """
    theme = get_ui_theme()
    color_setting = get_color_settings()
    bg = clean_text(theme.get("bg"), "#FFFFFF")
    surface = clean_text(theme.get("surface"), "#FFFFFF")
    soft = clean_text(theme.get("surface_soft"), bg)
    accent = clean_text(theme.get("accent"), "#C9705C")
    accent_dark = clean_text(theme.get("accent_dark"), accent)
    sub = clean_text(theme.get("sub"), "#666666")
    border = clean_text(theme.get("border"), "#E7E1D8")
    alert = clean_text(color_setting.get("alert"), accent)
    success = clean_text(color_setting.get("success"), accent_dark)

    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            -webkit-text-size-adjust: 100%;
            line-height: 1.78 !important;
        }}
        .stApp {{ background: {bg} !important; }}
        .block-container {{
            max-width: 1180px !important;
            padding-top: 1.8rem !important;
            padding-left: 2.1rem !important;
            padding-right: 2.1rem !important;
            padding-bottom: 4.5rem !important;
        }}
        h1, h2, h3 {{
            letter-spacing: .02em !important;
            line-height: 1.45 !important;
            margin-top: 1.3rem !important;
            margin-bottom: .9rem !important;
        }}
        h1 {{ font-size: 1.95rem !important; }}
        h2 {{ font-size: 1.48rem !important; }}
        h3 {{ font-size: 1.2rem !important; }}
        p, li, div, span {{ line-height: 1.78; }}
        [data-testid="stSidebar"] {{
            background: {surface} !important;
            border-right: 1px solid {border} !important;
            min-width: 300px;
        }}
        [data-testid="stSidebar"] .stRadio label {{
            background: {surface} !important;
            border: 1px solid {border} !important;
            border-radius: 16px !important;
            padding: 12px 13px !important;
            margin: 8px 0 !important;
            line-height: 1.55 !important;
        }}
        [data-testid="stSidebar"] .stRadio label:hover {{
            border-color: {accent} !important;
            background: {soft} !important;
        }}
        div[data-testid="stButton"],
        div[data-testid="stDownloadButton"] {{
            margin-top: .45rem !important;
            margin-bottom: .75rem !important;
        }}
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {{
            min-height: 62px !important;
            border-radius: 20px !important;
            font-size: 1.02rem !important;
            font-weight: 750 !important;
            letter-spacing: .02em;
            white-space: normal !important;
            line-height: 1.45 !important;
            box-shadow: none !important;
            border: 1px solid {border} !important;
            background: {surface} !important;
            color: {accent_dark} !important;
        }}
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stButton"] button[kind="secondary"],
        button[kind="primary"],
        button[kind="secondary"] {{ color: {accent_dark} !important; }}
        div[data-testid="stButton"] button:focus,
        div[data-testid="stDownloadButton"] button:focus,
        input:focus,
        textarea:focus {{
            outline: 3px solid rgba(201,112,92,.20) !important;
            outline-offset: 3px !important;
        }}
        div[data-baseweb="select"] > div,
        input,
        textarea,
        .stTextInput input,
        .stNumberInput input,
        .stDateInput input {{
            min-height: 58px !important;
            font-size: 1.02rem !important;
            border-radius: 18px !important;
            line-height: 1.65 !important;
            background: {surface} !important;
        }}
        textarea {{
            min-height: 140px !important;
            line-height: 1.85 !important;
            padding-top: 14px !important;
            padding-bottom: 14px !important;
        }}
        label, .stMarkdown {{ line-height: 1.75 !important; }}
        div[role="radiogroup"] label,
        label[data-baseweb="checkbox"] {{
            min-height: 50px !important;
            padding-top: 9px !important;
            padding-bottom: 9px !important;
            margin-bottom: 6px !important;
            font-size: 1.0rem !important;
            line-height: 1.6 !important;
        }}
        .ui-card,
        .ui-card-soft,
        .mindset-box,
        .check-card,
        .stop-card,
        .staff-welcome,
        .admin-welcome,
        .safe-note,
        .danger-note,
        .warning-note,
        .info-box {{
            background: {surface} !important;
            border-radius: 26px !important;
            padding: 24px 26px !important;
            margin: 18px 0 26px 0 !important;
            border: 1px solid {border} !important;
            box-shadow: none !important;
            line-height: 1.85 !important;
        }}
        .ui-card-soft,
        .mindset-box,
        .safe-note {{ background: {soft} !important; }}
        .danger-note,
        .warning-note {{ background: {soft} !important; }}
        .ui-card strong,
        .ui-card-soft strong,
        .mindset-title {{
            font-size: 1.08rem !important;
            line-height: 1.6 !important;
        }}
        .ui-section-title {{
            margin: 26px 0 12px 0 !important;
            gap: 12px !important;
            line-height: 1.5 !important;
        }}
        .ui-section-caption {{
            margin-bottom: 22px !important;
            line-height: 1.85 !important;
            color: {sub} !important;
        }}
        .ui-badge, .mini-badge {{
            background: {surface} !important;
            border: 1px solid {border} !important;
            padding: 7px 13px !important;
            margin: 5px 7px 5px 0 !important;
            line-height: 1.5 !important;
            box-shadow: none !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 12px !important;
            flex-wrap: wrap !important;
            margin-bottom: 18px !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            min-height: 52px !important;
            border-radius: 999px !important;
            padding: 12px 18px !important;
            background: {surface} !important;
            border: 1px solid {border} !important;
            line-height: 1.45 !important;
        }}
        div[data-testid="stDataFrame"] {{
            border-radius: 22px !important;
            overflow: hidden;
            border: 1px solid {border} !important;
            margin-top: 16px !important;
            margin-bottom: 24px !important;
            box-shadow: none !important;
        }}
        .hidamari-illust-row,
        .hidamari-illust-card,
        .hidamari-emoji,
        img[alt*="イラスト"],
        img[alt*="illustration"] {{
            display: none !important;
        }}
        .hidamari-hero {{
            background: {surface} !important;
            border: 1px solid {border} !important;
            border-radius: 28px !important;
            padding: 30px 28px !important;
            margin: 12px auto 34px auto !important;
            max-width: 920px !important;
            text-align: left !important;
            box-shadow: none !important;
        }}
        .hidamari-hero-title {{
            font-size: 1.9rem !important;
            line-height: 1.45 !important;
            margin-bottom: 14px !important;
        }}
        .hidamari-hero-sub {{
            font-size: 1.03rem !important;
            line-height: 1.9 !important;
            color: {sub} !important;
            margin-bottom: 0 !important;
        }}
        div[data-testid="column"] {{
            padding-left: .35rem !important;
            padding-right: .35rem !important;
        }}
        @media (max-width: 1100px) {{
            .block-container {{
                padding-left: 1.0rem !important;
                padding-right: 1.0rem !important;
                padding-top: 1.3rem !important;
            }}
            div[data-testid="column"] {{
                min-width: 100% !important;
                flex: 1 1 100% !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
            }}
            div[data-testid="stButton"] button,
            div[data-testid="stDownloadButton"] button {{
                min-height: 66px !important;
                font-size: 1.06rem !important;
            }}
            .stTabs [data-baseweb="tab"] {{
                min-height: 54px !important;
                padding: 13px 18px !important;
            }}
            .ui-card,
            .ui-card-soft,
            .mindset-box,
            .check-card,
            .stop-card,
            .staff-welcome,
            .admin-welcome,
            .safe-note,
            .danger-note,
            .warning-note,
            .info-box {{
                padding: 20px 18px !important;
                margin: 16px 0 24px 0 !important;
                border-radius: 22px !important;
            }}
            .hidamari-hero {{
                padding: 24px 20px !important;
                border-radius: 24px !important;
            }}
            .hidamari-hero-title {{ font-size: 1.5rem !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
