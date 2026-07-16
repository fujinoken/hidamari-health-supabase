import streamlit as st

from hidamari.config.menu import menu_category_label, menu_display_label


_build_menu_groups_from_settings = None
_filter_admin_menus = None


def configure_sidebar(build_menu_groups_from_settings, filter_admin_menus):
    global _build_menu_groups_from_settings, _filter_admin_menus
    _build_menu_groups_from_settings = build_menu_groups_from_settings
    _filter_admin_menus = filter_admin_menus


def flatten_menu_groups(groups):
    menus = []
    for values in groups.values():
        for item in values:
            if item not in menus:
                menus.append(item)
    return menus


def render_sidebar_menu(role, app_version, app_copy):
    """カテゴリ選択＋メニュー選択の共通サイドバー表示。"""
    if _build_menu_groups_from_settings is None or _filter_admin_menus is None:
        raise RuntimeError("configure_sidebar() must be called before render_sidebar_menu().")

    try:
        groups = _build_menu_groups_from_settings(role)
    except Exception:
        groups = {}
    if not isinstance(groups, dict):
        groups = {}
    filtered_flat = _filter_admin_menus(flatten_menu_groups(groups))
    safe_groups = {}
    for category, menu_names in groups.items():
        visible = [name for name in menu_names if name in filtered_flat]
        if visible:
            safe_groups[category] = visible
    groups = safe_groups
    with st.sidebar:
        st.markdown(f'<div class="sidebar-title">ひだまり</div><div class="sidebar-sub">{app_version}<br>{app_copy}</div>', unsafe_allow_html=True)
        st.caption(f"ログイン：{st.session_state.get('user_label', '')}")
        st.caption("区分：管理者メニュー" if role == "admin" else "区分：職員入力メニュー")
        st.divider()
        if not groups or not filtered_flat:
            st.error("表示できるメニューがありません。管理者にメニュー設定の確認を依頼してください。")
            return None
        if role != "admin":
            category_names = list(groups.keys())
            default_category = st.session_state.get("main_menu_category_staff", category_names[0])
            if default_category not in category_names:
                default_category = category_names[0]
            category = st.selectbox("目的を選ぶ", category_names, index=category_names.index(default_category), key="main_menu_category_staff", format_func=menu_category_label)
            menu_options = [m for m in groups.get(category, []) if m in filtered_flat]
            if not menu_options:
                menu_options = filtered_flat
            if not menu_options:
                st.error("このカテゴリに表示できる画面がありません。")
                return None
            selected = st.radio("開く画面", menu_options, key=f"main_menu_staff_{category}", format_func=menu_display_label)
            return selected
        category_names = list(groups.keys())
        default_category = st.session_state.get("main_menu_category", category_names[0])
        if default_category not in category_names:
            default_category = category_names[0]
        category = st.selectbox("目的を選ぶ", category_names, index=category_names.index(default_category), key="main_menu_category", format_func=menu_category_label)
        menu_options = [m for m in groups.get(category, []) if m in filtered_flat]
        if not menu_options:
            menu_options = filtered_flat
        if not menu_options:
            st.error("このカテゴリに表示できる画面がありません。")
            return None
        previous_menu = st.session_state.get("main_menu_selected", menu_options[0])
        menu_index = menu_options.index(previous_menu) if previous_menu in menu_options else 0
        selected = st.radio("開く画面", menu_options, index=menu_index, key=f"main_menu_selected_{category}", format_func=menu_display_label)
        st.session_state["main_menu_selected"] = selected
        return selected
