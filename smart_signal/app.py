"""
Smart Signal — Adaptive Traffic Light Dashboard
================================================
Main entry point for the Streamlit application.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""
import streamlit as st
from theme.styles import THEME_CSS
from state.session import init_state
from ui.annotation_panel import annotation_panel
from ui.analysis_tab import analysis_tab
from ui.sidebar import render_sidebar
from config.constants import DIRECTIONS


def main() -> None:
    st.set_page_config(
        page_title="Smart Signal — Adaptive Traffic Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    init_state()

    st.markdown(
        """
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <div>
                <span style="font-size:20px;font-weight:700;color:#F1F5F9;letter-spacing:-0.02em;">
                    Smart Signal
                </span>
                <span style="font-size:12px;color:#64748B;margin-left:12px;">
                    Adaptive Traffic Light Dashboard
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_sidebar()

    tabs = st.tabs([d.upper() for d in DIRECTIONS] + ["Analysis"])

    for tab, direction in zip(tabs[:4], DIRECTIONS):
        with tab:
            annotation_panel(direction)

    with tabs[4]:
        analysis_tab()


if __name__ == "__main__":
    main()