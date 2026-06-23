import streamlit as st

from hidamari.core.text_utils import clean_text, html_escape_text


def ui_section(title, caption="", icon="☀️"):
    """画面見出しの共通部品。"""
    safe_icon = html_escape_text(icon)
    safe_title = html_escape_text(title)
    safe_caption = html_escape_text(caption)
    caption_html = f'<div class="ui-section-caption">{safe_caption}</div>' if safe_caption else ""
    st.markdown(f'<div class="ui-section-title"><span>{safe_icon}</span><span>{safe_title}</span></div>{caption_html}', unsafe_allow_html=True)


def ui_card(title, body="", icon="", soft=False):
    """カード表示の共通部品。"""
    cls = "ui-card-soft" if soft else "ui-card"
    safe_icon = html_escape_text(icon)
    safe_title = html_escape_text(title)
    safe_body = html_escape_text(body)
    title_html = f"<strong>{safe_icon + ' ' if safe_icon else ''}{safe_title}</strong>" if safe_title else ""
    st.markdown(f'<div class="{cls}">{title_html}<div style="margin-top:4px; line-height:1.65; color:var(--hidamari-sub);">{safe_body}</div></div>', unsafe_allow_html=True)


def ui_badges(items):
    """小さな状態表示バッジ。"""
    badge_html = "".join([f'<span class="ui-badge">{html_escape_text(x)}</span>' for x in items if clean_text(x)])
    if badge_html:
        st.markdown(badge_html, unsafe_allow_html=True)


def product_ui_notice():
    """商品化UIの短い案内。現在は固定案内を非表示。"""
    return


def danger_note(text):
    """削除・復元などの危険操作用の共通表示。"""
    st.markdown(f'<div class="danger-note">{html_escape_text(text)}</div>', unsafe_allow_html=True)


def safe_note(text):
    """通常の安心メッセージ用の共通表示。"""
    st.markdown(f'<div class="safe-note">{html_escape_text(text)}</div>', unsafe_allow_html=True)


def warning_note(text):
    """注意喚起用の共通表示。"""
    st.markdown(f'<div class="warning-note">{html_escape_text(text)}</div>', unsafe_allow_html=True)


def os_mindset_box(title, body, icon="📝"):
    """現場OSマインド共通表示。"""
    safe_icon = html_escape_text(icon)
    safe_title = html_escape_text(title)
    safe_body = html_escape_text(body)
    st.markdown(
        f'<div class="mindset-box"><div class="mindset-title">{safe_icon} {safe_title}</div><div>{safe_body}</div></div>',
        unsafe_allow_html=True,
    )


def show_observation_perspective(kind="health"):
    """入力画面の観察の視点表示。現在は非表示。"""
    return
