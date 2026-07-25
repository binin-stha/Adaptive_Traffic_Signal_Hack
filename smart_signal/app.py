"""Smart Signal — entry point (Art Deco shell)."""

import streamlit as st

from state.session import init_state
from theme.styles import THEME_CSS, DASHBOARD_CSS
from ui.control_room import control_room
from ui.setup_view import setup_view

C = {"surface": "#141414", "border-h": "#D4AF37", "gold": "#D4AF37",
     "text-dim": "#888888"}
F_DISPLAY = "'Marcellus', serif"
F_BODY = "'Josefin Sans', sans-serif"


def main() -> None:
    st.set_page_config(
        page_title="Smart Signal — Adaptive Signal Operations",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)
    init_state()

    # Slim brand bar + view switcher
    brand_col, switch_col = st.columns([3, 2])
    with brand_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;padding:10px 4px;">'
            f'<div style="width:12px;height:12px;transform:rotate(45deg);border:2px solid {C["gold"]};'
            f'box-shadow:0 0 10px {C["gold"]};flex:none;"></div>'
            f'<div style="font-family:{F_DISPLAY};font-size:20px;letter-spacing:0.24em;color:{C["gold"]};">'
            f'SMART SIGNAL</div>'
            f'<div style="font-family:{F_BODY};font-size:10px;color:{C["text-dim"]};'
            f'text-transform:uppercase;letter-spacing:0.14em;">Intersection Intelligence</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with switch_col:
        view = st.radio(
            "View", ["Control Room", "Setup"], horizontal=True,
            key="main_view", label_visibility="collapsed",
        )

    if view == "Control Room":
        control_room()
    else:
        setup_view()


if __name__ == "__main__":
    main()