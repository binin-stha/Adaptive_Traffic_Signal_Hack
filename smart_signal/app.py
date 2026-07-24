"""Smart Signal — entry point."""

import streamlit as st

from state.session import init_state
from theme.styles import THEME_CSS
from ui.control_room import control_room
from ui.setup_view import setup_view


def main() -> None:
    st.set_page_config(
        page_title="Smart Signal — Control Room",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    init_state()

    view = st.radio(
        "View",
        ["Control Room", "Setup"],
        horizontal=True,
        key="main_view",
    )

    if view == "Control Room":
        control_room()
    else:
        setup_view()


if __name__ == "__main__":
    main()